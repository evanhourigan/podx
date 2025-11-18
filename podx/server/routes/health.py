"""Health check endpoints for monitoring and status."""

import platform
from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    timestamp: str
    version: str
    python_version: str
    platform: str


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint.

    Returns basic server health and version information.

    Returns:
        Health status information
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
        version="3.0.0",
        python_version=platform.python_version(),
        platform=platform.system(),
    )


@router.get("/", response_model=HealthResponse)
async def root() -> HealthResponse:
    """Root endpoint - alias for health check.

    Returns:
        Health status information
    """
    return await health_check()
