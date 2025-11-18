"""Integration tests for error handling."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_invalid_job_type(client: AsyncClient):
    """Test creating job with invalid job_type."""
    response = await client.post(
        "/api/v1/jobs",
        params={"job_type": "invalid_type", "input_params": {}},
    )

    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert "invalid_type" in data["error"].lower()
    assert "job_type" in data["details"]["field"]


@pytest.mark.asyncio
async def test_invalid_whisper_model(client: AsyncClient):
    """Test transcribe with invalid model name."""
    response = await client.post(
        "/api/v1/transcribe",
        json={"audio_url": "test.mp3", "model": "invalid_model"},
    )

    assert response.status_code == 422  # Pydantic validation error
    data = response.json()
    assert "detail" in data  # Pydantic uses 'detail' key


@pytest.mark.asyncio
async def test_empty_audio_url(client: AsyncClient):
    """Test transcribe with empty audio_url."""
    response = await client.post(
        "/api/v1/transcribe",
        json={"audio_url": "   ", "model": "base"},
    )

    assert response.status_code == 422  # Pydantic validation error
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_invalid_num_speakers_too_low(client: AsyncClient):
    """Test diarize with num_speakers < 2."""
    response = await client.post(
        "/api/v1/diarize",
        json={"audio_url": "test.mp3", "num_speakers": 1},
    )

    assert response.status_code == 422  # Pydantic validation error
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_invalid_num_speakers_too_high(client: AsyncClient):
    """Test diarize with num_speakers > 10."""
    response = await client.post(
        "/api/v1/diarize",
        json={"audio_url": "test.mp3", "num_speakers": 15},
    )

    assert response.status_code == 422  # Pydantic validation error
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_job_not_found(client: AsyncClient):
    """Test getting non-existent job returns proper error."""
    response = await client.get("/api/v1/jobs/fake-job-id")

    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert "fake-job-id" in data["error"]
    assert data["details"]["job_id"] == "fake-job-id"


@pytest.mark.asyncio
async def test_cancel_nonexistent_job(client: AsyncClient):
    """Test cancelling non-existent job."""
    response = await client.delete("/api/v1/jobs/fake-job-id")

    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert "fake-job-id" in data["error"]


@pytest.mark.asyncio
async def test_stream_nonexistent_job(client: AsyncClient):
    """Test streaming non-existent job."""
    response = await client.get("/api/v1/jobs/fake-job-id/stream")

    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert "fake-job-id" in data["error"]


@pytest.mark.asyncio
async def test_valid_whisper_models(client: AsyncClient):
    """Test all valid Whisper models are accepted."""
    valid_models = ["tiny", "base", "small", "medium", "large"]

    for model in valid_models:
        response = await client.post(
            "/api/v1/transcribe",
            json={"audio_url": "test.mp3", "model": model},
        )
        assert response.status_code == 202, f"Model {model} should be valid"
        data = response.json()
        assert "job_id" in data


@pytest.mark.asyncio
async def test_valid_num_speakers_range(client: AsyncClient):
    """Test valid num_speakers values (2-10)."""
    for num in [2, 5, 10]:
        response = await client.post(
            "/api/v1/diarize",
            json={"audio_url": "test.mp3", "num_speakers": num},
        )
        assert response.status_code == 202, f"num_speakers={num} should be valid"
        data = response.json()
        assert "job_id" in data
