"""High-level API client for podx.

This module provides a clean, type-safe interface for podcast processing operations.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from ..errors import AIError, AudioError, NetworkError, ValidationError
from ..logging import get_logger
from .models import (
    APIError,
    DeepcastResponse,
    ExistsCheckResponse,
    TranscribeResponse,
    ValidationResult,
)

# Import the underlying API functions from legacy module
from .legacy import (
    transcribe as _transcribe,
    deepcast as _deepcast,
    has_transcript as _has_transcript,
    has_markdown as _has_markdown,
)

logger = get_logger(__name__)


@dataclass
class ClientConfig:
    """Configuration for PodxClient.

    Attributes:
        default_model: Default ASR model to use
        default_llm_model: Default LLM model for analysis
        output_dir: Default output directory for results
        cache_enabled: Whether to enable result caching
        retry_failed: Whether to retry failed operations
        validate_inputs: Whether to validate inputs before processing
        verbose: Enable verbose logging
    """

    default_model: str = "base"
    default_llm_model: str = "gpt-4o"
    output_dir: Optional[Path] = None
    cache_enabled: bool = True
    retry_failed: bool = True
    validate_inputs: bool = True
    verbose: bool = False


class PodxClient:
    """High-level client for podx API.

    This class provides a clean, type-safe interface for podcast processing operations.
    It wraps the underlying API functions with enhanced error handling, validation,
    and structured responses.

    Examples:
        Basic transcription:
        >>> client = PodxClient()
        >>> result = client.transcribe("audio.mp3")
        >>> print(result.transcript_path)

        Transcription with analysis:
        >>> result = client.transcribe_and_analyze("audio.mp3")
        >>> print(result.transcript.transcript_path)
        >>> print(result.analysis.markdown_path)

        Check for existing results:
        >>> exists = client.check_transcript_exists("episode_123", "base")
        >>> if exists.exists:
        ...     print(f"Transcript found at {exists.path}")
    """

    def __init__(self, config: Optional[ClientConfig] = None):
        """Initialize the client.

        Args:
            config: Client configuration (uses defaults if not provided)
        """
        self.config = config or ClientConfig()
        self._setup_logging()

    def _setup_logging(self) -> None:
        """Setup logging based on config."""
        # Note: structlog doesn't support setLevel like standard logging
        # Verbose mode is handled by the logging configuration
        pass

    def transcribe(
        self,
        audio_url: str,
        model: Optional[str] = None,
        out_dir: Optional[str] = None,
    ) -> TranscribeResponse:
        """Transcribe audio to text.

        Args:
            audio_url: URL or local path to audio file
            model: ASR model to use (defaults to config.default_model)
            out_dir: Output directory (defaults to config.output_dir)

        Returns:
            TranscribeResponse with transcript path and metadata

        Raises:
            ValidationError: If inputs are invalid
            AudioError: If audio processing fails
            NetworkError: If download fails
        """
        # Validate inputs
        if self.config.validate_inputs:
            validation = self._validate_transcribe_inputs(audio_url, model, out_dir)
            if not validation.valid:
                raise ValidationError(
                    f"Invalid inputs: {', '.join(validation.errors)}"
                )

        # Set defaults
        model = model or self.config.default_model
        out_dir = out_dir or str(self.config.output_dir or Path.cwd() / "output")

        # Check cache if enabled
        if self.config.cache_enabled:
            cached = self._check_cache(audio_url, model, out_dir)
            if cached:
                logger.info("Using cached transcript", path=cached.transcript_path)
                return cached

        try:
            # Call underlying API
            result = _transcribe(audio_url, model, out_dir)

            # Wrap in response model
            response = TranscribeResponse(
                transcript_path=result["transcript_path"],
                duration_seconds=result.get("duration_seconds", 0),
                model_used=model,
                audio_path=audio_url,
                success=True,
            )

            # Extract segments count
            try:
                transcript_data = json.loads(Path(response.transcript_path).read_text())
                response.segments_count = len(transcript_data.get("segments", []))
            except Exception:
                pass

            logger.info(
                "Transcription completed",
                path=response.transcript_path,
                duration=response.duration_seconds,
            )
            return response

        except Exception as e:
            error_response = self._handle_error(e, "transcribe")
            return TranscribeResponse(
                transcript_path="",
                duration_seconds=0,
                success=False,
                error=str(error_response),
            )

    def deepcast(
        self,
        transcript_path: str,
        llm_model: Optional[str] = None,
        out_dir: Optional[str] = None,
        provider_keys: Optional[Dict[str, str]] = None,
        prompt: Optional[str] = None,
        prompt_name: str = "default",
    ) -> DeepcastResponse:
        """Run deepcast analysis on a transcript.

        Args:
            transcript_path: Path to transcript JSON file
            llm_model: LLM model to use (defaults to config.default_llm_model)
            out_dir: Output directory (defaults to config.output_dir)
            provider_keys: API keys for LLM providers
            prompt: Custom prompt for analysis
            prompt_name: Name for the prompt (for caching/organization)

        Returns:
            DeepcastResponse with markdown path and metadata

        Raises:
            ValidationError: If inputs are invalid
            AIError: If analysis fails
        """
        # Validate inputs
        if self.config.validate_inputs:
            validation = self._validate_deepcast_inputs(
                transcript_path, llm_model, out_dir
            )
            if not validation.valid:
                raise ValidationError(
                    f"Invalid inputs: {', '.join(validation.errors)}"
                )

        # Set defaults
        llm_model = llm_model or self.config.default_llm_model
        out_dir = out_dir or str(self.config.output_dir or Path.cwd() / "output")

        try:
            # Call underlying API
            result = _deepcast(
                transcript_path=transcript_path,
                llm_model=llm_model,
                out_dir=out_dir,
                provider_keys=provider_keys,
                prompt=prompt,
                prompt_name=prompt_name,
            )

            # Wrap in response model
            response = DeepcastResponse(
                markdown_path=result["markdown_path"],
                usage=result.get("usage"),
                prompt_used=result.get("prompt_used"),
                model_used=llm_model,
                success=True,
            )

            logger.info(
                "Deepcast analysis completed",
                path=response.markdown_path,
                model=llm_model,
            )
            return response

        except Exception as e:
            error_response = self._handle_error(e, "deepcast")
            return DeepcastResponse(
                markdown_path="",
                success=False,
                error=str(error_response),
            )

    def transcribe_and_analyze(
        self,
        audio_url: str,
        asr_model: Optional[str] = None,
        llm_model: Optional[str] = None,
        out_dir: Optional[str] = None,
        provider_keys: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Transcribe audio and run deepcast analysis in one call.

        Args:
            audio_url: URL or local path to audio file
            asr_model: ASR model to use
            llm_model: LLM model to use
            out_dir: Output directory
            provider_keys: API keys for LLM providers

        Returns:
            Dict with transcript and analysis results
        """
        # Transcribe
        transcript_result = self.transcribe(audio_url, asr_model, out_dir)
        if not transcript_result.success:
            return {
                "transcript": transcript_result,
                "analysis": None,
                "success": False,
            }

        # Analyze
        analysis_result = self.deepcast(
            transcript_path=transcript_result.transcript_path,
            llm_model=llm_model,
            out_dir=out_dir,
            provider_keys=provider_keys,
        )

        return {
            "transcript": transcript_result,
            "analysis": analysis_result,
            "success": transcript_result.success and analysis_result.success,
        }

    def check_transcript_exists(
        self,
        episode_id: int | str,
        asr_model: str,
        out_dir: str,
    ) -> ExistsCheckResponse:
        """Check if a transcript already exists.

        Args:
            episode_id: Episode identifier
            asr_model: ASR model used
            out_dir: Output directory to check

        Returns:
            ExistsCheckResponse with existence information
        """
        try:
            path = _has_transcript(episode_id, asr_model, out_dir)
            exists = path is not None

            metadata = None
            if exists and path:
                try:
                    transcript_data = json.loads(Path(path).read_text())
                    metadata = {
                        "model": transcript_data.get("asr_model"),
                        "segments": len(transcript_data.get("segments", [])),
                        "duration": transcript_data.get("duration"),
                    }
                except Exception:
                    pass

            return ExistsCheckResponse(
                exists=exists,
                path=path,
                resource_type="transcript",
                metadata=metadata,
            )
        except Exception as e:
            logger.warning("Failed to check transcript existence", error=str(e))
            return ExistsCheckResponse(
                exists=False,
                path=None,
                resource_type="transcript",
            )

    def check_markdown_exists(
        self,
        episode_id: int | str,
        asr_model: str,
        llm_model: str,
        prompt_name: str,
        out_dir: str,
    ) -> ExistsCheckResponse:
        """Check if a deepcast markdown file already exists.

        Args:
            episode_id: Episode identifier
            asr_model: ASR model used
            llm_model: LLM model used
            prompt_name: Prompt name used
            out_dir: Output directory to check

        Returns:
            ExistsCheckResponse with existence information
        """
        try:
            path = _has_markdown(episode_id, asr_model, llm_model, prompt_name, out_dir)
            exists = path is not None

            return ExistsCheckResponse(
                exists=exists,
                path=path,
                resource_type="markdown",
            )
        except Exception as e:
            logger.warning("Failed to check markdown existence", error=str(e))
            return ExistsCheckResponse(
                exists=False,
                path=None,
                resource_type="markdown",
            )

    def _validate_transcribe_inputs(
        self, audio_url: str, model: Optional[str], out_dir: Optional[str]
    ) -> ValidationResult:
        """Validate inputs for transcribe API."""
        result = ValidationResult(valid=True)

        # Validate audio_url
        if not audio_url:
            result.add_error("audio_url cannot be empty")
        elif not re.match(r"^https?://", audio_url):
            # If not a URL, check if file exists (if it's an absolute path)
            audio_path = Path(audio_url)
            if audio_path.is_absolute() and not audio_path.exists():
                result.add_error(f"Audio file not found: {audio_url}")

        # Validate model (basic check)
        if model and not re.match(r"^[a-zA-Z0-9._-]+$", model):
            result.add_error(f"Invalid model name: {model}")

        return result

    def _validate_deepcast_inputs(
        self, transcript_path: str, llm_model: Optional[str], out_dir: Optional[str]
    ) -> ValidationResult:
        """Validate inputs for deepcast API."""
        result = ValidationResult(valid=True)

        # Validate transcript_path
        if not transcript_path:
            result.add_error("transcript_path cannot be empty")
        elif not Path(transcript_path).exists():
            result.add_error(f"Transcript file not found: {transcript_path}")

        # Validate LLM model
        if llm_model and not re.match(r"^[a-zA-Z0-9._-]+$", llm_model):
            result.add_error(f"Invalid LLM model name: {llm_model}")

        return result

    def _check_cache(
        self, audio_url: str, model: str, out_dir: str
    ) -> Optional[TranscribeResponse]:
        """Check if cached result exists."""
        # Simplified cache check - just look for existing transcript
        transcript_path = Path(out_dir) / "transcript.json"
        if transcript_path.exists():
            try:
                data = json.loads(transcript_path.read_text())
                return TranscribeResponse(
                    transcript_path=str(transcript_path),
                    duration_seconds=data.get("duration", 0),
                    model_used=model,
                    segments_count=len(data.get("segments", [])),
                    audio_path=audio_url,
                    success=True,
                )
            except Exception:
                pass
        return None

    def _handle_error(self, error: Exception, operation: str) -> APIError:
        """Handle errors and convert to APIError."""
        if isinstance(error, ValidationError):
            return APIError(
                code="VALIDATION_ERROR",
                message=str(error),
                resolution="Check input parameters and try again",
            )
        elif isinstance(error, NetworkError):
            return APIError(
                code="NETWORK_ERROR",
                message=str(error),
                retry_after=30,
                resolution="Check network connection and retry",
            )
        elif isinstance(error, AudioError):
            return APIError(
                code="AUDIO_ERROR",
                message=str(error),
                resolution="Check audio file format and try again",
            )
        elif isinstance(error, AIError):
            return APIError(
                code="AI_ERROR",
                message=str(error),
                resolution="Check API keys and model availability",
            )
        else:
            logger.error(f"{operation} failed", error=str(error), exc_info=error)
            return APIError(
                code="UNKNOWN_ERROR",
                message=str(error),
                details={"operation": operation},
            )
