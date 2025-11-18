"""Integration tests for processing endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_transcribe_endpoint(client: AsyncClient):
    """Test POST /api/v1/transcribe creates job."""
    response = await client.post(
        "/api/v1/transcribe",
        json={
            "audio_url": "https://example.com/audio.mp3",
            "model": "base",
        },
    )

    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"

    # Verify job was created
    job_id = data["job_id"]
    job_response = await client.get(f"/api/v1/jobs/{job_id}")
    assert job_response.status_code == 200
    job_data = job_response.json()
    assert job_data["job_type"] == "transcribe"
    assert job_data["input_params"]["audio_url"] == "https://example.com/audio.mp3"
    assert job_data["input_params"]["model"] == "base"


@pytest.mark.asyncio
async def test_transcribe_default_model(client: AsyncClient):
    """Test transcribe uses default model."""
    response = await client.post(
        "/api/v1/transcribe",
        json={"audio_url": "https://example.com/audio.mp3"},
    )

    assert response.status_code == 202
    job_id = response.json()["job_id"]

    job_response = await client.get(f"/api/v1/jobs/{job_id}")
    job_data = job_response.json()
    assert job_data["input_params"]["model"] == "base"


@pytest.mark.asyncio
async def test_diarize_endpoint(client: AsyncClient):
    """Test POST /api/v1/diarize creates job."""
    response = await client.post(
        "/api/v1/diarize",
        json={
            "audio_url": "https://example.com/audio.mp3",
            "num_speakers": 2,
        },
    )

    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"

    # Verify job was created
    job_id = data["job_id"]
    job_response = await client.get(f"/api/v1/jobs/{job_id}")
    assert job_response.status_code == 200
    job_data = job_response.json()
    assert job_data["job_type"] == "diarize"
    assert job_data["input_params"]["audio_url"] == "https://example.com/audio.mp3"
    assert job_data["input_params"]["num_speakers"] == 2


@pytest.mark.asyncio
async def test_diarize_no_num_speakers(client: AsyncClient):
    """Test diarize without num_speakers."""
    response = await client.post(
        "/api/v1/diarize",
        json={"audio_url": "https://example.com/audio.mp3"},
    )

    assert response.status_code == 202
    job_id = response.json()["job_id"]

    job_response = await client.get(f"/api/v1/jobs/{job_id}")
    job_data = job_response.json()
    assert "num_speakers" not in job_data["input_params"]


@pytest.mark.asyncio
async def test_deepcast_endpoint(client: AsyncClient):
    """Test POST /api/v1/deepcast creates job."""
    response = await client.post(
        "/api/v1/deepcast",
        json={"transcript_path": "/path/to/transcript.json"},
    )

    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"

    # Verify job was created
    job_id = data["job_id"]
    job_response = await client.get(f"/api/v1/jobs/{job_id}")
    assert job_response.status_code == 200
    job_data = job_response.json()
    assert job_data["job_type"] == "deepcast"
    assert job_data["input_params"]["transcript_path"] == "/path/to/transcript.json"


@pytest.mark.asyncio
async def test_pipeline_endpoint(client: AsyncClient):
    """Test POST /api/v1/pipeline creates job."""
    response = await client.post(
        "/api/v1/pipeline",
        json={
            "audio_url": "https://example.com/audio.mp3",
            "model": "small",
            "num_speakers": 3,
        },
    )

    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"

    # Verify job was created
    job_id = data["job_id"]
    job_response = await client.get(f"/api/v1/jobs/{job_id}")
    assert job_response.status_code == 200
    job_data = job_response.json()
    assert job_data["job_type"] == "pipeline"
    assert job_data["input_params"]["audio_url"] == "https://example.com/audio.mp3"
    assert job_data["input_params"]["model"] == "small"
    assert job_data["input_params"]["num_speakers"] == 3


@pytest.mark.asyncio
async def test_pipeline_default_values(client: AsyncClient):
    """Test pipeline with default values."""
    response = await client.post(
        "/api/v1/pipeline",
        json={"audio_url": "https://example.com/audio.mp3"},
    )

    assert response.status_code == 202
    job_id = response.json()["job_id"]

    job_response = await client.get(f"/api/v1/jobs/{job_id}")
    job_data = job_response.json()
    assert job_data["input_params"]["model"] == "base"
    assert "num_speakers" not in job_data["input_params"]


@pytest.mark.asyncio
async def test_transcribe_validation(client: AsyncClient):
    """Test transcribe validates required fields."""
    response = await client.post(
        "/api/v1/transcribe",
        json={},
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_diarize_validation(client: AsyncClient):
    """Test diarize validates required fields."""
    response = await client.post(
        "/api/v1/diarize",
        json={},
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_deepcast_validation(client: AsyncClient):
    """Test deepcast validates required fields."""
    response = await client.post(
        "/api/v1/deepcast",
        json={},
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_pipeline_validation(client: AsyncClient):
    """Test pipeline validates required fields."""
    response = await client.post(
        "/api/v1/pipeline",
        json={},
    )

    assert response.status_code == 422  # Validation error
