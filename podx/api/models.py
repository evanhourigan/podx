"""API response models for structured return types.

This module provides Pydantic models for API responses to ensure:
- Type safety for API consumers
- Consistent response structure
- Easy serialization/deserialization
- Better IDE support and documentation
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class TranscribeResponse(BaseModel):
    """Response model for transcribe API.

    Attributes:
        transcript_path: Path to the generated transcript JSON file
        duration_seconds: Duration of the audio in seconds
        model_used: ASR model used for transcription
        segments_count: Number of segments in the transcript
        audio_path: Path to the processed audio file
        success: Whether the transcription was successful
        error: Error message if transcription failed
    """

    transcript_path: str = Field(
        ..., description="Path to the generated transcript JSON file"
    )
    duration_seconds: int = Field(
        ge=0, description="Duration of the audio in seconds"
    )
    model_used: Optional[str] = Field(
        None, description="ASR model used for transcription"
    )
    segments_count: Optional[int] = Field(
        None, ge=0, description="Number of segments in the transcript"
    )
    audio_path: Optional[str] = Field(
        None, description="Path to the processed audio file"
    )
    success: bool = Field(True, description="Whether the transcription was successful")
    error: Optional[str] = Field(None, description="Error message if failed")

    # Note: Removed path existence validation to allow flexibility in testing
    # and to avoid issues when paths may not yet exist

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        return self.model_dump(exclude_none=True)


class DeepcastResponse(BaseModel):
    """Response model for deepcast API.

    Attributes:
        markdown_path: Path to the generated markdown file
        json_path: Path to the generated JSON file
        usage: Token usage statistics (if available)
        prompt_used: The prompt that was used for analysis
        model_used: LLM model used for analysis
        analysis_type: Type of analysis performed (brief, quotes, outline, etc.)
        success: Whether the analysis was successful
        error: Error message if analysis failed
    """

    markdown_path: str = Field(..., description="Path to the generated markdown file")
    json_path: Optional[str] = Field(None, description="Path to the generated JSON file")
    usage: Optional[Dict[str, int]] = Field(
        None, description="Token usage statistics"
    )
    prompt_used: Optional[str] = Field(
        None, description="The prompt that was used for analysis"
    )
    model_used: Optional[str] = Field(
        None, description="LLM model used for analysis"
    )
    analysis_type: Optional[str] = Field(
        None, description="Type of analysis performed"
    )
    success: bool = Field(True, description="Whether the analysis was successful")
    error: Optional[str] = Field(None, description="Error message if failed")

    # Note: Removed path existence validation to allow flexibility in testing
    # and to avoid issues when paths may not yet exist

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        return self.model_dump(exclude_none=True)


class ExistsCheckResponse(BaseModel):
    """Response model for existence check APIs.

    Attributes:
        exists: Whether the resource exists
        path: Path to the resource (if exists)
        resource_type: Type of resource (transcript, markdown, etc.)
        metadata: Additional metadata about the resource
    """

    exists: bool = Field(..., description="Whether the resource exists")
    path: Optional[str] = Field(None, description="Path to the resource")
    resource_type: str = Field(..., description="Type of resource")
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional metadata"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        return self.model_dump(exclude_none=True)


@dataclass
class APIError:
    """Enhanced error information for API failures.

    Attributes:
        code: Error code for programmatic handling
        message: Human-readable error message
        details: Additional error context
        retry_after: Seconds to wait before retrying (if applicable)
        resolution: Suggested resolution steps
    """

    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    retry_after: Optional[int] = None
    resolution: Optional[str] = None

    def __str__(self) -> str:
        """String representation for logging."""
        parts = [f"[{self.code}] {self.message}"]
        if self.details:
            parts.append(f"Details: {self.details}")
        if self.resolution:
            parts.append(f"Resolution: {self.resolution}")
        return " | ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
            "retry_after": self.retry_after,
            "resolution": self.resolution,
        }


class ValidationResult(BaseModel):
    """Result of input validation.

    Attributes:
        valid: Whether the input is valid
        errors: List of validation errors
        warnings: List of validation warnings
    """

    valid: bool = Field(..., description="Whether the input is valid")
    errors: list[str] = Field(default_factory=list, description="Validation errors")
    warnings: list[str] = Field(default_factory=list, description="Validation warnings")

    def add_error(self, message: str) -> None:
        """Add a validation error."""
        self.errors.append(message)
        self.valid = False

    def add_warning(self, message: str) -> None:
        """Add a validation warning."""
        self.warnings.append(message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return self.model_dump()
