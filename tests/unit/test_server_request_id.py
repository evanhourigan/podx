"""Unit tests for request ID middleware."""

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from podx.server.middleware.request_id import (
    REQUEST_ID_HEADER,
    RequestIDMiddleware,
    get_request_id,
)


@pytest.fixture
def app_with_request_id():
    """Create minimal app with request ID middleware."""
    app = FastAPI()

    # Add request ID middleware
    app.add_middleware(RequestIDMiddleware)

    # Add test endpoint that returns request ID
    @app.get("/api/v1/test")
    async def test_endpoint(request: Request):
        return {"request_id": get_request_id(request)}

    return app


@pytest.mark.asyncio
async def test_request_id_generated_when_not_provided(app_with_request_id):
    """Test that request ID is generated when not provided by client."""
    transport = ASGITransport(app=app_with_request_id)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/test")

        assert response.status_code == 200
        # Response should have X-Request-ID header
        assert REQUEST_ID_HEADER in response.headers
        request_id = response.headers[REQUEST_ID_HEADER]

        # Request ID should be a valid UUID (36 chars with hyphens)
        assert len(request_id) == 36
        assert request_id.count("-") == 4

        # Request ID should also be in response body
        assert response.json()["request_id"] == request_id


@pytest.mark.asyncio
async def test_request_id_preserved_when_provided(app_with_request_id):
    """Test that request ID from client is preserved."""
    transport = ASGITransport(app=app_with_request_id)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Provide custom request ID
        custom_id = "custom-request-id-12345"

        response = await client.get(
            "/api/v1/test",
            headers={REQUEST_ID_HEADER: custom_id},
        )

        assert response.status_code == 200
        # Response should echo back the custom request ID
        assert response.headers[REQUEST_ID_HEADER] == custom_id
        assert response.json()["request_id"] == custom_id


@pytest.mark.asyncio
async def test_request_id_unique_across_requests(app_with_request_id):
    """Test that different requests get different request IDs."""
    transport = ASGITransport(app=app_with_request_id)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Make multiple requests
        response1 = await client.get("/api/v1/test")
        response2 = await client.get("/api/v1/test")
        response3 = await client.get("/api/v1/test")

        id1 = response1.headers[REQUEST_ID_HEADER]
        id2 = response2.headers[REQUEST_ID_HEADER]
        id3 = response3.headers[REQUEST_ID_HEADER]

        # All request IDs should be different
        assert id1 != id2
        assert id2 != id3
        assert id1 != id3


@pytest.mark.asyncio
async def test_request_id_available_in_request_state(app_with_request_id):
    """Test that request ID is available in request.state."""
    transport = ASGITransport(app=app_with_request_id)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/test")

        # Request ID from header should match the one in request state
        header_id = response.headers[REQUEST_ID_HEADER]
        body_id = response.json()["request_id"]

        assert header_id == body_id


@pytest.mark.asyncio
async def test_get_request_id_with_no_middleware():
    """Test get_request_id returns 'unknown' when middleware not used."""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint(request: Request):
        return {"request_id": get_request_id(request)}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/test")

        # Should return "unknown" when request_id not in state
        assert response.json()["request_id"] == "unknown"
