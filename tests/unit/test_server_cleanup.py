"""Unit tests for server file cleanup functionality."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from podx.server.models.database import Job
from podx.server.tasks.cleanup import cleanup_old_jobs, cleanup_orphaned_files, get_cleanup_config


def test_get_cleanup_config_defaults():
    """Test that cleanup config returns defaults when env vars not set."""
    with patch.dict(os.environ, {}, clear=True):
        # Clear any existing cleanup env vars
        os.environ.pop("PODX_CLEANUP_MAX_AGE_DAYS", None)
        os.environ.pop("PODX_CLEANUP_INTERVAL_HOURS", None)

        max_age, interval = get_cleanup_config()

        assert max_age == 7
        assert interval == 24


def test_get_cleanup_config_custom():
    """Test that cleanup config respects custom env vars."""
    with patch.dict(
        os.environ,
        {
            "PODX_CLEANUP_MAX_AGE_DAYS": "14",
            "PODX_CLEANUP_INTERVAL_HOURS": "12",
        },
        clear=False,
    ):
        max_age, interval = get_cleanup_config()

        assert max_age == 14
        assert interval == 12


@pytest.mark.asyncio
async def test_cleanup_old_jobs_no_old_jobs():
    """Test cleanup when there are no old jobs."""
    # Create mock session
    session = MagicMock(spec=AsyncSession)

    # Mock empty query result
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=mock_result)

    cleaned = await cleanup_old_jobs(session, max_age_days=7)

    assert cleaned == 0
    # Commit should not be called if nothing was cleaned
    session.commit.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.skip(
    reason="Flaky: passes when run alone or with unit tests, fails when run with integration tests due to module reload interference"
)
async def test_cleanup_old_jobs_with_local_files():
    """Test cleanup of old jobs with uploaded files."""
    # Create mock session
    session = MagicMock(spec=AsyncSession)

    # Use a unique test upload directory to avoid conflicts
    upload_dir = "/tmp/test_cleanup_uploads_unique_123"
    old_job = Job(
        id="job-1",
        status="completed",
        job_type="transcribe",
        input_params={"audio_url": f"{upload_dir}/test.mp3"},
        created_at=datetime.now(timezone.utc) - timedelta(days=10),
    )

    # Mock query result
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [old_job]
    session.execute = AsyncMock(return_value=mock_result)
    session.delete = AsyncMock()
    session.commit = AsyncMock()

    # Mock both get_upload_dir and delete_upload_file
    mock_delete = MagicMock()
    with patch("podx.server.tasks.cleanup.get_upload_dir", return_value=Path(upload_dir)):
        with patch("podx.server.tasks.cleanup.delete_upload_file", mock_delete):
            cleaned = await cleanup_old_jobs(session, max_age_days=7)

            assert cleaned == 1
            mock_delete.assert_called_once_with(f"{upload_dir}/test.mp3")
            session.delete.assert_called_once()
            session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_cleanup_old_jobs_with_external_urls():
    """Test cleanup doesn't delete external URLs."""
    # Create mock session
    session = MagicMock(spec=AsyncSession)

    # Create old job with external URL
    old_job = Job(
        id="job-1",
        status="completed",
        job_type="transcribe",
        input_params={"audio_url": "https://example.com/audio.mp3"},
        created_at=datetime.now(timezone.utc) - timedelta(days=10),
    )

    # Mock query result
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [old_job]
    session.execute = AsyncMock(return_value=mock_result)
    session.delete = AsyncMock()
    session.commit = AsyncMock()

    with patch(
        "podx.server.tasks.cleanup.get_upload_dir",
        return_value=Path("/Users/test/.podx/uploads"),
    ):
        with patch("podx.server.tasks.cleanup.delete_upload_file") as mock_delete:
            cleaned = await cleanup_old_jobs(session, max_age_days=7)

    assert cleaned == 1
    # delete_upload_file should not be called for external URLs
    mock_delete.assert_not_called()
    session.delete.assert_called_once()
    session.commit.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.skip(
    reason="Flaky: passes when run alone or with unit tests, fails when run with integration tests due to module reload interference"
)
async def test_cleanup_orphaned_files_no_files():
    """Test cleanup when upload directory is empty."""
    # Create a mock Path object that behaves correctly
    mock_dir = MagicMock(spec=Path)
    mock_dir.exists.return_value = True
    mock_dir.glob.return_value = []  # Empty list of files

    with patch("podx.server.tasks.cleanup.get_upload_dir", return_value=mock_dir):
        deleted = await cleanup_orphaned_files()

        assert deleted == 0


@pytest.mark.asyncio
@pytest.mark.skip(
    reason="Flaky: passes when run alone or with unit tests, fails when run with integration tests due to module reload interference"
)
async def test_cleanup_orphaned_files_all_referenced():
    """Test cleanup when all files are referenced by jobs."""
    # Create mock file objects
    file1 = MagicMock(spec=Path)
    file1.is_file.return_value = True
    file1.__str__.return_value = "/tmp/test_uploads/file1.mp3"

    file2 = MagicMock(spec=Path)
    file2.is_file.return_value = True
    file2.__str__.return_value = "/tmp/test_uploads/file2.mp3"

    # Create mock upload directory
    mock_upload_dir = MagicMock(spec=Path)
    mock_upload_dir.exists.return_value = True
    mock_upload_dir.glob.return_value = [file1, file2]

    with patch("podx.server.tasks.cleanup.get_upload_dir", return_value=mock_upload_dir):
        # Mock database query returning jobs that reference these files
        with patch("podx.server.tasks.cleanup.async_session_factory") as mock_factory:
            mock_session = MagicMock()
            mock_result = MagicMock()
            # Return both files as referenced
            mock_result.scalars.return_value.all.return_value = [
                {"audio_url": "/tmp/test_uploads/file1.mp3"},
                {"audio_url": "/tmp/test_uploads/file2.mp3"},
            ]
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_factory.return_value.__aenter__.return_value = mock_session

            deleted = await cleanup_orphaned_files()

    assert deleted == 0
    # Verify neither file was deleted
    file1.unlink.assert_not_called()
    file2.unlink.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.skip(
    reason="Flaky: passes when run alone or with unit tests, fails when run with integration tests due to module reload interference"
)
async def test_cleanup_orphaned_files_with_orphans():
    """Test cleanup deletes orphaned files."""
    # Create mock file objects
    file1 = MagicMock(spec=Path)
    file1.is_file.return_value = True
    file1.__str__.return_value = "/tmp/test_uploads/file1.mp3"

    file2 = MagicMock(spec=Path)
    file2.is_file.return_value = True
    file2.__str__.return_value = "/tmp/test_uploads/file2.mp3"

    # Create mock upload directory
    mock_upload_dir = MagicMock(spec=Path)
    mock_upload_dir.exists.return_value = True
    mock_upload_dir.glob.return_value = [file1, file2]

    with patch("podx.server.tasks.cleanup.get_upload_dir", return_value=mock_upload_dir):
        # Mock database query returning only one referenced file
        with patch("podx.server.tasks.cleanup.async_session_factory") as mock_factory:
            mock_session = MagicMock()
            mock_result = MagicMock()
            # Only file1 is referenced, file2 is orphaned
            mock_result.scalars.return_value.all.return_value = [
                {"audio_url": "/tmp/test_uploads/file1.mp3"},
            ]
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_factory.return_value.__aenter__.return_value = mock_session

            deleted = await cleanup_orphaned_files()

    # file2 should be deleted as it's orphaned
    assert deleted == 1
    file2.unlink.assert_called_once()
    # file1 should not be deleted
    file1.unlink.assert_not_called()
