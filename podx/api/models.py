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
    duration_seconds: int = Field(ge=0, description="Duration of the audio in seconds")
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


class AnalyzeResponse(BaseModel):
    """Response model for analyze API.

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
    json_path: Optional[str] = Field(
        None, description="Path to the generated JSON file"
    )
    usage: Optional[Dict[str, int]] = Field(None, description="Token usage statistics")
    prompt_used: Optional[str] = Field(
        None, description="The prompt that was used for analysis"
    )
    model_used: Optional[str] = Field(None, description="LLM model used for analysis")
    analysis_type: Optional[str] = Field(None, description="Type of analysis performed")
    success: bool = Field(True, description="Whether the analysis was successful")
    error: Optional[str] = Field(None, description="Error message if failed")

    # Note: Removed path existence validation to allow flexibility in testing
    # and to avoid issues when paths may not yet exist

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        return self.model_dump(exclude_none=True)


# Backwards compatibility alias
DeepcastResponse = AnalyzeResponse


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
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

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


class FetchResponse(BaseModel):
    """Response model for fetch_episode API.

    Attributes:
        episode_meta: Episode metadata (title, show, date, etc.)
        audio_meta: Audio file metadata (path, format, duration)
        audio_path: Path to the downloaded audio file
        metadata_path: Path to the episode metadata JSON file
        success: Whether the fetch was successful
        error: Error message if fetch failed
    """

    episode_meta: Dict[str, Any] = Field(..., description="Episode metadata")
    audio_meta: Optional[Dict[str, Any]] = Field(
        None, description="Audio file metadata"
    )
    audio_path: str = Field(..., description="Path to the downloaded audio file")
    metadata_path: Optional[str] = Field(None, description="Path to metadata JSON")
    success: bool = Field(True, description="Whether the fetch was successful")
    error: Optional[str] = Field(None, description="Error message if failed")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        return self.model_dump(exclude_none=True)


class DiarizeResponse(BaseModel):
    """Response model for diarize API.

    Attributes:
        transcript_path: Path to the diarized transcript JSON file
        speakers_found: Number of unique speakers identified
        transcript: Full transcript data with speaker labels
        success: Whether diarization was successful
        error: Error message if diarization failed
    """

    transcript_path: str = Field(..., description="Path to diarized transcript JSON")
    speakers_found: int = Field(
        ge=0, description="Number of unique speakers identified"
    )
    transcript: Optional[Dict[str, Any]] = Field(
        None, description="Full transcript data"
    )
    success: bool = Field(True, description="Whether diarization was successful")
    error: Optional[str] = Field(None, description="Error message if failed")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        return self.model_dump(exclude_none=True)


class ExportResponse(BaseModel):
    """Response model for export API.

    Attributes:
        output_files: Dict mapping format to output file path
        formats: List of formats that were exported
        success: Whether the export was successful
        error: Error message if export failed
    """

    output_files: Dict[str, str] = Field(..., description="Format to file path mapping")
    formats: list[str] = Field(..., description="List of exported formats")
    success: bool = Field(True, description="Whether export was successful")
    error: Optional[str] = Field(None, description="Error message if failed")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        return self.model_dump(exclude_none=True)


class NotionResponse(BaseModel):
    """Response model for publish_to_notion API.

    Attributes:
        page_url: URL of the created/updated Notion page
        page_id: Notion page ID
        database_id: Notion database ID where page was created
        success: Whether the publish was successful
        error: Error message if publish failed
    """

    page_url: str = Field(..., description="URL of the Notion page")
    page_id: str = Field(..., description="Notion page ID")
    database_id: Optional[str] = Field(None, description="Notion database ID")
    success: bool = Field(True, description="Whether publish was successful")
    error: Optional[str] = Field(None, description="Error message if failed")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        return self.model_dump(exclude_none=True)


class ModelPricingInfo(BaseModel):
    """Pricing information for a model.

    Attributes:
        input_per_1m: Cost per 1 million input tokens (USD)
        output_per_1m: Cost per 1 million output tokens (USD)
        currency: Currency code (always "USD")
        tier: Pricing tier (e.g., "standard", "batch")
        notes: Additional pricing notes (e.g., caching discounts)
    """

    input_per_1m: float = Field(..., description="Cost per 1M input tokens")
    output_per_1m: float = Field(..., description="Cost per 1M output tokens")
    currency: str = Field("USD", description="Currency code")
    tier: str = Field("standard", description="Pricing tier")
    notes: Optional[str] = Field(None, description="Additional pricing notes")


class ModelInfo(BaseModel):
    """Response model for get_model_info API.

    Provides detailed information about a language model including pricing,
    capabilities, and provider information.

    Attributes:
        id: Canonical model identifier (e.g., "gpt-5.1")
        name: Human-readable model name (e.g., "GPT-5.1")
        provider: Provider key (e.g., "openai", "anthropic")
        aliases: Alternative identifiers for this model
        description: Brief description of the model
        pricing: Pricing information
        context_window: Maximum context length in tokens
        capabilities: List of capabilities (e.g., "vision", "function-calling")
        default_in_cli: Whether this model appears in default CLI listings
    """

    id: str = Field(..., description="Canonical model identifier")
    name: str = Field(..., description="Human-readable model name")
    provider: str = Field(..., description="Provider key")
    aliases: list[str] = Field(
        default_factory=list, description="Alternative identifiers"
    )
    description: str = Field(..., description="Brief model description")
    pricing: ModelPricingInfo = Field(..., description="Pricing information")
    context_window: Optional[int] = Field(
        None, description="Maximum context length in tokens (None for ASR models)"
    )
    capabilities: list[str] = Field(
        default_factory=list, description="Model capabilities"
    )
    default_in_cli: bool = Field(False, description="Appears in default CLI listings")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        return self.model_dump(exclude_none=True)

    @classmethod
    def from_catalog_model(cls, model: Any) -> "ModelInfo":
        """Create ModelInfo from internal catalog Model dataclass.

        Args:
            model: Model dataclass from podx.models.catalog

        Returns:
            ModelInfo instance
        """
        return cls(
            id=model.id,
            name=model.name,
            provider=model.provider,
            aliases=model.aliases,
            description=model.description,
            pricing=ModelPricingInfo(
                input_per_1m=model.pricing.input_per_1m,
                output_per_1m=model.pricing.output_per_1m,
                currency=model.pricing.currency,
                tier=model.pricing.tier,
                notes=model.pricing.notes,
            ),
            context_window=model.context_window,
            capabilities=model.capabilities,
            default_in_cli=model.default_in_cli,
        )


class CostEstimate(BaseModel):
    """Response model for estimate_cost API.

    Provides cost estimation for processing a transcript with a specific model.

    Attributes:
        model_id: Model used for estimation
        model_name: Human-readable model name
        input_tokens: Estimated input token count
        output_tokens: Estimated output token count (based on typical response ratio)
        input_cost_usd: Cost for input tokens
        output_cost_usd: Cost for output tokens
        total_cost_usd: Total estimated cost
        currency: Currency code (always "USD")
        transcript_path: Path to transcript (if provided)
        text_length: Length of input text in characters
        notes: Additional notes about the estimate
    """

    model_id: str = Field(..., description="Model used for estimation")
    model_name: str = Field(..., description="Human-readable model name")
    input_tokens: int = Field(..., ge=0, description="Estimated input token count")
    output_tokens: int = Field(..., ge=0, description="Estimated output token count")
    input_cost_usd: float = Field(..., ge=0, description="Cost for input tokens")
    output_cost_usd: float = Field(..., ge=0, description="Cost for output tokens")
    total_cost_usd: float = Field(..., ge=0, description="Total estimated cost")
    currency: str = Field("USD", description="Currency code")
    transcript_path: Optional[str] = Field(None, description="Path to transcript file")
    text_length: int = Field(..., ge=0, description="Input text length in characters")
    notes: Optional[str] = Field(None, description="Additional estimation notes")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        return self.model_dump(exclude_none=True)
