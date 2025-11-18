"""Unit tests for server authentication middleware."""

import os
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from podx.server.middleware.auth import APIKeyAuthMiddleware


@pytest.fixture
def app_no_auth():
    """Create minimal app without authentication."""
    with patch.dict(os.environ, {}, clear=False):
        # Clear any existing API key
        if "PODX_API_KEY" in os.environ:
            del os.environ["PODX_API_KEY"]

        # Create minimal FastAPI app for testing auth middleware
        app = FastAPI()
        app.add_middleware(APIKeyAuthMiddleware)

        # Add test endpoints
        @app.get("/health")
        async def health():
            return {"status": "healthy"}

        @app.get("/docs")
        async def docs():
            return {"message": "docs"}

        @app.get("/api/v1/jobs")
        async def list_jobs():
            return []

        @app.post("/api/v1/transcribe", status_code=202)
        async def create_transcribe():
            return {"job_id": "test-job-123"}

        @app.get("/api/v1/jobs/{job_id}")
        async def get_job(job_id: str):
            return {"job_id": job_id, "status": "queued"}

        @app.get("/api/v1/jobs/{job_id}/stream")
        async def stream_job(job_id: str):
            return {"message": "streaming"}

        yield app


@pytest.fixture
def app_with_auth():
    """Create minimal app with authentication enabled."""
    with patch.dict(os.environ, {"PODX_API_KEY": "test-api-key-12345"}, clear=False):
        # Create minimal FastAPI app for testing auth middleware
        app = FastAPI()
        app.add_middleware(APIKeyAuthMiddleware)

        # Add test endpoints
        @app.get("/health")
        async def health():
            return {"status": "healthy"}

        @app.get("/docs")
        async def docs():
            return {"message": "docs"}

        @app.get("/api/v1/jobs")
        async def list_jobs():
            return []

        @app.post("/api/v1/transcribe", status_code=202)
        async def create_transcribe():
            return {"job_id": "test-job-123"}

        @app.get("/api/v1/jobs/{job_id}")
        async def get_job(job_id: str):
            return {"job_id": job_id, "status": "queued"}

        @app.get("/api/v1/jobs/{job_id}/stream")
        async def stream_job(job_id: str):
            return {"message": "streaming"}

        yield app


@pytest.mark.asyncio
async def test_health_endpoint_no_auth_required(app_with_auth):
    """Test that health endpoint doesn't require authentication."""
    transport = ASGITransport(app=app_with_auth)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_docs_endpoint_no_auth_required(app_with_auth):
    """Test that /docs endpoint doesn't require authentication."""
    transport = ASGITransport(app=app_with_auth)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/docs")
        # Should redirect or return docs, not 401
        assert response.status_code != 401


@pytest.mark.asyncio
async def test_api_endpoint_without_auth_disabled(app_no_auth):
    """Test API endpoint works when auth is disabled."""
    transport = ASGITransport(app=app_no_auth)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Should work without X-API-Key header when auth disabled
        response = await client.get("/api/v1/jobs")
        # May be 200 (empty list) or other valid response, but NOT 401
        assert response.status_code != 401


@pytest.mark.asyncio
async def test_api_endpoint_without_header_auth_enabled(app_with_auth):
    """Test API endpoint returns 401 when auth enabled but no header provided."""
    transport = ASGITransport(app=app_with_auth)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/jobs")
        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert "Authentication required" in data["error"]
        assert data["status_code"] == 401


@pytest.mark.asyncio
async def test_api_endpoint_with_invalid_key(app_with_auth):
    """Test API endpoint returns 403 with invalid API key."""
    transport = ASGITransport(app=app_with_auth)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/jobs",
            headers={"X-API-Key": "wrong-key"},
        )
        assert response.status_code == 403
        data = response.json()
        assert "error" in data
        assert "Invalid API key" in data["error"]
        assert data["status_code"] == 403


@pytest.mark.asyncio
async def test_api_endpoint_with_valid_key(app_with_auth):
    """Test API endpoint works with valid API key."""
    transport = ASGITransport(app=app_with_auth)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/jobs",
            headers={"X-API-Key": "test-api-key-12345"},
        )
        # Should not be auth error (may be 200 or other valid response)
        assert response.status_code != 401
        assert response.status_code != 403


@pytest.mark.asyncio
async def test_post_endpoint_with_valid_key(app_with_auth):
    """Test POST endpoint works with valid API key."""
    transport = ASGITransport(app=app_with_auth)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/transcribe",
            json={"audio_url": "test.mp3", "model": "base"},
            headers={"X-API-Key": "test-api-key-12345"},
        )
        # Should not be auth error (202 Accepted expected)
        assert response.status_code != 401
        assert response.status_code != 403
        assert response.status_code == 202


@pytest.mark.asyncio
async def test_post_endpoint_without_key(app_with_auth):
    """Test POST endpoint returns 401 without API key."""
    transport = ASGITransport(app=app_with_auth)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/transcribe",
            json={"audio_url": "test.mp3", "model": "base"},
        )
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_streaming_endpoint_with_valid_key(app_with_auth):
    """Test SSE streaming endpoint works with valid API key."""
    transport = ASGITransport(app=app_with_auth)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # First create a job
        create_response = await client.post(
            "/api/v1/transcribe",
            json={"audio_url": "test.mp3", "model": "base"},
            headers={"X-API-Key": "test-api-key-12345"},
        )
        assert create_response.status_code == 202
        job_id = create_response.json()["job_id"]

        # Then try to stream it
        stream_response = await client.get(
            f"/api/v1/jobs/{job_id}/stream",
            headers={"X-API-Key": "test-api-key-12345"},
        )
        # Should not be auth error
        assert stream_response.status_code != 401
        assert stream_response.status_code != 403


@pytest.mark.asyncio
async def test_streaming_endpoint_without_key(app_with_auth):
    """Test SSE streaming endpoint returns 401 without API key."""
    transport = ASGITransport(app=app_with_auth)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create job first (with auth)
        create_response = await client.post(
            "/api/v1/transcribe",
            json={"audio_url": "test.mp3", "model": "base"},
            headers={"X-API-Key": "test-api-key-12345"},
        )
        job_id = create_response.json()["job_id"]

        # Try to stream without auth
        stream_response = await client.get(f"/api/v1/jobs/{job_id}/stream")
        assert stream_response.status_code == 401


@pytest.mark.asyncio
async def test_multiple_requests_with_valid_key(app_with_auth):
    """Test multiple API requests with valid key all work."""
    transport = ASGITransport(app=app_with_auth)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"X-API-Key": "test-api-key-12345"}

        # List jobs
        response1 = await client.get("/api/v1/jobs", headers=headers)
        assert response1.status_code == 200

        # Create job
        response2 = await client.post(
            "/api/v1/transcribe",
            json={"audio_url": "test.mp3", "model": "base"},
            headers=headers,
        )
        assert response2.status_code == 202

        # Get job
        job_id = response2.json()["job_id"]
        response3 = await client.get(f"/api/v1/jobs/{job_id}", headers=headers)
        assert response3.status_code in (200, 404)  # May not exist yet
