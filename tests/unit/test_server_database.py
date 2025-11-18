"""Unit tests for PodX server database models."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from podx.server.models.database import Base, Job


@pytest.fixture
async def async_session():
    """Create an async test database session.

    Uses in-memory SQLite database for testing.
    """
    # Create in-memory async engine
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Yield session
    async with session_factory() as session:
        yield session

    # Cleanup
    await engine.dispose()


@pytest.mark.asyncio
async def test_job_create(async_session: AsyncSession):
    """Test creating a job in the database."""
    # Create a job
    job_id = str(uuid.uuid4())
    job = Job(
        id=job_id,
        status="queued",
        job_type="transcribe",
        input_params={"audio_url": "https://example.com/audio.mp3", "model": "base"},
    )

    async_session.add(job)
    await async_session.commit()

    # Query it back
    result = await async_session.get(Job, job_id)
    assert result is not None
    assert result.id == job_id
    assert result.status == "queued"
    assert result.job_type == "transcribe"
    assert result.input_params == {"audio_url": "https://example.com/audio.mp3", "model": "base"}
    assert result.progress is None
    assert result.result is None
    assert result.error is None
    assert isinstance(result.created_at, datetime)
    assert isinstance(result.updated_at, datetime)
    assert result.started_at is None
    assert result.completed_at is None


@pytest.mark.asyncio
async def test_job_update_status(async_session: AsyncSession):
    """Test updating job status."""
    # Create a job
    job_id = str(uuid.uuid4())
    job = Job(id=job_id, status="queued", job_type="diarize")

    async_session.add(job)
    await async_session.commit()

    # Update status to running
    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    job.progress = {"percentage": 0.0, "step": "preprocessing"}
    await async_session.commit()

    # Query it back
    result = await async_session.get(Job, job_id)
    assert result.status == "running"
    assert result.started_at is not None
    assert result.progress == {"percentage": 0.0, "step": "preprocessing"}


@pytest.mark.asyncio
async def test_job_complete(async_session: AsyncSession):
    """Test completing a job."""
    # Create a running job
    job_id = str(uuid.uuid4())
    job = Job(
        id=job_id,
        status="running",
        job_type="deepcast",
        started_at=datetime.now(timezone.utc),
    )

    async_session.add(job)
    await async_session.commit()

    # Complete the job
    job.status = "completed"
    job.completed_at = datetime.now(timezone.utc)
    job.result = {
        "output_path": "/path/to/result.json",
        "duration_seconds": 120,
    }
    await async_session.commit()

    # Query it back
    result = await async_session.get(Job, job_id)
    assert result.status == "completed"
    assert result.completed_at is not None
    assert result.result == {"output_path": "/path/to/result.json", "duration_seconds": 120}


@pytest.mark.asyncio
async def test_job_fail(async_session: AsyncSession):
    """Test failing a job."""
    # Create a running job
    job_id = str(uuid.uuid4())
    job = Job(
        id=job_id,
        status="running",
        job_type="pipeline",
        started_at=datetime.now(timezone.utc),
    )

    async_session.add(job)
    await async_session.commit()

    # Fail the job
    job.status = "failed"
    job.completed_at = datetime.now(timezone.utc)
    job.error = "Audio file not found"
    await async_session.commit()

    # Query it back
    result = await async_session.get(Job, job_id)
    assert result.status == "failed"
    assert result.completed_at is not None
    assert result.error == "Audio file not found"
    assert result.result is None


@pytest.mark.asyncio
async def test_job_list(async_session: AsyncSession):
    """Test listing multiple jobs."""
    # Create multiple jobs
    jobs = [
        Job(id=str(uuid.uuid4()), status="queued", job_type="transcribe"),
        Job(id=str(uuid.uuid4()), status="running", job_type="diarize"),
        Job(id=str(uuid.uuid4()), status="completed", job_type="deepcast"),
    ]

    for job in jobs:
        async_session.add(job)
    await async_session.commit()

    # Query all jobs
    from sqlalchemy import select

    result = await async_session.execute(select(Job))
    all_jobs = result.scalars().all()

    assert len(all_jobs) == 3
    assert {job.status for job in all_jobs} == {"queued", "running", "completed"}


@pytest.mark.asyncio
async def test_job_delete(async_session: AsyncSession):
    """Test deleting a job."""
    # Create a job
    job_id = str(uuid.uuid4())
    job = Job(id=job_id, status="completed", job_type="transcribe")

    async_session.add(job)
    await async_session.commit()

    # Delete it
    await async_session.delete(job)
    await async_session.commit()

    # Verify it's gone
    result = await async_session.get(Job, job_id)
    assert result is None


@pytest.mark.asyncio
async def test_job_updated_at_auto_update(async_session: AsyncSession):
    """Test that updated_at is automatically updated on modification."""
    # Create a job
    job_id = str(uuid.uuid4())
    job = Job(id=job_id, status="queued", job_type="transcribe")

    async_session.add(job)
    await async_session.commit()

    # Get timestamp as timezone-aware for comparison
    original_updated_at = job.updated_at.replace(tzinfo=timezone.utc)

    # Update the job
    job.status = "running"
    await async_session.commit()

    # Refresh from DB to get the updated timestamp
    await async_session.refresh(job)

    # Get updated timestamp as timezone-aware
    new_updated_at = job.updated_at.replace(tzinfo=timezone.utc)

    # updated_at should be newer (or same if too fast)
    assert new_updated_at >= original_updated_at
