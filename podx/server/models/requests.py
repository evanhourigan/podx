"""Pydantic request models for PodX API."""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class JobCreate(BaseModel):
    """Base model for creating a job."""

    job_type: str = Field(
        ..., description="Type of job (transcribe, diarize, deepcast, pipeline)"
    )
    input_params: Dict[str, Any] = Field(
        default_factory=dict, description="Job-specific input parameters"
    )


class TranscribeRequest(BaseModel):
    """Request model for transcription jobs."""

    audio_url: Optional[str] = Field(None, description="URL to audio file")
    upload_id: Optional[str] = Field(None, description="ID of uploaded file")
    model: str = Field(default="base", description="Whisper model to use")
    language: Optional[str] = Field(None, description="Language code (e.g., 'en')")
    api_keys: Dict[str, str] = Field(
        default_factory=dict, description="User-provided API keys (openai, etc.)"
    )


class DiarizeRequest(BaseModel):
    """Request model for diarization jobs."""

    audio_url: Optional[str] = Field(None, description="URL to audio file")
    upload_id: Optional[str] = Field(None, description="ID of uploaded file")
    num_speakers: Optional[int] = Field(None, description="Expected number of speakers")
    api_keys: Dict[str, str] = Field(
        default_factory=dict, description="User-provided API keys"
    )


class DeepcastRequest(BaseModel):
    """Request model for deepcast jobs."""

    transcript_path: str = Field(..., description="Path to transcript file")
    prompt: Optional[str] = Field(None, description="Custom LLM prompt")
    model: str = Field(default="gpt-4", description="LLM model to use")
    api_keys: Dict[str, str] = Field(
        default_factory=dict,
        description="User-provided API keys (openai, anthropic, etc.)",
    )


class PipelineRequest(BaseModel):
    """Request model for full pipeline jobs."""

    audio_url: Optional[str] = Field(None, description="URL to audio file")
    upload_id: Optional[str] = Field(None, description="ID of uploaded file")
    transcribe_model: str = Field(
        default="base", description="Whisper model for transcription"
    )
    diarize: bool = Field(default=True, description="Enable diarization")
    deepcast: bool = Field(default=True, description="Enable deepcast analysis")
    export_formats: list[str] = Field(
        default_factory=lambda: ["json"],
        description="Export formats (json, pdf, notion, etc.)",
    )
    api_keys: Dict[str, str] = Field(
        default_factory=dict, description="User-provided API keys"
    )
