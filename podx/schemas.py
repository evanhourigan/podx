from pathlib import Path
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, validator


class EpisodeMeta(BaseModel):
    """Metadata for a podcast episode."""

    show: str = Field(..., description="Name of the podcast show")
    feed: str = Field(..., description="RSS feed URL")
    episode_title: str = Field(..., description="Title of the episode")
    episode_published: str = Field(..., description="Publication date")
    audio_path: str = Field(..., description="Path to downloaded audio file")
    image_url: Optional[str] = Field(None, description="Podcast artwork URL")

    @validator("audio_path")
    def audio_must_exist(cls, v):
        """Validate that audio file exists."""
        if not Path(v).exists():
            raise ValueError(f"Audio file not found: {v}")
        return v

    @validator("feed")
    def feed_must_be_url(cls, v):
        """Validate that feed is a proper URL."""
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError(f"Feed must be a valid URL: {v}")
        return v

    class Config:
        extra = "forbid"  # Don't allow extra fields


class AudioMeta(BaseModel):
    """Metadata for processed audio."""

    audio_path: str = Field(..., description="Path to audio file")
    sample_rate: Optional[int] = Field(None, description="Audio sample rate in Hz")
    channels: Optional[int] = Field(None, description="Number of audio channels")
    format: Literal["wav16", "mp3", "aac"] = Field(..., description="Audio format")

    @validator("audio_path")
    def audio_must_exist(cls, v):
        """Validate that audio file exists."""
        if not Path(v).exists():
            raise ValueError(f"Audio file not found: {v}")
        return v

    @validator("sample_rate")
    def sample_rate_must_be_positive(cls, v):
        """Validate sample rate is positive."""
        if v is not None and v <= 0:
            raise ValueError(f"Sample rate must be positive: {v}")
        return v

    @validator("channels")
    def channels_must_be_positive(cls, v):
        """Validate channels is positive."""
        if v is not None and v <= 0:
            raise ValueError(f"Channels must be positive: {v}")
        return v

    class Config:
        extra = "forbid"


class Segment(BaseModel):
    """A transcript segment with timing."""

    start: float = Field(..., description="Start time in seconds")
    end: float = Field(..., description="End time in seconds")
    text: str = Field(..., description="Transcript text")

    @validator("end")
    def end_after_start(cls, v, values):
        """Validate that end time is after start time."""
        if "start" in values and v < values["start"]:
            raise ValueError(
                f"End time ({v}) must be after start time ({values['start']})"
            )
        return v

    @validator("start", "end")
    def times_must_be_non_negative(cls, v):
        """Validate that times are non-negative."""
        if v < 0:
            raise ValueError(f"Time must be non-negative: {v}")
        return v

    class Config:
        extra = "forbid"


class Word(BaseModel):
    """A word with timing information."""

    start: Optional[float] = Field(None, description="Start time in seconds")
    end: Optional[float] = Field(None, description="End time in seconds")
    word: str = Field(..., description="The word text")

    @validator("end")
    def end_after_start(cls, v, values):
        """Validate that end time is after start time if both present."""
        if v is not None and "start" in values and values["start"] is not None:
            if v < values["start"]:
                raise ValueError(
                    f"End time ({v}) must be after start time ({values['start']})"
                )
        return v

    class Config:
        extra = "forbid"


class AlignedSegment(Segment):
    """A segment with word-level alignment."""

    words: Optional[List[Word]] = Field(None, description="Word-level timing")

    class Config:
        extra = "forbid"


class DiarizedSegment(AlignedSegment):
    """A segment with speaker information."""

    speaker: Optional[str] = Field(None, description="Speaker identifier")

    class Config:
        extra = "forbid"


class Transcript(BaseModel):
    """Complete transcript with metadata."""

    audio_path: Optional[str] = Field(None, description="Path to source audio")
    language: Optional[str] = Field(None, description="Detected language")
    text: Optional[str] = Field(None, description="Full transcript text")
    segments: List[Segment] = Field(
        default_factory=list, description="Transcript segments"
    )

    @validator("audio_path")
    def audio_must_exist_if_present(cls, v):
        """Validate that audio file exists if path is provided."""
        if v is not None and not Path(v).exists():
            raise ValueError(f"Audio file not found: {v}")
        return v

    class Config:
        extra = "forbid"


class DeepcastQuote(BaseModel):
    """A notable quote from the transcript."""

    quote: str = Field(..., description="The quoted text")
    time: Optional[str] = Field(None, description="Timestamp in HH:MM:SS format")
    speaker: Optional[str] = Field(None, description="Speaker identifier")

    class Config:
        extra = "forbid"


class DeepcastOutlineItem(BaseModel):
    """An outline item with timestamp."""

    label: str = Field(..., description="Outline item description")
    time: Optional[str] = Field(None, description="Timestamp in HH:MM:SS format")

    class Config:
        extra = "forbid"


class DeepcastBrief(BaseModel):
    """AI-generated analysis of the transcript."""

    markdown: str = Field(..., description="Full markdown analysis")
    summary: Optional[str] = Field(None, description="Episode summary")
    key_points: List[str] = Field(default_factory=list, description="Key points")
    gold_nuggets: List[str] = Field(
        default_factory=list, description="Notable insights"
    )
    quotes: List[DeepcastQuote] = Field(
        default_factory=list, description="Notable quotes"
    )
    actions: List[str] = Field(default_factory=list, description="Action items")
    outline: List[DeepcastOutlineItem] = Field(
        default_factory=list, description="Timestamp outline"
    )
    metadata: Optional[Transcript] = Field(
        None, description="Source transcript metadata"
    )

    class Config:
        extra = "forbid"
