# SPDX-License-Identifier: MIT
"""
Human Factors Metrics Routes
Implements SRS FR-3.9.1 — Passive human-factors metrics collection
Implements SRS FR-3.9.2 — uFMEA JSON export

Endpoints:
  GET  /api/human-factors/export   (scope: human_factors_read)
  POST /api/human-factors/events   (scope: human_factors_write)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text, func
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from api.auth import get_current_user, require_scope
from database import get_db
from models import HumanFactorsMetric

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic schemas for request/response
# ---------------------------------------------------------------------------

class HumanFactorsEventIn(BaseModel):
    """Single human-factors event ingested from the frontend."""
    session_id: str = Field(..., min_length=1, max_length=255)
    event_type: str = Field(..., min_length=1, max_length=100)
    timestamp: Optional[float] = None
    latency_ms: Optional[int] = Field(None, ge=0)
    steps_count: Optional[int] = Field(None, ge=0)
    component: Optional[str] = Field(None, max_length=100)
    metadata: Optional[Dict[str, Any]] = None


class HumanFactorsBatchIn(BaseModel):
    """Batch of human-factors events for a single POST."""
    events: List[HumanFactorsEventIn] = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# POST /api/human-factors/events — ingest frontend events
# ---------------------------------------------------------------------------

@router.post("/events", status_code=status.HTTP_201_CREATED)
async def ingest_events(
    payload: HumanFactorsBatchIn,
    db: Session = Depends(get_db),
    current_user=Depends(require_scope("human_factors_write")),
):
    """
    Ingest a batch of human-factors events from the frontend.

    Events are written to the ``human_factors_metrics`` table (append-only,
    protected by a BEFORE UPDATE/DELETE trigger per SRS FR-3.8.1).

    Requires ``human_factors_write`` scope.
    """
    try:
        rows = []
        for ev in payload.events:
            row = HumanFactorsMetric(
                session_id=ev.session_id,
                event_type=ev.event_type,
                event_timestamp=(
                    datetime.utcfromtimestamp(ev.timestamp / 1000.0)
                    if ev.timestamp
                    else datetime.utcnow()
                ),
                latency_ms=ev.latency_ms,
                steps_count=ev.steps_count,
                component=ev.component,
                meta=ev.metadata,
            )
            db.add(row)
            rows.append(row)

        db.commit()
        logger.info(
            "Ingested %d human-factors events for session(s): %s",
            len(rows),
            ", ".join({r.session_id for r in rows}),
        )
        return {
            "status": "accepted",
            "count": len(rows),
            "inserted_ids": [r.id for r in rows],
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to ingest human-factors events: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to ingest human-factors events",
        )


# ---------------------------------------------------------------------------
# GET /api/human-factors/export — uFMEA JSON export
# ---------------------------------------------------------------------------

@router.get("/export")
async def export_ufmea(
    session_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(require_scope("human_factors_read")),
):
    """
    Export aggregated human-factors metrics as structured uFMEA JSON.

    Produces a comprehensive summary suitable for uFMEA (user Failure Mode
    and Effects Analysis) ingestion, including:

    - **sessions**: per-session event counts and time span
    - **event_type_counts**: total count per event type
    - **latency_stats**: percentile statistics (P50, P90, P95, P99) for
      events with ``latency_ms`` populated
    - **steps_stats**: min, max, mean, median for events with
      ``steps_count`` populated
    - **component_breakdown**: per-component event counts and latency averages

    Requires ``human_factors_read`` scope.

    Query parameters:
    - ``session_id`` (optional): filter export to a single session
    """
    try:
        # --- Sessions summary ---
        sessions_query = text("""
            SELECT
                session_id,
                COUNT(*) AS event_count,
                MIN(event_timestamp) AS first_event,
                MAX(event_timestamp) AS last_event
            FROM human_factors_metrics
            WHERE 1=1
            GROUP BY session_id
            ORDER BY session_id
        """)
        params: Dict[str, Any] = {}
        if session_id:
            sessions_query = text("""
                SELECT
                    session_id,
                    COUNT(*) AS event_count,
                    MIN(event_timestamp) AS first_event,
                    MAX(event_timestamp) AS last_event
                FROM human_factors_metrics
                WHERE session_id = :session_id
                GROUP BY session_id
                ORDER BY session_id
            """)
            params["session_id"] = session_id

        sessions_result = db.execute(sessions_query, params)
        sessions = []
        for row in sessions_result:
            sessions.append({
                "session_id": row.session_id,
                "event_count": row.event_count,
                "first_event": row.first_event.isoformat() if row.first_event else None,
                "last_event": row.last_event.isoformat() if row.last_event else None,
            })

        # --- Event-type counts ---
        et_query = text("""
            SELECT event_type, COUNT(*) AS count
            FROM human_factors_metrics
            WHERE 1=1
            GROUP BY event_type
            ORDER BY count DESC
        """)
        if session_id:
            et_query = text("""
                SELECT event_type, COUNT(*) AS count
                FROM human_factors_metrics
                WHERE session_id = :session_id
                GROUP BY event_type
                ORDER BY count DESC
            """)
        et_result = db.execute(et_query, params)
        event_type_counts = [
            {"event_type": row.event_type, "count": row.count}
            for row in et_result
        ]

        # --- Latency percentile stats ---
        latency_query = text("""
            SELECT
                COUNT(latency_ms) AS total,
                MIN(latency_ms) AS min_latency,
                MAX(latency_ms) AS max_latency,
                AVG(latency_ms) AS mean_latency,
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY latency_ms) AS p50,
                PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY latency_ms) AS p90,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95,
                PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY latency_ms) AS p99
            FROM human_factors_metrics
            WHERE latency_ms IS NOT NULL
        """)
        if session_id:
            latency_query = text("""
                SELECT
                    COUNT(latency_ms) AS total,
                    MIN(latency_ms) AS min_latency,
                    MAX(latency_ms) AS max_latency,
                    AVG(latency_ms) AS mean_latency,
                    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY latency_ms) AS p50,
                    PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY latency_ms) AS p90,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95,
                    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY latency_ms) AS p99
                FROM human_factors_metrics
                WHERE latency_ms IS NOT NULL
                  AND session_id = :session_id
            """)
        lat_result = db.execute(latency_query, params).first()
        latency_stats = {
            "total_events": lat_result.total if lat_result and lat_result.total else 0,
            "min_ms": float(lat_result.min_latency) if lat_result and lat_result.min_latency else None,
            "max_ms": float(lat_result.max_latency) if lat_result and lat_result.max_latency else None,
            "mean_ms": float(lat_result.mean_latency) if lat_result and lat_result.mean_latency else None,
            "p50_ms": float(lat_result.p50) if lat_result and lat_result.p50 else None,
            "p90_ms": float(lat_result.p90) if lat_result and lat_result.p90 else None,
            "p95_ms": float(lat_result.p95) if lat_result and lat_result.p95 else None,
            "p99_ms": float(lat_result.p99) if lat_result and lat_result.p99 else None,
        }

        # --- Steps stats ---
        steps_query = text("""
            SELECT
                COUNT(steps_count) AS total,
                MIN(steps_count) AS min_steps,
                MAX(steps_count) AS max_steps,
                AVG(steps_count) AS mean_steps,
                PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY steps_count) AS median_steps
            FROM human_factors_metrics
            WHERE steps_count IS NOT NULL
        """)
        if session_id:
            steps_query = text("""
                SELECT
                    COUNT(steps_count) AS total,
                    MIN(steps_count) AS min_steps,
                    MAX(steps_count) AS max_steps,
                    AVG(steps_count) AS mean_steps,
                    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY steps_count) AS median_steps
                FROM human_factors_metrics
                WHERE steps_count IS NOT NULL
                  AND session_id = :session_id
            """)
        steps_result = db.execute(steps_query, params).first()
        steps_stats = {
            "total_events": steps_result.total if steps_result and steps_result.total else 0,
            "min_steps": steps_result.min_steps if steps_result and steps_result.min_steps else None,
            "max_steps": steps_result.max_steps if steps_result and steps_result.max_steps else None,
            "mean_steps": float(steps_result.mean_steps) if steps_result and steps_result.mean_steps else None,
            "median_steps": steps_result.median_steps if steps_result and steps_result.median_steps else None,
        }

        # --- Per-component breakdown ---
        component_query = text("""
            SELECT
                component,
                COUNT(*) AS event_count,
                AVG(latency_ms) AS avg_latency_ms,
                AVG(steps_count) AS avg_steps
            FROM human_factors_metrics
            WHERE component IS NOT NULL
            GROUP BY component
            ORDER BY event_count DESC
        """)
        if session_id:
            component_query = text("""
                SELECT
                    component,
                    COUNT(*) AS event_count,
                    AVG(latency_ms) AS avg_latency_ms,
                    AVG(steps_count) AS avg_steps
                FROM human_factors_metrics
                WHERE component IS NOT NULL
                  AND session_id = :session_id
                GROUP BY component
                ORDER BY event_count DESC
            """)
        comp_result = db.execute(component_query, params)
        component_breakdown = [
            {
                "component": row.component,
                "event_count": row.event_count,
                "avg_latency_ms": float(row.avg_latency_ms) if row.avg_latency_ms else None,
                "avg_steps": float(row.avg_steps) if row.avg_steps else None,
            }
            for row in comp_result
        ]

        # --- Total event count ---
        total_query = text("""
            SELECT COUNT(*) AS total
            FROM human_factors_metrics
            WHERE 1=1
        """)
        if session_id:
            total_query = text("""
                SELECT COUNT(*) AS total
                FROM human_factors_metrics
                WHERE session_id = :session_id
            """)
        total_count = db.execute(total_query, params).scalar()

        export = {
            "export_timestamp": datetime.utcnow().isoformat() + "Z",
            "scope": "human_factors_read",
            "user": current_user.username,
            "total_events": total_count,
            "sessions": sessions,
            "event_type_counts": event_type_counts,
            "latency_stats": latency_stats,
            "steps_stats": steps_stats,
            "component_breakdown": component_breakdown,
        }

        logger.info(
            "uFMEA export generated: %d total events, %d sessions, %d components",
            total_count,
            len(sessions),
            len(component_breakdown),
        )
        return export

    except Exception as e:
        logger.error(f"Failed to generate uFMEA export: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate uFMEA export",
        )
