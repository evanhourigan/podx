"""Health check endpoints for monitoring and status."""

import platform
from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from podx.server.database import get_session

router = APIRouter()

# Server start time for uptime calculation
_SERVER_START_TIME: datetime | None = None


def set_server_start_time() -> None:
    """Set the server start time. Called during app startup."""
    global _SERVER_START_TIME
    if _SERVER_START_TIME is None:
        _SERVER_START_TIME = datetime.now(timezone.utc)


def get_uptime_seconds() -> float:
    """Get server uptime in seconds.

    Returns:
        Uptime in seconds, or 0 if server start time not set
    """
    if _SERVER_START_TIME is None:
        return 0.0
    return (datetime.now(timezone.utc) - _SERVER_START_TIME).total_seconds()


class BasicHealthResponse(BaseModel):
    """Basic health check response model."""

    status: str
    timestamp: str


class DetailedHealthResponse(BaseModel):
    """Detailed health check response model."""

    status: str
    timestamp: str
    version: str
    uptime_seconds: float
    python_version: str
    platform: str
    database: str


class ReadinessResponse(BaseModel):
    """Readiness probe response model."""

    status: str
    timestamp: str
    checks: Dict[str, Any]


@router.get("/health/live", response_model=BasicHealthResponse)
async def liveness_probe() -> BasicHealthResponse:
    """Liveness probe endpoint.

    Returns basic server health. This endpoint should always return 200
    if the server is running, even if dependent services are down.

    Returns:
        Basic health status
    """
    return BasicHealthResponse(
        status="alive",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness_probe(session: AsyncSession = Depends(get_session)) -> ReadinessResponse:
    """Readiness probe endpoint.

    Checks if the server is ready to accept traffic by verifying
    that dependent services (database) are available.

    Args:
        session: Database session

    Returns:
        Readiness status with dependency checks
    """
    checks: Dict[str, Any] = {}
    overall_status = "ready"

    # Check database connection
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = {"status": "connected", "error": None}
    except Exception as e:
        checks["database"] = {"status": "disconnected", "error": str(e)}
        overall_status = "not_ready"

    return ReadinessResponse(
        status=overall_status,
        timestamp=datetime.now(timezone.utc).isoformat(),
        checks=checks,
    )


@router.get("/health", response_model=DetailedHealthResponse)
async def health_check(session: AsyncSession = Depends(get_session)) -> DetailedHealthResponse:
    """Detailed health check endpoint.

    Returns comprehensive server health and version information,
    including uptime and database connectivity.

    Args:
        session: Database session

    Returns:
        Detailed health status information
    """
    # Check database
    db_status = "connected"
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        db_status = "disconnected"

    return DetailedHealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        timestamp=datetime.now(timezone.utc).isoformat(),
        version="3.0.0",
        uptime_seconds=get_uptime_seconds(),
        python_version=platform.python_version(),
        platform=platform.system(),
        database=db_status,
    )


@router.get("/", response_model=BasicHealthResponse)
async def root() -> BasicHealthResponse:
    """Root endpoint - returns basic liveness status.

    Returns:
        Basic health status information
    """
    return await liveness_probe()
