"""Server-Sent Events (SSE) streaming endpoints for PodX API.

Provides real-time progress updates for jobs via SSE.
"""

import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from podx.logging import get_logger
from podx.server.database import get_session
from podx.server.exceptions import JobNotFoundException
from podx.server.services import JobManager
from podx.server.services.events import get_broadcaster

logger = get_logger(__name__)

router = APIRouter()


async def generate_job_progress_events(
    job_id: str,
    session: AsyncSession,
) -> AsyncGenerator[str, None]:
    """Generate SSE events for job progress using event broadcaster.

    Args:
        job_id: Job ID to stream progress for
        session: Database session

    Yields:
        SSE formatted event strings
    """
    job_manager = JobManager(session)
    broadcaster = get_broadcaster()

    # Get initial job state
    job = await job_manager.get_job(job_id)
    if not job:
        yield f"event: error\ndata: {json.dumps({'error': 'Job not found'})}\n\n"
        return

    # Send initial job state
    initial_data = {"status": job.status, "progress": job.progress}
    yield f"event: job_status\ndata: {json.dumps(initial_data)}\n\n"

    # If job is already complete, send completion and exit
    if job.status not in ("queued", "running"):
        yield f"event: complete\ndata: {json.dumps({'status': job.status})}\n\n"
        return

    # Subscribe to real-time events
    try:
        # Subscribe to progress events
        async for event in broadcaster.subscribe(job_id):
            # Format event data
            event_data: dict = {}

            if event.status:
                event_data["status"] = event.status

            if event.percentage is not None:
                event_data["progress"] = {
                    "percentage": event.percentage,
                    "message": event.message,
                    "step": event.step,
                }

            if event.result:
                event_data["result"] = event.result

            if event.error:
                event_data["error"] = event.error

            # Send event
            yield f"event: job_status\ndata: {json.dumps(event_data)}\n\n"

            # Send completion event if job is done
            if event.status in ("completed", "failed", "cancelled"):
                yield f"event: complete\ndata: {json.dumps({'status': event.status})}\n\n"
                break

    except Exception as e:
        logger.error(f"Error streaming job {job_id}: {e}", exc_info=True)
        yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"


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
