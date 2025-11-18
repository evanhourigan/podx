"""Pydantic response models for PodX API."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class JobResponse(BaseModel):
    """Response model for a single job."""

    id: str = Field(..., description="Job ID")
    status: str = Field(..., description="Job status (queued, running, completed, failed, cancelled)")
    job_type: str = Field(..., description="Job type (transcribe, diarize, deepcast, pipeline)")
    input_params: Optional[Dict[str, Any]] = Field(None, description="Job input parameters")
    progress: Optional[Dict[str, Any]] = Field(None, description="Current progress information")
    result: Optional[Dict[str, Any]] = Field(None, description="Job result (when completed)")
    error: Optional[str] = Field(None, description="Error message (when failed)")
    created_at: datetime = Field(..., description="Job creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    started_at: Optional[datetime] = Field(None, description="Job start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Job completion timestamp")

    model_config = ConfigDict(from_attributes=True)  # Allow creation from ORM models


class JobListResponse(BaseModel):
    """Response model for listing jobs."""

    jobs: List[JobResponse] = Field(..., description="List of jobs")
    total: int = Field(..., description="Total number of jobs")
    skip: int = Field(..., description="Number of jobs skipped")
    limit: int = Field(..., description="Maximum number of jobs returned")


class ProgressEvent(BaseModel):
    """Server-Sent Event for job progress updates."""

    percentage: float = Field(..., description="Progress percentage (0.0 to 1.0)")
    step: Optional[str] = Field(None, description="Current processing step")
    message: Optional[str] = Field(None, description="Progress message")
    eta_seconds: Optional[int] = Field(None, description="Estimated time remaining in seconds")


class JobCreateResponse(BaseModel):
    """Response model for job creation."""

    job_id: str = Field(..., description="Created job ID")
    status: str = Field(..., description="Initial job status")
