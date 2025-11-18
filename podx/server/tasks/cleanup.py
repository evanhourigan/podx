"""Background task for cleaning up old uploaded files and jobs.

Periodically removes files and database records for jobs older than a configured
threshold to prevent disk space exhaustion.
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from podx.logging import get_logger
from podx.server.database import async_session_factory
from podx.server.models.database import Job
from podx.server.storage import delete_upload_file, get_upload_dir

logger = get_logger(__name__)


def get_cleanup_config() -> tuple[int, int]:
    """Get cleanup configuration from environment.

    Returns:
        Tuple of (max_age_days, interval_hours)
        - max_age_days: Maximum age of jobs to keep (default: 7)
        - interval_hours: How often to run cleanup (default: 24)
    """
    max_age_days = int(os.getenv("PODX_CLEANUP_MAX_AGE_DAYS", "7"))
    interval_hours = int(os.getenv("PODX_CLEANUP_INTERVAL_HOURS", "24"))

    logger.info(
        f"Cleanup configured: max_age={max_age_days} days, interval={interval_hours} hours"
    )
    return max_age_days, interval_hours


async def cleanup_old_jobs(session: AsyncSession, max_age_days: int) -> int:
    """Clean up old jobs and their associated files.

    Args:
        session: Database session
        max_age_days: Maximum age of jobs to keep in days

    Returns:
        Number of jobs cleaned up
    """
    # Calculate cutoff date
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=max_age_days)

    logger.info(f"Cleaning up jobs older than {cutoff_date}")

    # Query old jobs
    stmt = select(Job).where(Job.created_at < cutoff_date)
    result = await session.execute(stmt)
    old_jobs = result.scalars().all()

    if not old_jobs:
        logger.info("No old jobs to clean up")
        return 0

    logger.info(f"Found {len(old_jobs)} jobs to clean up")

    # Clean up each job
    cleaned_count = 0
    for job in old_jobs:
        try:
            # Delete associated uploaded file if it exists
            if job.input_params and "audio_url" in job.input_params:
                audio_url = job.input_params["audio_url"]
                # Only delete if it's in our upload directory (don't delete external URLs)
                upload_dir = str(get_upload_dir())
                if audio_url.startswith(upload_dir):
                    delete_upload_file(audio_url)

            # Delete job from database
            await session.delete(job)
            cleaned_count += 1

        except Exception as e:
            logger.warning(f"Failed to clean up job {job.id}: {e}")

    # Commit all deletions
    await session.commit()

    logger.info(f"Successfully cleaned up {cleaned_count} old jobs")
    return cleaned_count


async def cleanup_orphaned_files() -> int:
    """Clean up orphaned files in the upload directory.

    Files that exist on disk but have no corresponding job in the database
    are considered orphaned and will be deleted.

    Returns:
        Number of orphaned files deleted
    """
    upload_dir = get_upload_dir()
    if not upload_dir.exists():
        return 0

    logger.info(f"Scanning for orphaned files in {upload_dir}")

    # Get all files in upload directory
    all_files = list(upload_dir.glob("*"))
    if not all_files:
        return 0

    # Query all jobs to find referenced files
    async with async_session_factory() as session:
        stmt = select(Job.input_params)
        result = await session.execute(stmt)
        all_input_params = result.scalars().all()

    # Build set of referenced file paths (as strings for comparison)
    referenced_files = set()
    for params in all_input_params:
        if params and "audio_url" in params:
            audio_url = params["audio_url"]
            referenced_files.add(str(audio_url))

    # Delete orphaned files
    orphaned_count = 0
    for file_path in all_files:
        if file_path.is_file() and str(file_path) not in referenced_files:
            try:
                file_path.unlink()
                logger.info(f"Deleted orphaned file: {file_path}")
                orphaned_count += 1
            except Exception as e:
                logger.warning(f"Failed to delete orphaned file {file_path}: {e}")

    if orphaned_count > 0:
        logger.info(f"Deleted {orphaned_count} orphaned files")
    else:
        logger.info("No orphaned files found")

    return orphaned_count


async def run_cleanup_task() -> None:
    """Background task that periodically runs cleanup operations.

    This task runs indefinitely until cancelled, performing cleanup
    at the configured interval.
    """
    max_age_days, interval_hours = get_cleanup_config()
    interval_seconds = interval_hours * 3600

    logger.info(f"Starting cleanup task (runs every {interval_hours} hours)")

    while True:
        try:
            # Run cleanup
            async with async_session_factory() as session:
                jobs_cleaned = await cleanup_old_jobs(session, max_age_days)

            # Clean up orphaned files
            files_cleaned = await cleanup_orphaned_files()

            logger.info(
                f"Cleanup completed: {jobs_cleaned} jobs, {files_cleaned} orphaned files"
            )

        except Exception as e:
            logger.error(f"Cleanup task error: {e}", exc_info=True)

        # Sleep until next cleanup
        await asyncio.sleep(interval_seconds)
