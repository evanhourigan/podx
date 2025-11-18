"""Integration tests for PodX server job endpoints."""

import os
import tempfile

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(scope="function", autouse=True)
def setup_test_db():
    """Set up a unique test database for each test."""
    # Create unique temp database
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    original_db_path = os.environ.get("PODX_DB_PATH")

    # Set env var
    os.environ["PODX_DB_PATH"] = db_path

    # Force reload of database module to pick up new path
    import sys

    # Remove cached modules
    modules_to_reload = [k for k in sys.modules if k.startswith("podx.server")]
    for module in modules_to_reload:
        del sys.modules[module]

    yield

    # Cleanup
    os.close(db_fd)
    if os.path.exists(db_path):
        os.unlink(db_path)

    # Restore original env var
    if original_db_path:
        os.environ["PODX_DB_PATH"] = original_db_path
    elif "PODX_DB_PATH" in os.environ:
        del os.environ["PODX_DB_PATH"]


@pytest.fixture(scope="function")
async def client(setup_test_db):
    """Create test client."""
    from podx.server.app import create_app
    from podx.server.database import init_db

    # Create the app
    app = create_app()

    # Manually initialize the database (lifespan doesn't run in tests)
    await init_db()

    # Create client
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_create_job(client: AsyncClient):
    """Test creating a job via API."""
    response = await client.post(
        "/api/v1/jobs",
        params={
            "job_type": "transcribe",
        },
        json={"audio_url": "https://example.com/audio.mp3", "model": "base"},
    )

    assert response.status_code == 201
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"
    assert len(data["job_id"]) == 36  # UUID length


@pytest.mark.asyncio
async def test_get_job(client: AsyncClient):
    """Test getting a job by ID."""
    # Create a job first
    create_response = await client.post(
        "/api/v1/jobs", params={"job_type": "diarize"}, json={}
    )
    job_id = create_response.json()["job_id"]

    # Get the job
    response = await client.get(f"/api/v1/jobs/{job_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == job_id
    assert data["status"] == "queued"
    assert data["job_type"] == "diarize"
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_get_job_not_found(client: AsyncClient):
    """Test getting a non-existent job."""
    response = await client.get("/api/v1/jobs/nonexistent-id")
    assert response.status_code == 404
    assert "not found" in response.json()["error"].lower()


@pytest.mark.asyncio
async def test_list_jobs(client: AsyncClient):
    """Test listing jobs."""
    # Create multiple jobs
    for i in range(5):
        await client.post("/api/v1/jobs", params={"job_type": "transcribe"}, json={})

    # List jobs
    response = await client.get("/api/v1/jobs")

    assert response.status_code == 200
    data = response.json()
    assert "jobs" in data
    assert "total" in data
    assert "skip" in data
    assert "limit" in data
    assert data["total"] == 5
    assert len(data["jobs"]) == 5


@pytest.mark.asyncio
async def test_list_jobs_pagination(client: AsyncClient):
    """Test job listing with pagination."""
    # Create 10 jobs
    for i in range(10):
        await client.post("/api/v1/jobs", params={"job_type": "transcribe"}, json={})

    # Get first page (5 jobs)
    response = await client.get("/api/v1/jobs?skip=0&limit=5")
    assert response.status_code == 200
    data = response.json()
    assert len(data["jobs"]) == 5
    assert data["total"] == 10
    assert data["skip"] == 0
    assert data["limit"] == 5

    # Get second page (5 jobs)
    response = await client.get("/api/v1/jobs?skip=5&limit=5")
    assert response.status_code == 200
    data = response.json()
    assert len(data["jobs"]) == 5
    assert data["total"] == 10
    assert data["skip"] == 5


@pytest.mark.asyncio
async def test_list_jobs_filter_by_status(client: AsyncClient):
    """Test filtering jobs by status."""
    # Create jobs with different statuses
    await client.post("/api/v1/jobs", params={"job_type": "transcribe"}, json={})
    await client.post("/api/v1/jobs", params={"job_type": "diarize"}, json={})

    # Filter by status
    response = await client.get("/api/v1/jobs?status=queued")
    assert response.status_code == 200
    data = response.json()
    assert all(job["status"] == "queued" for job in data["jobs"])


@pytest.mark.asyncio
async def test_list_jobs_filter_by_type(client: AsyncClient):
    """Test filtering jobs by type."""
    # Create jobs of different types
    await client.post("/api/v1/jobs", params={"job_type": "transcribe"}, json={})
    await client.post("/api/v1/jobs", params={"job_type": "transcribe"}, json={})
    await client.post("/api/v1/jobs", params={"job_type": "diarize"}, json={})

    # Filter by type
    response = await client.get("/api/v1/jobs?job_type=transcribe")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert all(job["job_type"] == "transcribe" for job in data["jobs"])


@pytest.mark.asyncio
async def test_cancel_queued_job(client: AsyncClient):
    """Test cancelling a queued job."""
    # Create a job
    create_response = await client.post(
        "/api/v1/jobs", params={"job_type": "transcribe"}, json={}
    )
    job_id = create_response.json()["job_id"]

    # Cancel it
    response = await client.delete(f"/api/v1/jobs/{job_id}")
    assert response.status_code == 204

    # Verify it's cancelled
    get_response = await client.get(f"/api/v1/jobs/{job_id}")
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_delete_completed_job(client: AsyncClient):
    """Test deleting a completed job."""
    # Create a job
    create_response = await client.post(
        "/api/v1/jobs", params={"job_type": "transcribe"}, json={}
    )
    job_id = create_response.json()["job_id"]

    # Manually mark it as completed (would normally be done by worker)
    # For now, we'll just cancel it twice to test deletion path
    await client.delete(f"/api/v1/jobs/{job_id}")  # First delete: cancel
    response = await client.delete(f"/api/v1/jobs/{job_id}")  # Second delete: remove
    assert response.status_code == 204

    # Verify it's gone
    get_response = await client.get(f"/api/v1/jobs/{job_id}")
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_cancel_job_not_found(client: AsyncClient):
    """Test cancelling a non-existent job."""
    response = await client.delete("/api/v1/jobs/nonexistent-id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_jobs_empty(client: AsyncClient):
    """Test listing jobs when there are none."""
    response = await client.get("/api/v1/jobs")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert len(data["jobs"]) == 0
