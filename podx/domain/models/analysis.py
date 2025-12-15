"""Analysis and deepcast result models."""

from typing import List, Optional

from pydantic import BaseModel, Field

from .transcript import Transcript


class DeepcastQuote(BaseModel):
    """A notable quote from the transcript."""

    quote: str = Field(..., description="The quoted text")
    time: Optional[str] = Field(None, description="Timestamp in HH:MM:SS format")
    speaker: Optional[str] = Field(None, description="Speaker identifier")

    model_config = {"extra": "forbid"}


class DeepcastOutlineItem(BaseModel):
    """An outline item with timestamp."""

    label: str = Field(..., description="Outline item description")
    time: Optional[str] = Field(None, description="Timestamp in HH:MM:SS format")

    model_config = {"extra": "forbid"}


class DeepcastBrief(BaseModel):
    """AI-generated analysis of the transcript."""

    markdown: str = Field(..., description="Full markdown analysis")
    summary: Optional[str] = Field(None, description="Episode summary")
    key_points: List[str] = Field(default_factory=list, description="Key points")
    gold_nuggets: List[str] = Field(default_factory=list, description="Notable insights")
    quotes: List[DeepcastQuote] = Field(default_factory=list, description="Notable quotes")
    actions: List[str] = Field(default_factory=list, description="Action items")
    outline: List[DeepcastOutlineItem] = Field(
        default_factory=list, description="Timestamp outline"
    )
    metadata: Optional[Transcript] = Field(None, description="Source transcript metadata")

    model_config = {"extra": "forbid"}
