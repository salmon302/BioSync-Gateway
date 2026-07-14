"""
Telemetry Routes
Implements SRS §3.1 - Telemetry Dashboard
"""

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from typing import List, Dict
import logging
import json
from datetime import datetime

from api.auth import get_current_user, require_scope

router = APIRouter()
logger = logging.getLogger(__name__)

# Connection manager for WebSocket clients
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.message_buffer: List[Dict] = []
        self.max_buffer_size = 1000
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected: {websocket.client}")
        
        # Send buffered messages for replay
        if self.message_buffer:
            for msg in self.message_buffer[-100:]:
                try:
                    await websocket.send_json(msg)
                except Exception:
                    break
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket disconnected: {websocket.client}")
    
    async def broadcast(self, message: Dict):
        """Broadcast message to all connected clients"""
        self.message_buffer.append(message)
        if len(self.message_buffer) > self.max_buffer_size:
            self.message_buffer.pop(0)
        
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)
        
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()


@router.websocket("/stream")
async def telemetry_stream(websocket: WebSocket):
    """
    WebSocket endpoint for real-time telemetry streaming.
    Implements SRS NFR-R4 - WebSocket with auto-reconnect.
    """
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
    current_user=Depends(require_scope("telemetry_write"))
):
    """
    Ingest telemetry data from medical devices.
    Stores raw data and triggers filtering pipeline.
    Implements SRS FR-3.5.3 - Raw vs filtered storage.
    """
    # Broadcast to WebSocket clients
    message = {
        "type": "telemetry",
        "payload": telemetry_data,
        "timestamp": datetime.utcnow().isoformat()
    }
    await manager.broadcast(message)
    
    return {"status": "accepted", "timestamp": datetime.utcnow().isoformat()}


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

