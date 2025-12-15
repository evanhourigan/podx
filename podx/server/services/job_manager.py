"""Job management service for PodX server."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from podx.server.models import Job


class JobManager:
    """Manages job lifecycle and database operations.

    Provides high-level interface for creating, updating, and querying jobs.
    """

    def __init__(self, session: AsyncSession):
        """Initialize job manager.

        Args:
            session: Database session
        """
        self.session = session

    async def create_job(self, job_type: str, input_params: Optional[dict] = None) -> Job:
        """Create a new job.

        Args:
            job_type: Type of job (transcribe, diarize, deepcast, pipeline)
            input_params: Job-specific input parameters

        Returns:
            Created job
        """
        job = Job(
            id=str(uuid.uuid4()),
            status="queued",
            job_type=job_type,
            input_params=input_params or {},
        )

        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)

        return job

    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID.

        Args:
            job_id: Job ID

        Returns:
            Job if found, None otherwise
        """
        return await self.session.get(Job, job_id)

    async def update_job(
        self,
        job_id: str,
        status: Optional[str] = None,
        progress: Optional[dict] = None,
        result: Optional[dict] = None,
        error: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ) -> Optional[Job]:
        """Update job fields.

        Args:
            job_id: Job ID
            status: New status
            progress: Progress update
            result: Job result
            error: Error message
            started_at: Start timestamp
            completed_at: Completion timestamp

        Returns:
            Updated job if found, None otherwise
        """
        job = await self.get_job(job_id)
        if not job:
            return None

        if status is not None:
            job.status = status
        if progress is not None:
            job.progress = progress
        if result is not None:
            job.result = result
        if error is not None:
            job.error = error
        if started_at is not None:
            job.started_at = started_at
        if completed_at is not None:
            job.completed_at = completed_at

        await self.session.commit()
        await self.session.refresh(job)

        return job

    async def cancel_job(self, job_id: str) -> Optional[Job]:
        """Cancel a job.

        Args:
            job_id: Job ID

        Returns:
            Cancelled job if found, None otherwise
        """
        return await self.update_job(
            job_id,
            status="cancelled",
            completed_at=datetime.now(timezone.utc),
        )

    async def list_jobs(
        self,
        skip: int = 0,
        limit: int = 50,
        status: Optional[str] = None,
        job_type: Optional[str] = None,
    ) -> tuple[List[Job], int]:
        """List jobs with pagination and filtering.

        Args:
            skip: Number of jobs to skip
            limit: Maximum number of jobs to return
            status: Optional status filter
            job_type: Optional job type filter

        Returns:
            Tuple of (jobs list, total count)
        """
        # Build query
        query = select(Job)

        # Apply filters
        if status:
            query = query.where(Job.status == status)
        if job_type:
            query = query.where(Job.job_type == job_type)

        # Get total count
        from sqlalchemy import func

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        query = query.order_by(Job.created_at.desc()).offset(skip).limit(limit)

        # Execute
        result = await self.session.execute(query)
        jobs = list(result.scalars().all())

        return jobs, total
