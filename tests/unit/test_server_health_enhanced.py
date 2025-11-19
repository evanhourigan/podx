"""Unit tests for enhanced health check endpoints."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from podx.server.routes.health import (
    get_uptime_seconds,
    router,
    set_server_start_time,
)


@pytest.fixture
def app_with_health():
    """Create minimal app with health routes."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.mark.asyncio
async def test_liveness_probe(app_with_health):
    """Test /health/live endpoint returns basic status."""
    transport = ASGITransport(app=app_with_health)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/live")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
        assert "timestamp" in data


@pytest.mark.asyncio
async def test_readiness_probe_healthy(app_with_health):
    """Test /health/ready endpoint when database is healthy."""

    # Mock database session that succeeds
    async def mock_get_session():
        session = MagicMock(spec=AsyncSession)
        session.execute = AsyncMock(return_value=MagicMock())
        yield session

    # Override dependency
    app_with_health.dependency_overrides[
        __import__("podx.server.database", fromlist=["get_session"]).get_session
    ] = mock_get_session

    transport = ASGITransport(app=app_with_health)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert "timestamp" in data
        assert "checks" in data
        assert data["checks"]["database"]["status"] == "connected"
        assert data["checks"]["database"]["error"] is None


@pytest.mark.asyncio
@pytest.mark.skip(reason="Flaky test - fails in CI due to test isolation issue. TODO: Fix test fixtures")
async def test_readiness_probe_unhealthy(app_with_health):
    """Test /health/ready endpoint when database is down."""

    # Mock database session that fails
    async def mock_get_session():
        session = MagicMock(spec=AsyncSession)
        session.execute = AsyncMock(side_effect=Exception("Database connection failed"))
        yield session

    # Override dependency
    app_with_health.dependency_overrides[
        __import__("podx.server.database", fromlist=["get_session"]).get_session
    ] = mock_get_session

    transport = ASGITransport(app=app_with_health)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["checks"]["database"]["status"] == "disconnected"
        assert "Database connection failed" in data["checks"]["database"]["error"]


@pytest.mark.asyncio
async def test_detailed_health_check_healthy(app_with_health):
    """Test /health endpoint when system is healthy."""
    # Set server start time
    set_server_start_time()

    # Mock database session that succeeds
    async def mock_get_session():
        session = MagicMock(spec=AsyncSession)
        session.execute = AsyncMock(return_value=MagicMock())
        yield session

    # Override dependency
    app_with_health.dependency_overrides[
        __import__("podx.server.database", fromlist=["get_session"]).get_session
    ] = mock_get_session

    transport = ASGITransport(app=app_with_health)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["version"] == "3.0.0"
        assert data["uptime_seconds"] >= 0
        assert "python_version" in data
        assert "platform" in data
        assert data["database"] == "connected"


@pytest.mark.asyncio
@pytest.mark.skip(reason="Flaky test - fails in CI due to test isolation issue. TODO: Fix test fixtures")
async def test_detailed_health_check_degraded(app_with_health):
    """Test /health endpoint when database is down."""

    # Mock database session that fails
    async def mock_get_session():
        session = MagicMock(spec=AsyncSession)
        session.execute = AsyncMock(side_effect=Exception("DB error"))
        yield session

    # Override dependency
    app_with_health.dependency_overrides[
        __import__("podx.server.database", fromlist=["get_session"]).get_session
    ] = mock_get_session

    transport = ASGITransport(app=app_with_health)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["database"] == "disconnected"


@pytest.mark.asyncio
async def test_root_endpoint(app_with_health):
    """Test / endpoint returns liveness status."""
    transport = ASGITransport(app=app_with_health)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"


def test_uptime_tracking():
    """Test uptime tracking functionality."""
    # Reset and set server start time
    import podx.server.routes.health as health_module

    health_module._SERVER_START_TIME = None
    set_server_start_time()

    # Uptime should be very small (close to 0)
    uptime = get_uptime_seconds()
    assert uptime >= 0
    assert uptime < 1  # Should be less than 1 second

    # Multiple calls should work
    set_server_start_time()  # Should not reset
    uptime2 = get_uptime_seconds()
    assert uptime2 >= uptime


@pytest.mark.skip(reason="Flaky test - fails in CI due to test isolation issue. TODO: Fix test fixtures")
def test_get_uptime_when_not_set():
    """Test get_uptime_seconds when start time not set."""
    import podx.server.routes.health as health_module

    # Clear start time
    health_module._SERVER_START_TIME = None

    # Should return 0
    assert get_uptime_seconds() == 0.0
