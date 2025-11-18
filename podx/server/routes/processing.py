"""Processing endpoints for PodX API.

Provides endpoints for transcribe, diarize, deepcast, and pipeline operations.
Each endpoint creates a job and returns the job ID for tracking.
"""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from podx.server.database import get_session
from podx.server.services import JobManager

router = APIRouter()


class TranscribeRequest(BaseModel):
    """Request body for transcription."""

    audio_url: str = Field(..., description="URL or path to audio file")
    model: str = Field("base", description="Whisper model to use (tiny, base, small, medium, large)")


class DiarizeRequest(BaseModel):
    """Request body for diarization."""

    audio_url: str = Field(..., description="URL or path to audio file")
    num_speakers: Optional[int] = Field(None, description="Number of speakers (optional)")


class DeepcastRequest(BaseModel):
    """Request body for deepcast analysis."""

    transcript_path: str = Field(..., description="Path to transcript JSON file")


class PipelineRequest(BaseModel):
    """Request body for full pipeline."""

    audio_url: str = Field(..., description="URL or path to audio file")
    model: str = Field("base", description="Whisper model to use")
    num_speakers: Optional[int] = Field(None, description="Number of speakers (optional)")


class ProcessingResponse(BaseModel):
    """Response for processing requests."""

    job_id: str = Field(..., description="Job ID for tracking progress")
    status: str = Field(..., description="Initial job status (queued)")


@router.post("/api/v1/transcribe", response_model=ProcessingResponse, status_code=202)
async def transcribe(
    request: TranscribeRequest,
    session: AsyncSession = Depends(get_session),
) -> ProcessingResponse:
    """Start a transcription job.

    Args:
        request: Transcription parameters
        session: Database session

    Returns:
        Job ID and status
    """
    job_manager = JobManager(session)
    job = await job_manager.create_job(
        job_type="transcribe",
        input_params={
            "audio_url": request.audio_url,
            "model": request.model,
        },
    )

    return ProcessingResponse(job_id=job.id, status=job.status)


@router.post("/api/v1/diarize", response_model=ProcessingResponse, status_code=202)
async def diarize(
    request: DiarizeRequest,
    session: AsyncSession = Depends(get_session),
) -> ProcessingResponse:
    """Start a diarization job.

    Args:
        request: Diarization parameters
        session: Database session

    Returns:
        Job ID and status
    """
    job_manager = JobManager(session)
    params = {"audio_url": request.audio_url}
    if request.num_speakers is not None:
        params["num_speakers"] = request.num_speakers

    job = await job_manager.create_job(
        job_type="diarize",
        input_params=params,
    )

    return ProcessingResponse(job_id=job.id, status=job.status)


@router.post("/api/v1/deepcast", response_model=ProcessingResponse, status_code=202)
async def deepcast(
    request: DeepcastRequest,
    session: AsyncSession = Depends(get_session),
) -> ProcessingResponse:
    """Start a deepcast analysis job.

    Args:
        request: Deepcast parameters
        session: Database session

    Returns:
        Job ID and status
    """
    job_manager = JobManager(session)
    job = await job_manager.create_job(
        job_type="deepcast",
        input_params={"transcript_path": request.transcript_path},
    )

    return ProcessingResponse(job_id=job.id, status=job.status)


@router.post("/api/v1/pipeline", response_model=ProcessingResponse, status_code=202)
async def pipeline(
    request: PipelineRequest,
    session: AsyncSession = Depends(get_session),
) -> ProcessingResponse:
    """Start a full pipeline job (transcribe + diarize + deepcast).

    Args:
        request: Pipeline parameters
        session: Database session

    Returns:
        Job ID and status
    """
    job_manager = JobManager(session)
    params = {
        "audio_url": request.audio_url,
        "model": request.model,
    }
    if request.num_speakers is not None:
        params["num_speakers"] = request.num_speakers

    job = await job_manager.create_job(
        job_type="pipeline",
        input_params=params,
    )

    return ProcessingResponse(job_id=job.id, status=job.status)
