"""Server-Sent Events (SSE) streaming endpoints for PodX API.

Provides real-time progress updates for jobs via SSE.
"""

import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from podx.logging import get_logger
from podx.server.database import get_session
from podx.server.exceptions import JobNotFoundException
from podx.server.services import JobManager

logger = get_logger(__name__)

router = APIRouter()


async def generate_job_progress_events(
    job_id: str,
    session: AsyncSession,
) -> AsyncGenerator[str, None]:
    """Generate SSE events for job progress.

    Args:
        job_id: Job ID to stream progress for
        session: Database session

    Yields:
        SSE formatted event strings
    """
    job_manager = JobManager(session)

    # Get initial job state
    job = await job_manager.get_job(job_id)
    if not job:
        yield f"event: error\ndata: {json.dumps({'error': 'Job not found'})}\n\n"
        return

    # Send initial job state
    yield f"event: job_status\ndata: {json.dumps({'status': job.status, 'progress': job.progress})}\n\n"

    # Poll for updates until job is complete
    last_status = job.status
    last_progress = job.progress

    while job.status in ("queued", "running"):
        # Wait a bit before checking again
        await asyncio.sleep(0.5)

        # Get updated job state
        await session.refresh(job)

        # Send update if status or progress changed
        if job.status != last_status or job.progress != last_progress:
            event_data = {
                "status": job.status,
                "progress": job.progress,
            }

            # Include result if completed
            if job.status == "completed":
                event_data["result"] = job.result

            # Include error if failed
            if job.status == "failed":
                event_data["error"] = job.error

            yield f"event: job_status\ndata: {json.dumps(event_data)}\n\n"

            last_status = job.status
            last_progress = job.progress

    # Send final completion event
    yield f"event: complete\ndata: {json.dumps({'status': job.status})}\n\n"


@router.get("/api/v1/jobs/{job_id}/stream")
async def stream_job_progress(
    job_id: str,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Stream job progress updates via Server-Sent Events.

    Args:
        job_id: Job ID to stream progress for
        session: Database session

    Returns:
        SSE streaming response

    Raises:
        JobNotFoundException: If job not found
    """
    # Verify job exists first
    job_manager = JobManager(session)
    job = await job_manager.get_job(job_id)
    if not job:
        raise JobNotFoundException(job_id)

    return StreamingResponse(
        generate_job_progress_events(job_id, session),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
