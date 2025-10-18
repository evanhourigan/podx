"""Episode and audio metadata models."""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from ..enums import AudioFormat


class EpisodeMeta(BaseModel):
    """Metadata for a podcast episode."""

    show: str = Field(..., description="Name of the podcast show")
    feed: str = Field(..., description="RSS feed URL")
    episode_title: str = Field(..., description="Title of the episode")
    episode_published: str = Field(..., description="Publication date")
    audio_path: str = Field(..., description="Path to downloaded audio file")
    image_url: Optional[str] = Field(None, description="Podcast artwork URL")

    @field_validator("audio_path")
    @classmethod
    def audio_must_exist(cls, v: str) -> str:
        """Validate that audio file exists."""
        if not Path(v).exists():
            raise ValueError(f"Audio file not found: {v}")
        return v

    @field_validator("feed")
    @classmethod
    def feed_must_be_url(cls, v: str) -> str:
        """Validate that feed is a proper URL."""
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError(f"Feed must be a valid URL: {v}")
        return v

    model_config = {"extra": "forbid"}


class AudioMeta(BaseModel):
    """Metadata for processed audio."""

    audio_path: str = Field(..., description="Path to audio file")
    sample_rate: Optional[int] = Field(None, description="Audio sample rate in Hz")
    channels: Optional[int] = Field(None, description="Number of audio channels")
    format: AudioFormat = Field(..., description="Audio format")

    @field_validator("audio_path")
    @classmethod
    def audio_must_exist(cls, v: str) -> str:
        """Validate that audio file exists."""
        if not Path(v).exists():
            raise ValueError(f"Audio file not found: {v}")
        return v

    @field_validator("sample_rate")
    @classmethod
    def sample_rate_must_be_positive(cls, v: Optional[int]) -> Optional[int]:
        """Validate sample rate is positive."""
        if v is not None and v <= 0:
            raise ValueError(f"Sample rate must be positive: {v}")
        return v

    @field_validator("channels")
    @classmethod
    def channels_must_be_positive(cls, v: Optional[int]) -> Optional[int]:
        """Validate channels is positive."""
        if v is not None and v <= 0:
            raise ValueError(f"Channels must be positive: {v}")
        return v

    model_config = {"extra": "forbid"}
