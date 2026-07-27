"""
Telemetry Routes
Implements SRS §3.1 - Telemetry Dashboard
"""

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Dict, Optional
import logging
import json
import time
from datetime import datetime
from uuid import uuid4

from api.auth import get_current_user, require_scope, verify_token, User
from api.middleware.response_time import track_ws_relay, record_ingestion_rate, record_ws_connection
from engine.signal import MultiChannelEMAFilter
from database import get_db
from models import Observation

router = APIRouter()
logger = logging.getLogger(__name__)

# Per-channel physiological alarm thresholds evaluated on the EMA-filtered value.
# Prevents false alarms from noisy raw samples (SRS FR-3.5.4).
# Thresholds reflect SRS §3.1.5 (e.g. 150 mmHg arthroscopic pump pressure limit).
ALARM_THRESHOLDS = {
    "pressure": {"high": 150.0},                  # mmHg
    "hr": {"high": 120.0, "low": 50.0},          # bpm
    "spo2": {"low": 90.0},                        # %
    "flow": {"high": 60.0, "low": -60.0},         # L/min
}


def evaluate_alarm(channel: str, filtered_value: Optional[float]) -> Optional[Dict]:
    """
    Evaluate alarm state for a channel using the EMA-filtered value.

    Args:
        channel: Resolved telemetry channel name
        filtered_value: EMA-filtered observation value

    Returns:
        Alarm dict with active flag and severity, or None if channel unknown.

    Implements:
        SRS FR-3.5.4 - Filtered alarms (false alarm prevention)
    """
    thresholds = ALARM_THRESHOLDS.get(channel)
    if not thresholds or filtered_value is None:
        return None

    if "high" in thresholds and filtered_value > thresholds["high"]:
        return {"active": True, "direction": "high", "threshold": thresholds["high"]}
    if "low" in thresholds and filtered_value < thresholds["low"]:
        return {"active": True, "direction": "low", "threshold": thresholds["low"]}
    return {"active": False, "direction": None, "threshold": None}

# Bearer token extractor for WebSocket auth
bearer_scheme = HTTPBearer(auto_error=False)

# Initialize multi-channel EMA filter with per-channel alpha defaults
# Implements SRS FR-3.5.1 - Per-channel EMA filtering
ema_filter = MultiChannelEMAFilter()

# Connection manager for WebSocket clients
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.message_buffer: List[Dict] = []
        self.max_buffer_size = 1000
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        record_ws_connection(1)
        logger.info(f"WebSocket connected: {websocket.client}")
        
        # Send buffered messages for replay
        if self.message_buffer:
            for msg in self.message_buffer[-100:]:
                try:
                    async with track_ws_relay():
                        await websocket.send_json(msg)
                except Exception:
                    break
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            record_ws_connection(-1)
            logger.info(f"WebSocket disconnected: {websocket.client}")
    
    async def broadcast(self, message: Dict):
        """Broadcast message to all connected clients"""
        self.message_buffer.append(message)
        if len(self.message_buffer) > self.max_buffer_size:
            self.message_buffer.pop(0)
        
        disconnected = []
        for connection in self.active_connections:
            try:
                async with track_ws_relay():
                    await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()


@router.websocket("/stream")
async def telemetry_stream(websocket: WebSocket, token: Optional[str] = None):
    """
    WebSocket endpoint for real-time telemetry streaming.
    Implements SRS NFR-R4 - WebSocket with auto-reconnect.
    Requires JWT authentication via query parameter ?token=xxx or Authorization header.
    """
    # Authenticate WebSocket connection
    auth_header = websocket.headers.get("Authorization")
    if not token and auth_header:
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    
    if not token:
        await websocket.close(code=4401, reason="Missing authentication token")
        return
    
    # Verify JWT token
    try:
        payload = verify_token(token)
        if not payload:
            await websocket.close(code=4401, reason="Invalid authentication token")
            return
    except Exception as e:
        await websocket.close(code=4401, reason="Authentication failed")
        return
    
    # Check scope
    scopes = payload.get("scope") or payload.get("scopes") or []
    if "telemetry_read" not in scopes and "admin" not in scopes:
        await websocket.close(code=4403, reason="Insufficient scope")
        return
    
    await manager.connect(websocket)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            
            # Process incoming message
            if data.get("type") == "subscribe":
                await websocket.send_json({
                    "type": "subscribed",
                    "payload": {"channels": data.get("channels", [])},
                    "timestamp": datetime.utcnow().isoformat()
                })
            elif data.get("type") == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


@router.post("/ingest")
async def ingest_telemetry(
    telemetry_data: dict,
    db: Session = Depends(get_db),
    current_user=Depends(require_scope("telemetry_write"))
):
    """
    Ingest telemetry data from medical devices.
    Applies EMA filtering, evaluates alarms on the filtered signal, and persists
    both raw and filtered values to the immutable observations table.
    Implements SRS FR-3.5.1, FR-3.5.3, FR-3.5.4.
    """
    observations = telemetry_data.get("observations", [])
    filtered_observations = []
    alarms = []
    persisted = 0
    ingest_start = time.perf_counter()

    try:
        for obs in observations:
            # Preserve raw value before filtering (FR-3.5.3)
            raw_value = obs.get("valueQuantity", {}).get("value")
            obs["raw_data"] = {
                "value": raw_value,
                "unit": obs.get("valueQuantity", {}).get("unit"),
                "timestamp": datetime.utcnow().isoformat()
            }

            # Apply per-channel EMA filter
            filtered_obs = ema_filter.filter_observation(obs)

            # Alarm evaluation on the EMA-filtered value (FR-3.5.4)
            channel = ema_filter.resolve_channel(filtered_obs)
            filtered_value = (filtered_obs.get("filtered_data") or {}).get("value")
            alarm = evaluate_alarm(channel, filtered_value)
            if alarm:
                filtered_obs["alarm"] = alarm
                if alarm["active"]:
                    alarms.append({"channel": channel, **alarm})

            # Persist raw + filtered to observations table (FR-3.5.3)
            code = filtered_obs.get("code", {}) or {}
            coding = code.get("coding") or [{}]
            obs_code = coding[0].get("code") or code.get("text") or "unknown"
            vq = filtered_obs.get("valueQuantity", {})
            db_obs = Observation(
                observation_uid=str(uuid4()),
                observation_code=obs_code,
                value_quantity=vq,
                unit=vq.get("unit") or vq.get("code"),
                raw_data=filtered_obs.get("raw_data"),
                filtered_data=filtered_obs.get("filtered_data"),
                fhir_resource=filtered_obs,
            )
            db.add(db_obs)
            persisted += 1

            filtered_observations.append(filtered_obs)

        # Durable commit to the append-only observations table
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Failed to persist telemetry observations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist telemetry observations"
        )

    # Update telemetry data with filtered observations
    telemetry_data["observations"] = filtered_observations
    telemetry_data["alarms"] = alarms

    # Record ingestion throughput (NFR-P1)
    if persisted > 0:
        ingest_elapsed = time.perf_counter() - ingest_start
        rate = persisted / max(ingest_elapsed, 0.001)
        record_ingestion_rate(rate)

    # Broadcast to WebSocket clients
    message = {
        "type": "telemetry",
        "payload": telemetry_data,
        "timestamp": datetime.utcnow().isoformat()
    }
    await manager.broadcast(message)

    return {
        "status": "accepted",
        "persisted": persisted,
        "alarms": alarms,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/stream/info")
async def get_stream_info():
    """
    Get telemetry stream information.
    """
    return {
        "stream_url": "ws://localhost:8000/api/telemetry/stream",
        "active_connections": len(manager.active_connections),
        "buffer_size": len(manager.message_buffer),
        "supported_channels": ["pressure", "flow", "hr", "spo2"]
    }


@router.get("/ingestion/stats")
async def get_ingestion_stats():
    """
    Get telemetry ingestion statistics.
    Implements SRS NFR-P1 — telemetry ingestion throughput monitoring.
    """
    from api.middleware.response_time import get_metrics
    snapshot = get_metrics().snapshot()
    return {
        "active_connections": len(manager.active_connections),
        "buffer_size": len(manager.message_buffer),
        "ingestion_rate_pps": snapshot["throughput"]["ingestion_rate_pps"],
        "ws_relay_latency_ms": snapshot["websocket"]["relay_latency_ms"],
    }


@router.get("/history")
async def get_telemetry_history(
    db: Session = Depends(get_db),
    channel: Optional[str] = None,
    from_time: Optional[str] = None,
    to_time: Optional[str] = None,
    threshold: int = 1000,
    current_user=Depends(require_scope("telemetry_read"))
):
    """
    Retrieve historical telemetry with LTTB downsampling.
    Implements SRS FR-3.1.2 — 60 fps at 100k pts/s via LTTB downsampling.

    Args:
        channel: Optional channel filter (pressure, flow, hr, spo2).
        from_time: ISO timestamp filter (inclusive).
        to_time: ISO timestamp filter (inclusive).
        threshold: Maximum number of points to return per channel (default 1000).

    Returns:
        Dict with 'channels' mapping channel name to downsampled time-series.
    """
    from engine.lttb import downsample_telemetry
    from sqlalchemy import func

    query = db.query(Observation).filter(Observation.observation_code.isnot(None))

    if channel:
        query = query.filter(Observation.observation_code.ilike(f"%{channel}%"))
    if from_time:
        query = query.filter(Observation.timestamp >= from_time)
    if to_time:
        query = query.filter(Observation.timestamp <= to_time)

    # Limit to a reasonable window to avoid loading millions of rows
    # (LTTB handles the downsampling; we cap the DB query for memory safety)
    query = query.order_by(Observation.timestamp.desc()).limit(threshold * 10)

    observations = query.all()

    # Group by channel code
    channels_data: dict = {}
    for obs in observations:
        code = obs.observation_code or "unknown"
        if code not in channels_data:
            channels_data[code] = []
        channels_data[code].append({
            "timestamp": obs.timestamp.isoformat() if obs.timestamp else None,
            "value": obs.value_quantity.get("value") if obs.value_quantity else None,
            "unit": obs.unit,
            "observation_uid": obs.observation_uid,
        })

    # Apply LTTB downsampling per channel
    downsampled = {}
    for ch_name, points in channels_data.items():
        if len(points) <= threshold:
            downsampled[ch_name] = points
        else:
            downsampled[ch_name] = downsample_telemetry(points, threshold)

    return {
        "channels": downsampled,
        "total_points": sum(len(v) for v in downsampled.values()),
        "downsampled_to": threshold,
    }

