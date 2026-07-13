"""
JWT Authentication Module
Implements SRS §3.7 - Authentication and Authorization
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

# JWT Configuration (should be loaded from environment variables)
JWT_SECRET = "your-super-secret-jwt-key-change-in-production"
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

security = HTTPBearer()


class User(BaseModel):
    """Authenticated user model"""
    username: str
    email: str
    role: str
    scopes: List[str]


class TokenData(BaseModel):
    """JWT token payload"""
    username: Optional[str] = None
    role: Optional[str] = None
    scopes: Optional[List[str]] = None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """
    Dependency to extract and validate JWT token from Authorization header.
    Returns authenticated User object or raises 401 Unauthorized.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Decode JWT token
        payload = jwt.decode(
            credentials.credentials,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM]
        )
        
        username: str = payload.get("sub")
        role: str = payload.get("role")
        scopes: List[str] = payload.get("scopes", [])
        
        if username is None:
            raise credentials_exception
            
        token_data = TokenData(
            username=username,
            role=role,
            scopes=scopes
        )
        
    except JWTError as e:
        logger.warning(f"JWT validation failed: {e}")
        raise credentials_exception
    
    # In production, you would validate against database
    # For now, return user from token
    return User(
        username=token_data.username,
        email=f"{token_data.username}@biosync.local",
        role=token_data.role or "user",
        scopes=token_data.scopes or []
    )


def create_access_token(data: dict, expires_delta: Optional[int] = None) -> str:
    """
    Create JWT access token.
    
    Args:
        data: Payload to encode in token
        expires_delta: Expiration time in hours (default: JWT_EXPIRATION_HOURS)
    
    Returns:
        Encoded JWT token string
    """
    from datetime import datetime, timedelta
    
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + timedelta(hours=expires_delta)
    else:
        expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def require_scope(required_scope: str):
    """
    Dependency factory for scope-based authorization.
    
    Usage:
        @app.get("/api/audit")
        async def read_audit(user: User = Depends(require_scope("audit_read"))):
            ...
    """
    async def scope_checker(user: User = Depends(get_current_user)) -> User:
        if required_scope not in user.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required scope: {required_scope}"
            )
        return user
    return scope_checker
