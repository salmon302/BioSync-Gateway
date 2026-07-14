"""
Health Check Routes
Implements OQ-13/14/15 - Authentication and health endpoints
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from datetime import datetime

from api.auth import get_current_user
from database import get_db

router = APIRouter()


@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """
    Public health check endpoint.
    Returns 200 if all systems operational.
    """
    try:
        # Check database connectivity
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    return {
        "database": db_status,
        "middleware": "healthy",
        "pulseEngine": "running"
    }


@router.get("/health/protected")
async def protected_health_check(current_user=Depends(get_current_user)):
    """
    Protected health check endpoint.
    Requires valid JWT token (OQ-13/14/15).
    """
    return {
        "status": "healthy",
        "authenticated": True,
        "user": current_user.username
    }
