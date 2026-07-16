# SPDX-License-Identifier: MIT
"""
JWT Authentication Routes
Implements SRS §3.7 - Authentication and Authorization
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
import logging

from api.auth import (
    get_current_user,
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
    User,
    JWT_EXPIRATION_HOURS,
)

router = APIRouter()
logger = logging.getLogger(__name__)


class TokenRequest(BaseModel):
    """Login request body"""
    username: str
    password: str


class TokenResponse(BaseModel):
    """Token response body"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    """Refresh token request body"""
    refresh_token: str


@router.post("/login", response_model=TokenResponse)
async def login(token_request: TokenRequest):
    """
    Authenticate user and return access + refresh tokens.
    Implements SRS NFR-S3 - JWT ≤1 hour lifetime with refresh tokens.
    """
    # TODO: Validate credentials against database
    # For development, accept any non-empty credentials
    if not token_request.username or not token_request.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # In production, hash password and verify against DB
    # For now, create token with user scopes based on username
    scopes = ["read", "write"]
    if token_request.username == "admin":
        scopes.extend(["admin", "audit_read", "audit_write"])

    access_token = create_access_token(
        data={"sub": token_request.username, "role": "admin", "scopes": scopes},
        expires_delta=JWT_EXPIRATION_HOURS,
    )
    refresh_token = create_refresh_token(
        data={"sub": token_request.username, "role": "admin", "scopes": scopes}
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=JWT_EXPIRATION_HOURS * 3600,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshRequest):
    """
    Exchange a valid refresh token for a new access token + new refresh token.
    Implements SRS NFR-S3 - Refresh token rotation.
    """
    user = verify_refresh_token(request.refresh_token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Rotate refresh token — issue new one each time
    new_access = create_access_token(
        data={"sub": user.username, "role": user.role, "scopes": user.scopes},
        expires_delta=JWT_EXPIRATION_HOURS,
    )
    new_refresh = create_refresh_token(
        data={"sub": user.username, "role": user.role, "scopes": user.scopes}
    )

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        token_type="bearer",
        expires_in=JWT_EXPIRATION_HOURS * 3600,
    )
