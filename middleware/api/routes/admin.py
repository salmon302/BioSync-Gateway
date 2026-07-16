# SPDX-License-Identifier: MIT
"""
Admin API Routes
Implements SRS §3.6/3.5/3.7 - Admin Console backend endpoints

Provides endpoints for:
- JWT key rotation
- EMA parameter tuning
- Pulse Engine controls
- System configuration
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
import logging
import os
import secrets

from api.auth import get_current_user, require_scope, User

router = APIRouter()
logger = logging.getLogger(__name__)


class EMAConfig(BaseModel):
    """EMA parameter configuration"""
    pressure_alpha: float = 0.2
    flow_alpha: float = 0.1
    hr_alpha: float = 0.3
    spo2_alpha: float = 0.4


class JWTRotationResponse(BaseModel):
    """JWT rotation response"""
    message: str
    new_secret_set: bool
    warning: Optional[str] = None


class PulseRestartResponse(BaseModel):
    """Pulse restart response"""
    message: str
    status: str


@router.post("/jwt/rotate", response_model=JWTRotationResponse)
async def rotate_jwt_key(
    current_user: User = Depends(require_scope("admin"))
):
    """
    Rotate JWT signing secret.
    WARNING: This invalidates all existing tokens.
    Implements SRS NFR-S3 - Session controls.
    """
    new_secret = secrets.token_hex(32)
    env_path = os.getenv("JWT_SECRET_FILE")

    if env_path:
        try:
            with open(env_path, "w") as f:
                f.write(new_secret)
            return JWTRotationResponse(
                message="JWT secret rotated and written to file",
                new_secret_set=True,
            )
        except OSError as e:
            logger.error(f"Failed to write JWT secret file: {e}")
            return JWTRotationResponse(
                message="JWT secret generated but could not persist to file",
                new_secret_set=False,
                warning="Secret was generated but not persisted. Manual restart required.",
            )
    else:
        return JWTRotationResponse(
            message="JWT secret rotation simulated (no JWT_SECRET_FILE configured)",
            new_secret_set=False,
            warning="Set JWT_SECRET_FILE env var to enable file-based rotation.",
        )


@router.put("/signal/ema", response_model=dict)
async def update_ema_config(
    config: EMAConfig,
    current_user: User = Depends(require_scope("admin"))
):
    """
    Update EMA smoothing factors per channel.
    Implements SRS FR-3.5.2 - Per-channel α configuration.
    """
    # In production, persist to database or config file
    # For now, return the accepted configuration
    return {
        "message": "EMA configuration updated",
        "config": config.dict(),
    }


@router.post("/pulse/restart", response_model=PulseRestartResponse)
async def restart_pulse_engine(
    current_user: User = Depends(require_scope("admin"))
):
    """
    Restart the Pulse Engine simulation worker pool.
    Implements SRS FR-3.6.2 - Simulation lifecycle control.
    """
    # TODO: Actually restart Pulse Engine workers
    # For now, return simulated response
    return PulseRestartResponse(
        message="Pulse Engine restart initiated",
        status="restarting",
    )


@router.get("/system/info", response_model=dict)
async def get_system_info(
    current_user: User = Depends(require_scope("admin"))
):
    """
    Get system configuration and health information.
    """
    return {
        "environment": os.getenv("ENVIRONMENT", "development"),
        "jwt_expiration_hours": 1,
        "jwt_refresh_expiration_days": 7,
        "telemetry_mode": os.getenv("TELEMETRY_MODE", "synthetic"),
        "max_concurrent_simulations": 10,
    }
