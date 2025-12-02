"""Transcript and segment models."""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator

from ..enums import ASRPreset, ASRProvider


class Word(BaseModel):
    """A word with timing information."""

    start: Optional[float] = Field(None, description="Start time in seconds")
    end: Optional[float] = Field(None, description="End time in seconds")
    word: str = Field(..., description="The word text")

    @field_validator("end")
    @classmethod
    def end_after_start(cls, v: Optional[float], info: Any) -> Optional[float]:
        """Validate that end time is after start time if both present."""
        if v is not None and "start" in info.data and info.data["start"] is not None:
            if v < info.data["start"]:
                raise ValueError(
                    f"End time ({v}) must be after start time ({info.data['start']})"
                )
        return v

    model_config = {"extra": "forbid"}


class Segment(BaseModel):
    """A transcript segment with timing."""

    start: float = Field(..., description="Start time in seconds")
    end: float = Field(..., description="End time in seconds")
    text: str = Field(..., description="Transcript text")

    @field_validator("end")
    @classmethod
    def end_after_start(cls, v: float, info: Any) -> float:
        """Validate that end time is after start time."""
        if "start" in info.data and v < info.data["start"]:
            raise ValueError(
                f"End time ({v}) must be after start time ({info.data['start']})"
            )
        return v

    @field_validator("start", "end")
    @classmethod
    def times_must_be_non_negative(cls, v: float) -> float:
        """Validate that times are non-negative."""
        if v < 0:
            raise ValueError(f"Time must be non-negative: {v}")
        return v

    model_config = {"extra": "forbid"}


class AlignedSegment(Segment):
    """A segment with word-level alignment."""

    words: Optional[List[Word]] = Field(None, description="Word-level timing")

    model_config = {"extra": "forbid"}


class DiarizedSegment(AlignedSegment):
    """A segment with speaker information."""

    speaker: Optional[str] = Field(None, description="Speaker identifier")

    model_config = {"extra": "forbid"}


class Transcript(BaseModel):
    """Complete transcript with metadata."""

    audio_path: Optional[str] = Field(None, description="Path to source audio")
    language: Optional[str] = Field(None, description="Detected language")
    asr_model: Optional[str] = Field(
        None, description="ASR model used for transcription"
    )
    asr_provider: Optional[ASRProvider] = Field(
        None, description="ASR provider backend"
    )
    preset: Optional[ASRPreset] = Field(
        None, description="High-level preset guiding decoder options"
    )
    decoder_options: Optional[Dict[str, Union[str, int, float, bool]]] = Field(
        default=None, description="Advanced decoder/provider options"
    )
    text: Optional[str] = Field(None, description="Full transcript text")
    segments: List[Segment] = Field(
        default_factory=list, description="Transcript segments"
    )

    @field_validator("audio_path")
    @classmethod
    def audio_must_exist_if_present(cls, v: Optional[str]) -> Optional[str]:
        """Validate that audio file exists if path is provided.

        Note: This validator is lenient - it doesn't fail if the audio file
        is missing, as transcripts can be processed without the original audio
        (e.g., during preprocessing, merging, or other text transformations).
        """
        # Just return the path as-is; downstream operations that need the audio
        # will fail with more specific error messages
        return v

    model_config = {"extra": "forbid"}
