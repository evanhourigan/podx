"""Processing endpoints for PodX API.

Provides endpoints for transcribe, diarize, deepcast, and pipeline operations.
Each endpoint creates a job and returns the job ID for tracking.
"""

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from podx.server.database import get_session
from podx.server.middleware.rate_limit import get_rate_limit_config, limiter
from podx.server.services import JobManager
from podx.server.storage import save_upload_file

router = APIRouter()

# Get rate limit configuration
general_limit, upload_limit = get_rate_limit_config()


class TranscribeRequest(BaseModel):
    """Request body for transcription."""

    audio_url: str = Field(..., description="URL or path to audio file")
    model: str = Field(
        "base", description="Whisper model to use (tiny, base, small, medium, large)"
    )

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        """Validate Whisper model name."""
        valid_models = {"tiny", "base", "small", "medium", "large"}
        if v not in valid_models:
            raise ValueError(
                f"Invalid model '{v}'. Must be one of: {', '.join(valid_models)}"
            )
        return v

    @field_validator("audio_url")
    @classmethod
    def validate_audio_url(cls, v: str) -> str:
        """Validate audio URL is not empty."""
        if not v or not v.strip():
            raise ValueError("audio_url cannot be empty")
        return v.strip()


class DiarizeRequest(BaseModel):
    """Request body for diarization."""

    audio_url: str = Field(..., description="URL or path to audio file")
    num_speakers: Optional[int] = Field(
        None, description="Number of speakers (optional)", ge=2, le=10
    )

    @field_validator("audio_url")
    @classmethod
    def validate_audio_url(cls, v: str) -> str:
        """Validate audio URL is not empty."""
        if not v or not v.strip():
            raise ValueError("audio_url cannot be empty")
        return v.strip()


class DeepcastRequest(BaseModel):
    """Request body for deepcast analysis."""

    transcript_path: str = Field(..., description="Path to transcript JSON file")


class PipelineRequest(BaseModel):
    """Request body for full pipeline."""

    audio_url: str = Field(..., description="URL or path to audio file")
    model: str = Field("base", description="Whisper model to use")
    num_speakers: Optional[int] = Field(
        None, description="Number of speakers (optional)", ge=2, le=10
    )

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        """Validate Whisper model name."""
        valid_models = {"tiny", "base", "small", "medium", "large"}
        if v not in valid_models:
            raise ValueError(
                f"Invalid model '{v}'. Must be one of: {', '.join(valid_models)}"
            )
        return v

    @field_validator("audio_url")
    @classmethod
    def validate_audio_url(cls, v: str) -> str:
        """Validate audio URL is not empty."""
        if not v or not v.strip():
            raise ValueError("audio_url cannot be empty")
        return v.strip()


class ProcessingResponse(BaseModel):
    """Response for processing requests."""

    job_id: str = Field(..., description="Job ID for tracking progress")
    status: str = Field(..., description="Initial job status (queued)")


@router.post("/api/v1/transcribe", response_model=ProcessingResponse, status_code=202)
@limiter.limit(general_limit)
async def transcribe(
    request: Request,
    body: TranscribeRequest,
    session: AsyncSession = Depends(get_session),
) -> ProcessingResponse:
    """Start a transcription job.

    Args:
        request: FastAPI request object (for rate limiting)
        body: Transcription parameters
        session: Database session

    Returns:
        Job ID and status
    """
    job_manager = JobManager(session)
    job = await job_manager.create_job(
        job_type="transcribe",
        input_params={
            "audio_url": body.audio_url,
            "model": body.model,
        },
    )

    return ProcessingResponse(job_id=job.id, status=job.status)


@router.post("/api/v1/diarize", response_model=ProcessingResponse, status_code=202)
@limiter.limit(general_limit)
async def diarize(
    request: Request,
    body: DiarizeRequest,
    session: AsyncSession = Depends(get_session),
) -> ProcessingResponse:
    """Start a diarization job.

    Args:
        request: FastAPI request object (for rate limiting)
        body: Diarization parameters
        session: Database session

    Returns:
        Job ID and status
    """
    job_manager = JobManager(session)
    params = {"audio_url": body.audio_url}
    if body.num_speakers is not None:
        params["num_speakers"] = body.num_speakers

    job = await job_manager.create_job(
        job_type="diarize",
        input_params=params,
    )

    return ProcessingResponse(job_id=job.id, status=job.status)


@router.post("/api/v1/deepcast", response_model=ProcessingResponse, status_code=202)
@limiter.limit(general_limit)
async def deepcast(
    request: Request,
    body: DeepcastRequest,
    session: AsyncSession = Depends(get_session),
) -> ProcessingResponse:
    """Start a deepcast analysis job.

    Args:
        request: FastAPI request object (for rate limiting)
        body: Deepcast parameters
        session: Database session

    Returns:
        Job ID and status
    """
    job_manager = JobManager(session)
    job = await job_manager.create_job(
        job_type="deepcast",
        input_params={"transcript_path": body.transcript_path},
    )

    return ProcessingResponse(job_id=job.id, status=job.status)


@router.post("/api/v1/pipeline", response_model=ProcessingResponse, status_code=202)
@limiter.limit(general_limit)
async def pipeline(
    request: Request,
    body: PipelineRequest,
    session: AsyncSession = Depends(get_session),
) -> ProcessingResponse:
    """Start a full pipeline job (transcribe + diarize + deepcast).

    Args:
        request: FastAPI request object (for rate limiting)
        body: Pipeline parameters
        session: Database session

    Returns:
        Job ID and status
    """
    job_manager = JobManager(session)
    params = {
        "audio_url": body.audio_url,
        "model": body.model,
    }
    if body.num_speakers is not None:
        params["num_speakers"] = body.num_speakers

    job = await job_manager.create_job(
        job_type="pipeline",
        input_params=params,
    )

    return ProcessingResponse(job_id=job.id, status=job.status)


# File upload endpoints


@router.post(
    "/api/v1/transcribe/upload", response_model=ProcessingResponse, status_code=202
)
@limiter.limit(upload_limit)
async def transcribe_upload(
    request: Request,
    file: UploadFile = File(...),
    model: str = Form("base"),
    session: AsyncSession = Depends(get_session),
) -> ProcessingResponse:
    """Start a transcription job with file upload.

    Args:
        file: Audio file to transcribe
        model: Whisper model to use
        session: Database session

    Returns:
        Job ID and status
    """
    # Save uploaded file
    file_path = save_upload_file(file.file, file.filename or "audio.mp3")

    # Create job
    job_manager = JobManager(session)
    job = await job_manager.create_job(
        job_type="transcribe",
        input_params={
            "audio_url": file_path,
            "model": model,
        },
    )

    return ProcessingResponse(job_id=job.id, status=job.status)


@router.post(
    "/api/v1/diarize/upload", response_model=ProcessingResponse, status_code=202
)
@limiter.limit(upload_limit)
async def diarize_upload(
    request: Request,
    file: UploadFile = File(...),
    num_speakers: Optional[int] = Form(None),
    session: AsyncSession = Depends(get_session),
) -> ProcessingResponse:
    """Start a diarization job with file upload.

    Args:
        file: Audio file to diarize
        num_speakers: Number of speakers (optional)
        session: Database session

    Returns:
        Job ID and status
    """
    # Save uploaded file
    file_path = save_upload_file(file.file, file.filename or "audio.mp3")

    # Create job
    job_manager = JobManager(session)
    params = {"audio_url": file_path}
    if num_speakers is not None:
        params["num_speakers"] = num_speakers

    job = await job_manager.create_job(
        job_type="diarize",
        input_params=params,
    )

    return ProcessingResponse(job_id=job.id, status=job.status)


@router.post(
    "/api/v1/pipeline/upload", response_model=ProcessingResponse, status_code=202
)
@limiter.limit(upload_limit)
async def pipeline_upload(
    request: Request,
    file: UploadFile = File(...),
    model: str = Form("base"),
    num_speakers: Optional[int] = Form(None),
    session: AsyncSession = Depends(get_session),
) -> ProcessingResponse:
    """Start a full pipeline job with file upload.

    Args:
        file: Audio file to process
        model: Whisper model to use
        num_speakers: Number of speakers (optional)
        session: Database session

    Returns:
        Job ID and status
    """
    # Save uploaded file
    file_path = save_upload_file(file.file, file.filename or "audio.mp3")

    # Create job
    job_manager = JobManager(session)
    params = {
        "audio_url": file_path,
        "model": model,
    }
    if num_speakers is not None:
        params["num_speakers"] = num_speakers

    job = await job_manager.create_job(
        job_type="pipeline",
        input_params=params,
    )

    return ProcessingResponse(job_id=job.id, status=job.status)
