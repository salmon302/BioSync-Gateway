"""
BioSync-Gateway FastAPI Main Application
Implements SRS §3.0 - Middleware Tier
"""

from fastapi import FastAPI, Depends, HTTPException, status, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import time
from typing import Callable

from api.auth import get_current_user, User
from api.routes import health, audit, telemetry, plates, fhir, simulations, auth, admin
from engine import init_engines

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class PerformanceMiddleware(BaseHTTPMiddleware):
    """
    Middleware for performance instrumentation.
    Tracks response time for all requests.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()
        
        response = await call_next(request)
        
        end_time = time.perf_counter()
        response_time_ms = (end_time - start_time) * 1000
        
        # Add response time header
        response.headers["X-Response-Time-ms"] = f"{response_time_ms:.2f}"
        
        # Log slow requests (>100ms)
        if response_time_ms > 100:
            logger.warning(
                f"Slow request: {request.method} {request.url.path} "
                f"took {response_time_ms:.2f}ms"
            )
        
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    import asyncio
    
    # Startup
    logger.info("Starting BioSync-Gateway middleware...")
    try:
        init_engines()
        logger.info("Algorithmic engines initialized")
    except Exception as e:
        logger.error(f"Failed to initialize engines: {e}")
        raise
    
    # Start telemetry broadcast task
    from api.routes.telemetry import manager as telemetry_manager
    app.state.telemetry_task = asyncio.create_task(_telemetry_broadcast_task(telemetry_manager))
    logger.info("Telemetry broadcast task started")
    
    yield
    
    # Shutdown
    logger.info("Shutting down BioSync-Gateway middleware...")
    # Cancel telemetry task
    if hasattr(app.state, 'telemetry_task'):
        app.state.telemetry_task.cancel()
        try:
            await app.state.telemetry_task
        except asyncio.CancelledError:
            pass
        logger.info("Telemetry broadcast task stopped")


async def _telemetry_broadcast_task(manager):
    """Background task that generates and broadcasts telemetry data."""
    from api.routes.telemetry_generator import TelemetryGenerator
    import asyncio
    from datetime import datetime
    
    gen = TelemetryGenerator()
    logger.info("Telemetry generator started")
    
    while True:
        try:
            data = gen.generate_timestep(dt=0.1)
            message = {
                "type": "telemetry",
                "payload": data,
                "timestamp": datetime.utcnow().isoformat()
            }
            await manager.broadcast(message)
            await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            logger.info("Telemetry broadcast task cancelled")
            break
        except Exception as e:
            logger.error(f"Telemetry broadcast error: {e}")
            await asyncio.sleep(1)


# Create FastAPI application
app = FastAPI(
    title="BioSync-Gateway",
    description="Medical telemetry and laboratory informatics middleware",
    version="1.0.0",
    lifespan=lifespan
)

# Add performance middleware for response time tracking
app.add_middleware(PerformanceMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",
        "http://localhost:8080"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(audit.router, prefix="/api/audit", tags=["audit"])
app.include_router(telemetry.router, prefix="/api/telemetry", tags=["telemetry"])
app.include_router(plates.router, prefix="/api/plates", tags=["plates"])
app.include_router(fhir.router, prefix="/api/fhir", tags=["fhir"])
app.include_router(simulations.router, prefix="/api/simulations", tags=["simulations"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])


@app.get("/")
async def root():
    """Root endpoint - API information"""
    return {
        "service": "BioSync-Gateway",
        "version": "1.0.0",
        "status": "operational",
        "documentation": "/docs",
        "openapi": "/openapi.json"
    }


@app.get("/api/protected")
async def protected_endpoint(current_user: User = Depends(get_current_user)):
    """Example protected endpoint requiring JWT authentication"""
    return {
        "message": "Access granted",
        "user": current_user.username,
        "role": current_user.role,
        "scopes": current_user.scopes
    }


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "detail": str(exc) if app.debug else "An unexpected error occurred"
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
