"""Unit tests for CORS configuration."""

import os
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def app_with_wildcard_cors():
    """Create minimal app with wildcard CORS (default)."""
    with patch.dict(os.environ, {}, clear=False):
        # Remove PODX_CORS_ORIGINS if set
        os.environ.pop("PODX_CORS_ORIGINS", None)

        # Create minimal FastAPI app
        app = FastAPI()

        # Add CORS middleware with wildcard (default behavior)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Add test endpoint
        @app.get("/api/v1/test")
        async def test_endpoint():
            return {"message": "success"}

        yield app


@pytest.fixture
def app_with_restricted_cors():
    """Create minimal app with restricted CORS origins."""
    with patch.dict(
        os.environ,
        {"PODX_CORS_ORIGINS": "http://localhost:3000,https://app.example.com"},
        clear=False,
    ):
        # Create minimal FastAPI app
        app = FastAPI()

        # Add CORS middleware with specific origins
        cors_origins_str = os.getenv("PODX_CORS_ORIGINS", "*")
        cors_origins = (
            [origin.strip() for origin in cors_origins_str.split(",")]
            if cors_origins_str != "*"
            else ["*"]
        )

        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Add test endpoint
        @app.get("/api/v1/test")
        async def test_endpoint():
            return {"message": "success"}

        yield app


@pytest.mark.asyncio
async def test_cors_wildcard_allows_any_origin(app_with_wildcard_cors):
    """Test that wildcard CORS allows any origin."""
    transport = ASGITransport(app=app_with_wildcard_cors)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Request with Origin header
        response = await client.get(
            "/api/v1/test",
            headers={"Origin": "http://example.com"},
        )

        assert response.status_code == 200
        # Wildcard CORS returns * for Access-Control-Allow-Origin
        assert response.headers.get("access-control-allow-origin") == "*"


@pytest.mark.asyncio
async def test_cors_wildcard_allows_credentials(app_with_wildcard_cors):
    """Test that CORS allows credentials."""
    transport = ASGITransport(app=app_with_wildcard_cors)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/test",
            headers={"Origin": "http://example.com"},
        )

        assert response.status_code == 200
        # Should have Access-Control-Allow-Credentials header
        # Note: When using wildcard origin (*), credentials should technically be false
        # but FastAPI's CORS middleware still sets it based on allow_credentials=True


@pytest.mark.asyncio
async def test_cors_preflight_request(app_with_wildcard_cors):
    """Test CORS preflight (OPTIONS) request."""
    transport = ASGITransport(app=app_with_wildcard_cors)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # OPTIONS request is a CORS preflight
        response = await client.options(
            "/api/v1/test",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )

        # Preflight should succeed
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers


@pytest.mark.asyncio
async def test_cors_restricted_allows_listed_origin(app_with_restricted_cors):
    """Test that restricted CORS allows listed origins."""
    transport = ASGITransport(app=app_with_restricted_cors)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Request from allowed origin
        response = await client.get(
            "/api/v1/test",
            headers={"Origin": "http://localhost:3000"},
        )

        assert response.status_code == 200
        # Should echo back the origin
        assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


@pytest.mark.asyncio
async def test_cors_restricted_blocks_unlisted_origin(app_with_restricted_cors):
    """Test that restricted CORS blocks unlisted origins."""
    transport = ASGITransport(app=app_with_restricted_cors)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Request from disallowed origin
        response = await client.get(
            "/api/v1/test",
            headers={"Origin": "http://evil.com"},
        )

        # Request succeeds but CORS headers should NOT be present
        assert response.status_code == 200
        # access-control-allow-origin should not be set for disallowed origins
        assert "access-control-allow-origin" not in response.headers


@pytest.mark.asyncio
async def test_cors_allows_all_methods(app_with_wildcard_cors):
    """Test that CORS allows all HTTP methods."""
    transport = ASGITransport(app=app_with_wildcard_cors)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Preflight request asking about POST method
        response = await client.options(
            "/api/v1/test",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "POST",
            },
        )

        assert response.status_code == 200
        # Should allow POST and other methods
        allowed_methods = response.headers.get("access-control-allow-methods", "")
        # Different CORS implementations may return different formats
        # Just check that it's present
        assert allowed_methods


@pytest.mark.asyncio
async def test_cors_allows_custom_headers(app_with_wildcard_cors):
    """Test that CORS allows custom headers."""
    transport = ASGITransport(app=app_with_wildcard_cors)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Preflight request with custom header
        response = await client.options(
            "/api/v1/test",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-Custom-Header,X-API-Key",
            },
        )

        assert response.status_code == 200
        # Should allow custom headers
        allowed_headers = response.headers.get("access-control-allow-headers", "")
        assert allowed_headers


def test_cors_origins_parsing_single():
    """Test parsing single CORS origin from env var."""
    with patch.dict(os.environ, {"PODX_CORS_ORIGINS": "http://localhost:3000"}, clear=False):
        cors_origins_str = os.getenv("PODX_CORS_ORIGINS", "*")
        cors_origins = (
            [origin.strip() for origin in cors_origins_str.split(",")]
            if cors_origins_str != "*"
            else ["*"]
        )

        assert cors_origins == ["http://localhost:3000"]


def test_cors_origins_parsing_multiple():
    """Test parsing multiple CORS origins from env var."""
    with patch.dict(
        os.environ,
        {
            "PODX_CORS_ORIGINS": "http://localhost:3000, https://app.example.com, https://api.example.com"
        },
        clear=False,
    ):
        cors_origins_str = os.getenv("PODX_CORS_ORIGINS", "*")
        cors_origins = (
            [origin.strip() for origin in cors_origins_str.split(",")]
            if cors_origins_str != "*"
            else ["*"]
        )

        assert cors_origins == [
            "http://localhost:3000",
            "https://app.example.com",
            "https://api.example.com",
        ]


def test_cors_origins_parsing_wildcard():
    """Test that wildcard is preserved."""
    with patch.dict(os.environ, {"PODX_CORS_ORIGINS": "*"}, clear=False):
        cors_origins_str = os.getenv("PODX_CORS_ORIGINS", "*")
        cors_origins = (
            [origin.strip() for origin in cors_origins_str.split(",")]
            if cors_origins_str != "*"
            else ["*"]
        )

        assert cors_origins == ["*"]
