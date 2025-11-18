"""Job management endpoints for PodX API."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from podx.server.database import get_session
from podx.server.exceptions import InvalidInputException, JobNotFoundException
from podx.server.models import Job, JobCreateResponse, JobListResponse, JobResponse

router = APIRouter()


@router.post("/api/v1/jobs", response_model=JobCreateResponse, status_code=201)
async def create_job(
    job_type: str,
    input_params: Optional[dict] = None,
    session: AsyncSession = Depends(get_session),
) -> JobCreateResponse:
    """Create a new job.

    Args:
        job_type: Type of job (transcribe, diarize, deepcast, pipeline)
        input_params: Job-specific input parameters
        session: Database session

    Returns:
        Created job information

    Raises:
        InvalidInputException: If job_type is invalid
    """
    # Validate job type
    valid_job_types = {"transcribe", "diarize", "deepcast", "pipeline"}
    if job_type not in valid_job_types:
        raise InvalidInputException(
            f"Invalid job_type '{job_type}'. Must be one of: {', '.join(valid_job_types)}", field="job_type"
        )

    # Generate job ID
    job_id = str(uuid.uuid4())

    # Create job
    job = Job(
        id=job_id,
        status="queued",
        job_type=job_type,
        input_params=input_params or {},
    )

    session.add(job)
    await session.commit()
    await session.refresh(job)

    return JobCreateResponse(job_id=job.id, status=job.status)


@router.get("/api/v1/jobs", response_model=JobListResponse)
async def list_jobs(
    skip: int = Query(0, ge=0, description="Number of jobs to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of jobs to return"),
    status: Optional[str] = Query(None, description="Filter by status"),
    job_type: Optional[str] = Query(None, description="Filter by job type"),
    session: AsyncSession = Depends(get_session),
) -> JobListResponse:
    """List jobs with pagination and filtering.

    Args:
        skip: Number of jobs to skip (for pagination)
        limit: Maximum number of jobs to return (1-100)
        status: Optional status filter
        job_type: Optional job type filter
        session: Database session

    Returns:
        List of jobs with pagination info
    """
    # Build query
    query = select(Job)

    # Apply filters
    if status:
        query = query.where(Job.status == status)
    if job_type:
        query = query.where(Job.job_type == job_type)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination and order by created_at descending (newest first)
    query = query.order_by(Job.created_at.desc()).offset(skip).limit(limit)

    # Execute query
    result = await session.execute(query)
    jobs = result.scalars().all()

    # Convert to response models
    job_responses = [JobResponse.model_validate(job) for job in jobs]

    return JobListResponse(jobs=job_responses, total=total, skip=skip, limit=limit)


@router.get("/api/v1/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, session: AsyncSession = Depends(get_session)) -> JobResponse:
    """Get job status and details.

    Args:
        job_id: Job ID
        session: Database session

    Returns:
        Job details

    Raises:
        JobNotFoundException: If job not found
    """
    job = await session.get(Job, job_id)

    if not job:
        raise JobNotFoundException(job_id)

    return JobResponse.model_validate(job)


@router.delete("/api/v1/jobs/{job_id}", status_code=204)
async def cancel_job(job_id: str, session: AsyncSession = Depends(get_session)) -> None:
    """Cancel a job.

    Marks the job as cancelled if it's queued or running.
    Deletes the job if it's already completed or failed.

    Args:
        job_id: Job ID
        session: Database session

    Raises:
        JobNotFoundException: If job not found
    """
    job = await session.get(Job, job_id)

    if not job:
        raise JobNotFoundException(job_id)

    # If job is queued or running, mark as cancelled
    if job.status in ("queued", "running"):
        job.status = "cancelled"
        job.completed_at = datetime.now(timezone.utc)
        await session.commit()
    else:
        # If already completed/failed/cancelled, delete it
        await session.delete(job)
        await session.commit()
