"""Integration tests for file upload endpoints."""

import io

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_upload_file(client: AsyncClient):
    """Test POST /api/v1/upload."""
    # Create a fake audio file
    file_content = b"fake audio data"
    files = {"file": ("test.mp3", io.BytesIO(file_content), "audio/mpeg")}

    response = await client.post("/api/v1/upload", files=files)

    assert response.status_code == 201
    data = response.json()
    assert "file_path" in data
    assert "filename" in data
    assert data["filename"] == "test.mp3"
    assert data["size"] == len(file_content)


@pytest.mark.asyncio
async def test_transcribe_with_upload(client: AsyncClient):
    """Test POST /api/v1/transcribe/upload."""
    # Create a fake audio file
    file_content = b"fake audio data for transcription"
    files = {"file": ("audio.mp3", io.BytesIO(file_content), "audio/mpeg")}
    data = {"model": "base"}

    response = await client.post("/api/v1/transcribe/upload", files=files, data=data)

    assert response.status_code == 202
    result = response.json()
    assert "job_id" in result
    assert result["status"] == "queued"

    # Verify job was created
    job_id = result["job_id"]
    job_response = await client.get(f"/api/v1/jobs/{job_id}")
    assert job_response.status_code == 200
    job_data = job_response.json()
    assert job_data["job_type"] == "transcribe"
    assert job_data["input_params"]["model"] == "base"
    assert "audio_url" in job_data["input_params"]


@pytest.mark.asyncio
async def test_transcribe_upload_default_model(client: AsyncClient):
    """Test transcribe upload uses default model."""
    file_content = b"fake audio"
    files = {"file": ("audio.mp3", io.BytesIO(file_content), "audio/mpeg")}

    response = await client.post("/api/v1/transcribe/upload", files=files)

    assert response.status_code == 202
    job_id = response.json()["job_id"]

    job_response = await client.get(f"/api/v1/jobs/{job_id}")
    job_data = job_response.json()
    assert job_data["input_params"]["model"] == "base"


@pytest.mark.asyncio
async def test_diarize_with_upload(client: AsyncClient):
    """Test POST /api/v1/diarize/upload."""
    file_content = b"fake audio data for diarization"
    files = {"file": ("audio.mp3", io.BytesIO(file_content), "audio/mpeg")}
    data = {"num_speakers": "2"}

    response = await client.post("/api/v1/diarize/upload", files=files, data=data)

    assert response.status_code == 202
    result = response.json()
    assert "job_id" in result
    assert result["status"] == "queued"

    # Verify job was created
    job_id = result["job_id"]
    job_response = await client.get(f"/api/v1/jobs/{job_id}")
    assert job_response.status_code == 200
    job_data = job_response.json()
    assert job_data["job_type"] == "diarize"
    assert job_data["input_params"]["num_speakers"] == 2


@pytest.mark.asyncio
async def test_diarize_upload_no_num_speakers(client: AsyncClient):
    """Test diarize upload without num_speakers."""
    file_content = b"fake audio"
    files = {"file": ("audio.mp3", io.BytesIO(file_content), "audio/mpeg")}

    response = await client.post("/api/v1/diarize/upload", files=files)

    assert response.status_code == 202
    job_id = response.json()["job_id"]

    job_response = await client.get(f"/api/v1/jobs/{job_id}")
    job_data = job_response.json()
    assert "num_speakers" not in job_data["input_params"]


@pytest.mark.asyncio
async def test_pipeline_with_upload(client: AsyncClient):
    """Test POST /api/v1/pipeline/upload."""
    file_content = b"fake audio data for pipeline"
    files = {"file": ("audio.mp3", io.BytesIO(file_content), "audio/mpeg")}
    data = {"model": "small", "num_speakers": "3"}

    response = await client.post("/api/v1/pipeline/upload", files=files, data=data)

    assert response.status_code == 202
    result = response.json()
    assert "job_id" in result
    assert result["status"] == "queued"

    # Verify job was created
    job_id = result["job_id"]
    job_response = await client.get(f"/api/v1/jobs/{job_id}")
    assert job_response.status_code == 200
    job_data = job_response.json()
    assert job_data["job_type"] == "pipeline"
    assert job_data["input_params"]["model"] == "small"
    assert job_data["input_params"]["num_speakers"] == 3


@pytest.mark.asyncio
async def test_pipeline_upload_defaults(client: AsyncClient):
    """Test pipeline upload with default values."""
    file_content = b"fake audio"
    files = {"file": ("audio.mp3", io.BytesIO(file_content), "audio/mpeg")}

    response = await client.post("/api/v1/pipeline/upload", files=files)

    assert response.status_code == 202
    job_id = response.json()["job_id"]

    job_response = await client.get(f"/api/v1/jobs/{job_id}")
    job_data = job_response.json()
    assert job_data["input_params"]["model"] == "base"
    assert "num_speakers" not in job_data["input_params"]


@pytest.mark.asyncio
async def test_upload_missing_file(client: AsyncClient):
    """Test upload endpoints require file."""
    response = await client.post("/api/v1/transcribe/upload", data={"model": "base"})

    assert response.status_code == 422  # Validation error
