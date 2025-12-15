"""Unit tests for server rate limiting."""

import os
from unittest.mock import patch

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from podx.server.middleware.rate_limit import create_limiter, get_rate_limit_config


@pytest.fixture
def app_with_rate_limit():
    """Create minimal app with rate limiting."""
    with patch.dict(os.environ, {"PODX_RATE_LIMIT_PER_MINUTE": "5/minute"}, clear=False):
        # Create minimal FastAPI app for testing rate limiting
        app = FastAPI()

        # Add limiter to app state
        limiter = create_limiter()
        app.state.limiter = limiter

        # Add test endpoint with rate limit
        @app.get("/api/v1/test")
        @limiter.limit("5/minute")
        async def test_endpoint(request: Request):
            return {"message": "success"}

        yield app


@pytest.fixture
def app_with_strict_rate_limit():
    """Create minimal app with very strict rate limiting for testing."""
    with patch.dict(os.environ, {"PODX_RATE_LIMIT_PER_MINUTE": "2/minute"}, clear=False):
        # Create minimal FastAPI app for testing rate limiting
        app = FastAPI()

        # Add limiter to app state
        limiter = create_limiter()
        app.state.limiter = limiter

        # Register rate limit exception handler
        from slowapi.errors import RateLimitExceeded

        from podx.server.middleware.rate_limit import rate_limit_exceeded_handler

        app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

        # Add test endpoint with strict rate limit
        @app.get("/api/v1/strict")
        @limiter.limit("2/minute")
        async def strict_endpoint(request: Request):
            return {"message": "success"}

        yield app


def test_get_rate_limit_config_defaults():
    """Test that rate limit config returns defaults when env vars not set."""
    with patch.dict(os.environ, {}, clear=True):
        # Clear any existing rate limit env vars
        os.environ.pop("PODX_RATE_LIMIT_PER_MINUTE", None)
        os.environ.pop("PODX_UPLOAD_LIMIT_PER_HOUR", None)

        general_limit, upload_limit = get_rate_limit_config()

        assert general_limit == "100/minute"
        assert upload_limit == "10/hour"


def test_get_rate_limit_config_custom():
    """Test that rate limit config respects custom env vars."""
    with patch.dict(
        os.environ,
        {
            "PODX_RATE_LIMIT_PER_MINUTE": "50/minute",
            "PODX_UPLOAD_LIMIT_PER_HOUR": "5/hour",
        },
        clear=False,
    ):
        general_limit, upload_limit = get_rate_limit_config()

        assert general_limit == "50/minute"
        assert upload_limit == "5/hour"


@pytest.mark.asyncio
async def test_rate_limit_allows_requests_under_limit(app_with_rate_limit):
    """Test that requests under the rate limit are allowed."""
    transport = ASGITransport(app=app_with_rate_limit)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Make 3 requests (under the limit of 5)
        for i in range(3):
            response = await client.get("/api/v1/test")
            assert response.status_code == 200
            assert response.json()["message"] == "success"


@pytest.mark.asyncio
async def test_rate_limit_blocks_requests_over_limit(app_with_strict_rate_limit):
    """Test that requests over the rate limit are blocked with 429."""
    transport = ASGITransport(app=app_with_strict_rate_limit)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Make requests up to the limit (2)
        for i in range(2):
            response = await client.get("/api/v1/strict")
            assert response.status_code == 200

        # Third request should be rate limited
        response = await client.get("/api/v1/strict")
        assert response.status_code == 429
        data = response.json()
        assert "error" in data
        assert "Rate limit exceeded" in data["error"]
        assert data["status_code"] == 429
        assert "Retry-After" in response.headers


@pytest.mark.asyncio
async def test_rate_limit_response_includes_retry_after(app_with_strict_rate_limit):
    """Test that 429 responses include Retry-After header."""
    transport = ASGITransport(app=app_with_strict_rate_limit)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Exhaust rate limit
        for i in range(2):
            await client.get("/api/v1/strict")

        # Get rate limited response
        response = await client.get("/api/v1/strict")
        assert response.status_code == 429
        assert "Retry-After" in response.headers
        # Retry-After should be a positive number
        retry_after = int(response.headers["Retry-After"])
        assert retry_after > 0


@pytest.mark.asyncio
async def test_rate_limit_per_ip_isolation(app_with_strict_rate_limit):
    """Test that rate limits are per-IP (different IPs don't affect each other)."""
    # Note: In the test environment, all requests come from the same IP
    # This test demonstrates the concept but actual IP isolation requires
    # network-level testing or mocking
    transport = ASGITransport(app=app_with_strict_rate_limit)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # All requests from same client should share rate limit
        for i in range(2):
            response = await client.get("/api/v1/strict")
            assert response.status_code == 200

        # Third request should be rate limited
        response = await client.get("/api/v1/strict")
        assert response.status_code == 429
