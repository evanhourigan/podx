"""Synchronous API client for podx."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..errors import AIError, AudioError, NetworkError, ValidationError
from ..logging import get_logger
from .config import ClientConfig

# Import the underlying API functions from legacy module
from .legacy import analyze as _analyze
from .legacy import has_markdown as _has_markdown
from .legacy import has_transcript as _has_transcript
from .legacy import transcribe as _transcribe
from .models import (
    AnalyzeResponse,
    APIError,
    CostEstimate,
    DiarizeResponse,
    ExistsCheckResponse,
    ExportResponse,
    FetchResponse,
    ModelInfo,
    NotionResponse,
    TranscribeResponse,
    ValidationResult,
)

logger = get_logger(__name__)


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
                raise ValidationError(f"Invalid inputs: {', '.join(validation.errors)}")

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
            response = TranscribeResponse(  # type: ignore[call-arg]
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
            return TranscribeResponse(  # type: ignore[call-arg]
                transcript_path="",
                duration_seconds=0,
                success=False,
                error=str(error_response),
            )

    def analyze(
        self,
        transcript_path: str,
        llm_model: Optional[str] = None,
        out_dir: Optional[str] = None,
        provider_keys: Optional[Dict[str, str]] = None,
        prompt: Optional[str] = None,
        prompt_name: str = "default",
    ) -> AnalyzeResponse:
        """Run analysis on a transcript.

        Args:
            transcript_path: Path to transcript JSON file
            llm_model: LLM model to use (defaults to config.default_llm_model)
            out_dir: Output directory (defaults to config.output_dir)
            provider_keys: API keys for LLM providers
            prompt: Custom prompt for analysis
            prompt_name: Name for the prompt (for caching/organization)

        Returns:
            AnalyzeResponse with markdown path and metadata

        Raises:
            ValidationError: If inputs are invalid
            AIError: If analysis fails
        """
        # Validate inputs
        if self.config.validate_inputs:
            validation = self._validate_analyze_inputs(transcript_path, llm_model, out_dir)
            if not validation.valid:
                raise ValidationError(f"Invalid inputs: {', '.join(validation.errors)}")

        # Set defaults
        llm_model = llm_model or self.config.default_llm_model
        out_dir = out_dir or str(self.config.output_dir or Path.cwd() / "output")

        try:
            # Call underlying API
            result = _analyze(
                transcript_path=transcript_path,
                llm_model=llm_model,
                out_dir=out_dir,
                provider_keys=provider_keys,
                prompt=prompt,
                prompt_name=prompt_name,
            )

            # Wrap in response model
            response = AnalyzeResponse(  # type: ignore[call-arg]
                markdown_path=result["markdown_path"],
                usage=result.get("usage"),
                prompt_used=result.get("prompt_used"),
                model_used=llm_model,
                success=True,
            )

            logger.info(
                "Analysis completed",
                path=response.markdown_path,
                model=llm_model,
            )
            return response

        except Exception as e:
            error_response = self._handle_error(e, "analyze")
            return AnalyzeResponse(  # type: ignore[call-arg]
                markdown_path="",
                success=False,
                error=str(error_response),
            )

    # Backwards compatibility alias
    def deepcast(
        self,
        transcript_path: str,
        llm_model: Optional[str] = None,
        out_dir: Optional[str] = None,
        provider_keys: Optional[Dict[str, str]] = None,
        prompt: Optional[str] = None,
        prompt_name: str = "default",
    ) -> AnalyzeResponse:
        """Deprecated: Use analyze() instead. This is a backwards compatibility alias."""
        return self.analyze(
            transcript_path=transcript_path,
            llm_model=llm_model,
            out_dir=out_dir,
            provider_keys=provider_keys,
            prompt=prompt,
            prompt_name=prompt_name,
        )

    def fetch_episode(
        self,
        show_name: Optional[str] = None,
        rss_url: Optional[str] = None,
        date: Optional[str] = None,
        title_contains: Optional[str] = None,
        output_dir: Optional[Path] = None,
    ) -> FetchResponse:
        """Fetch podcast episode by show name or RSS URL.

        Args:
            show_name: Name of podcast show (e.g., "huberman lab")
            rss_url: Direct RSS feed URL (alternative to show_name)
            date: Episode date (YYYY-MM-DD) or "latest"
            title_contains: Substring to match in episode title
            output_dir: Directory to save audio and metadata

        Returns:
            FetchResponse with episode metadata and file paths

        Raises:
            ValidationError: If inputs are invalid
            NetworkError: If download fails

        Example:
            >>> client = PodxClient()
            >>> result = client.fetch_episode("huberman lab", date="latest")
            >>> print(result.audio_path)
        """
        from ..core.fetch import PodcastFetcher

        if not show_name and not rss_url:
            raise ValidationError("Either show_name or rss_url must be provided")

        try:
            fetcher = PodcastFetcher()
            result = fetcher.fetch_episode(
                show_name=show_name,
                rss_url=rss_url,
                date=date,
                title_contains=title_contains,
                output_dir=output_dir or Path.cwd(),
            )

            return FetchResponse(  # type: ignore[call-arg]
                episode_meta=result["meta"],
                audio_meta=result.get("audio_meta"),
                audio_path=str(result["audio_path"]),
                metadata_path=str(result.get("meta_path")),
                success=True,
            )
        except Exception as e:
            logger.error("Failed to fetch episode", error=str(e))
            return FetchResponse(  # type: ignore[call-arg]
                episode_meta={},
                audio_path="",
                success=False,
                error=str(e),
            )

    def diarize(
        self,
        transcript_path: Path,
        audio_path: Optional[Path] = None,
        language: str = "en",
        output_dir: Optional[Path] = None,
    ) -> DiarizeResponse:
        """Add speaker identification to transcript.

        Args:
            transcript_path: Path to existing transcript JSON
            audio_path: Path to audio file (required for diarization)
            language: Language code (default: "en")
            output_dir: Directory to save diarized transcript

        Returns:
            DiarizeResponse with diarized transcript and speaker count

        Raises:
            ValidationError: If inputs are invalid

        Example:
            >>> result = client.diarize(Path("transcript.json"), audio_path=Path("audio.mp3"))
            >>> print(f"Found {result.speakers_found} speakers")
        """
        from ..core.diarize import DiarizationEngine

        if not transcript_path.exists():
            raise ValidationError(f"Transcript file not found: {transcript_path}")

        try:
            # Load transcript
            transcript_data = json.loads(transcript_path.read_text())

            # Get audio path from transcript if not provided
            if not audio_path:
                audio_path_str = transcript_data.get("audio_path")
                if not audio_path_str:
                    raise ValidationError("audio_path must be provided or exist in transcript JSON")
                audio_path = Path(audio_path_str)

            if not audio_path.exists():
                raise ValidationError(f"Audio file not found: {audio_path}")

            # Diarize
            engine = DiarizationEngine(language=language)
            diarized_segments = engine.diarize(audio_path, transcript_data["segments"])

            # Save diarized transcript
            out_dir = output_dir or transcript_path.parent
            diarized_path = out_dir / f"{transcript_path.stem}_diarized.json"

            diarized_data = {**transcript_data, "segments": diarized_segments}
            diarized_path.write_text(json.dumps(diarized_data, indent=2))

            # Count unique speakers
            speakers: set[str] = set()
            for seg in diarized_segments:
                if isinstance(seg, dict) and seg.get("speaker"):
                    speakers.add(seg["speaker"])

            return DiarizeResponse(  # type: ignore[call-arg]
                transcript_path=str(diarized_path),
                speakers_found=len(speakers),
                transcript=diarized_data,
                success=True,
            )
        except Exception as e:
            logger.error("Failed to diarize transcript", error=str(e))
            return DiarizeResponse(  # type: ignore[call-arg]
                transcript_path="",
                speakers_found=0,
                success=False,
                error=str(e),
            )

    def cleanup(
        self,
        transcript_path: Path,
        restore: bool = True,
        output_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Clean up transcript text for readability and improved LLM analysis.

        Args:
            transcript_path: Path to transcript JSON file
            restore: Use LLM to restore punctuation/capitalization (default: True)
            output_dir: Directory to save cleaned transcript (default: same as input)

        Returns:
            Dict with success status, output path, and segment counts

        Raises:
            ValidationError: If inputs are invalid

        Notes:
            - Merges short adjacent segments into readable paragraphs
            - Normalizes whitespace and punctuation spacing
            - Optionally restores punctuation/capitalization via LLM

        Example:
            >>> result = client.cleanup(Path("transcript.json"))
            >>> print(f"Cleaned {result['original_segments']} -> {result['cleaned_segments']}")
        """
        from ..core.preprocess import PreprocessError, TranscriptPreprocessor

        if not transcript_path.exists():
            raise ValidationError(f"Transcript file not found: {transcript_path}")

        try:
            # Load transcript
            transcript_data = json.loads(transcript_path.read_text())

            # Check if already cleaned
            if transcript_data.get("cleaned"):
                logger.info("Transcript already cleaned, skipping")
                return {
                    "success": True,
                    "skipped": True,
                    "transcript_path": str(transcript_path),
                    "original_segments": len(transcript_data.get("segments", [])),
                    "cleaned_segments": len(transcript_data.get("segments", [])),
                }

            # Run preprocessing
            preprocessor = TranscriptPreprocessor(
                merge=True,
                normalize=True,
                restore=restore,
                max_gap=1.0,
                max_len=800,
                restore_model="gpt-4o-mini",
            )
            result = preprocessor.preprocess(transcript_data)

            # Preserve existing metadata
            original_keys = [
                "audio_path",
                "language",
                "asr_model",
                "asr_provider",
                "decoder_options",
                "diarized",
            ]
            for key in original_keys:
                if key in transcript_data:
                    result[key] = transcript_data[key]

            # Set cleanup state flags
            result["cleaned"] = True
            result["restored"] = restore

            # Save to output location
            out_dir = output_dir or transcript_path.parent
            out_path = out_dir / transcript_path.name
            out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))

            original_count = len(transcript_data.get("segments", []))
            cleaned_count = len(result.get("segments", []))

            logger.info(
                "Cleanup completed",
                original_segments=original_count,
                cleaned_segments=cleaned_count,
            )

            return {
                "success": True,
                "transcript_path": str(out_path),
                "original_segments": original_count,
                "cleaned_segments": cleaned_count,
                "restored": restore,
            }

        except PreprocessError as e:
            logger.error("Failed to cleanup transcript", error=str(e))
            return {
                "success": False,
                "error": str(e),
            }
        except Exception as e:
            logger.error("Failed to cleanup transcript", error=str(e))
            return {
                "success": False,
                "error": str(e),
            }

    def export(
        self,
        transcript_path: Path,
        formats: Optional[List[str]] = None,
        output_dir: Optional[Path] = None,
    ) -> ExportResponse:
        """Export transcript to different formats.

        Args:
            transcript_path: Path to transcript JSON
            formats: List of output formats (txt, srt, vtt, md)
            output_dir: Output directory (default: same as transcript)

        Returns:
            ExportResponse with output file paths

        Example:
            >>> result = client.export(Path("transcript.json"), formats=["txt", "srt"])
            >>> print(result.output_files)
        """
        from ..core.export import ExportEngine

        if formats is None:
            formats = ["txt", "srt"]

        if not transcript_path.exists():
            raise ValidationError(f"Transcript file not found: {transcript_path}")

        try:
            # Load transcript
            transcript_data = json.loads(transcript_path.read_text())

            # Export
            engine = ExportEngine()
            out_dir = output_dir or transcript_path.parent
            base_name = transcript_path.stem

            result = engine.export(
                transcript=transcript_data,
                formats=formats,
                output_dir=out_dir,
                base_name=base_name,
            )

            return ExportResponse(  # type: ignore[call-arg]
                output_files=result,
                formats=formats,
                success=True,
            )
        except Exception as e:
            logger.error("Failed to export transcript", error=str(e))
            return ExportResponse(
                output_files={},
                formats=formats or [],
                success=False,
                error=str(e),
            )

    def publish_to_notion(
        self,
        deepcast_path: Path,
        database_id: str,
        notion_token: Optional[str] = None,
    ) -> NotionResponse:
        """Publish deepcast analysis to Notion.

        Args:
            deepcast_path: Path to deepcast JSON file
            database_id: Notion database ID
            notion_token: Notion API token (or use NOTION_TOKEN env var)

        Returns:
            NotionResponse with Notion page URL

        Example:
            >>> result = client.publish_to_notion(
            ...     Path("deepcast.json"),
            ...     database_id="abc123"
            ... )
            >>> print(f"Published: {result.page_url}")
        """
        import os

        from ..core.notion import NotionEngine

        if not deepcast_path.exists():
            raise ValidationError(f"Deepcast file not found: {deepcast_path}")

        # Get Notion token
        token = notion_token or os.getenv("NOTION_TOKEN")
        if not token:
            raise ValidationError("NOTION_TOKEN must be provided or set as environment variable")

        try:
            # Load deepcast data
            deepcast_data = json.loads(deepcast_path.read_text())
            markdown = deepcast_data.get("markdown", "")
            metadata = deepcast_data.get("metadata", {})

            # Extract episode info
            episode_title = (
                metadata.get("episode_title") or metadata.get("title") or "Podcast Notes"
            )
            podcast_name = metadata.get("show") or "Unknown Podcast"
            date_iso = metadata.get("episode_published") or metadata.get("date")

            # Publish to Notion
            from ..core.notion import md_to_blocks

            engine = NotionEngine(api_token=token)
            properties: Dict[str, Any] = {
                "Name": {"title": [{"text": {"content": episode_title}}]},
                "Show": {"rich_text": [{"text": {"content": podcast_name}}]},
            }
            if date_iso:
                properties["Date"] = {"date": {"start": date_iso}}
            blocks = md_to_blocks(markdown)
            page_id = engine.upsert_page(
                database_id=database_id,
                properties=properties,
                blocks=blocks,
            )

            page_url = f"https://notion.so/{page_id.replace('-', '')}"

            return NotionResponse(  # type: ignore[call-arg]
                page_url=page_url,
                page_id=page_id,
                database_id=database_id,
                success=True,
            )
        except Exception as e:
            logger.error("Failed to publish to Notion", error=str(e))
            return NotionResponse(  # type: ignore[call-arg]
                page_url="",
                page_id="",
                success=False,
                error=str(e),
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
            return ExistsCheckResponse(  # type: ignore[call-arg]
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

            return ExistsCheckResponse(  # type: ignore[call-arg]
                exists=exists,
                path=path,
                resource_type="markdown",
            )
        except Exception as e:
            logger.warning("Failed to check markdown existence", error=str(e))
            return ExistsCheckResponse(  # type: ignore[call-arg]
                exists=False,
                path=None,
                resource_type="markdown",
            )

    # =========================================================================
    # Model Catalog Methods
    # =========================================================================

    def list_models(
        self,
        provider: Optional[str] = None,
        default_only: bool = False,
        capability: Optional[str] = None,
    ) -> list[ModelInfo]:
        """List available LLM models with optional filtering.

        Args:
            provider: Filter by provider (e.g., "openai", "anthropic")
            default_only: If True, only include models shown in default CLI listings
            capability: Filter by capability (e.g., "vision", "function-calling")

        Returns:
            List of ModelInfo objects, sorted by provider then model ID

        Example:
            >>> client = PodxClient()
            >>> # List all OpenAI models
            >>> openai_models = client.list_models(provider="openai")
            >>> for model in openai_models:
            ...     print(f"{model.name}: ${model.pricing.input_per_1m}/M")
            >>>
            >>> # List models with vision capability
            >>> vision_models = client.list_models(capability="vision")
        """
        from ..models import list_models as _list_models

        catalog_models = _list_models(
            provider=provider,
            default_only=default_only,
            capability=capability,
        )
        return [ModelInfo.from_catalog_model(m) for m in catalog_models]

    def get_model_info(self, model_id_or_alias: str) -> ModelInfo:
        """Get detailed information about a specific model.

        Supports case-insensitive lookup and aliases. For example, "gpt-5.1",
        "gpt5.1", "GPT-5-1" all resolve to the same model.

        Args:
            model_id_or_alias: Model ID or alias (case-insensitive)

        Returns:
            ModelInfo with full model details including pricing

        Raises:
            KeyError: If model not found

        Example:
            >>> client = PodxClient()
            >>> model = client.get_model_info("gpt-5")
            >>> print(f"Name: {model.name}")
            >>> print(f"Provider: {model.provider}")
            >>> print(f"Price: ${model.pricing.input_per_1m}/M input")
            >>> print(f"Context: {model.context_window:,} tokens")
            >>> print(f"Capabilities: {', '.join(model.capabilities)}")
        """
        from ..models import get_model as _get_model

        catalog_model = _get_model(model_id_or_alias)
        return ModelInfo.from_catalog_model(catalog_model)

    def estimate_cost(
        self,
        model: str,
        transcript_path: Optional[str] = None,
        text: Optional[str] = None,
        token_count: Optional[int] = None,
        output_ratio: float = 0.3,
    ) -> CostEstimate:
        """Estimate the cost of processing with a specific model.

        Provide one of: transcript_path, text, or token_count.

        Token estimation uses ~4 characters per token as a rough approximation.
        Output tokens are estimated as a ratio of input tokens (default 30%).

        Args:
            model: Model ID or alias (e.g., "gpt-5", "claude-sonnet-4.5")
            transcript_path: Path to transcript JSON file
            text: Raw text to estimate
            token_count: Pre-calculated token count
            output_ratio: Expected output/input token ratio (default 0.3 = 30%)

        Returns:
            CostEstimate with token counts and USD costs

        Raises:
            ValueError: If no input provided or multiple inputs provided
            KeyError: If model not found
            FileNotFoundError: If transcript_path doesn't exist

        Example:
            >>> client = PodxClient()
            >>> # Estimate from transcript file
            >>> estimate = client.estimate_cost(
            ...     transcript_path="transcript.json",
            ...     model="claude-sonnet-4.5"
            ... )
            >>> print(f"Estimated tokens: {estimate.input_tokens:,}")
            >>> print(f"Estimated cost: ${estimate.total_cost_usd:.4f}")
            >>>
            >>> # Estimate from raw text
            >>> estimate = client.estimate_cost(model="gpt-5", text="Hello world")
            >>>
            >>> # Estimate from known token count
            >>> estimate = client.estimate_cost(model="gpt-5", token_count=50000)
        """
        from ..models import get_model as _get_model

        # Validate input - exactly one source required
        inputs_provided = sum(
            [transcript_path is not None, text is not None, token_count is not None]
        )
        if inputs_provided == 0:
            raise ValueError("Must provide one of: transcript_path, text, or token_count")
        if inputs_provided > 1:
            raise ValueError("Provide only one of: transcript_path, text, or token_count")

        # Get model info
        catalog_model = _get_model(model)

        # Determine input text and tokens
        input_text = ""
        if transcript_path:
            path = Path(transcript_path)
            if not path.exists():
                raise FileNotFoundError(f"Transcript not found: {transcript_path}")
            try:
                transcript_data = json.loads(path.read_text())
                # Extract text from segments
                segments = transcript_data.get("segments", [])
                input_text = " ".join(seg.get("text", "") for seg in segments)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid transcript JSON: {e}")

        elif text:
            input_text = text

        # Calculate tokens
        if token_count is not None:
            input_tokens = token_count
            text_length = 0
        else:
            text_length = len(input_text)
            # Rough estimate: ~4 characters per token
            input_tokens = max(1, text_length // 4)

        # Estimate output tokens based on ratio
        output_tokens = int(input_tokens * output_ratio)

        # Calculate costs
        input_cost = (input_tokens / 1_000_000) * catalog_model.pricing.input_per_1m
        output_cost = (output_tokens / 1_000_000) * catalog_model.pricing.output_per_1m
        total_cost = input_cost + output_cost

        return CostEstimate(
            model_id=catalog_model.id,
            model_name=catalog_model.name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_cost_usd=round(input_cost, 6),
            output_cost_usd=round(output_cost, 6),
            total_cost_usd=round(total_cost, 6),
            currency="USD",
            transcript_path=transcript_path,
            text_length=text_length if token_count is None else 0,
            notes=f"Estimate based on ~4 chars/token, {output_ratio:.0%} output ratio",
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

    def _validate_analyze_inputs(
        self, transcript_path: str, llm_model: Optional[str], out_dir: Optional[str]
    ) -> ValidationResult:
        """Validate inputs for analyze API."""
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

    # Backwards compatibility alias
    _validate_deepcast_inputs = _validate_analyze_inputs

    def _check_cache(
        self, audio_url: str, model: str, out_dir: str
    ) -> Optional[TranscribeResponse]:
        """Check if cached result exists."""
        # Simplified cache check - just look for existing transcript
        transcript_path = Path(out_dir) / "transcript.json"
        if transcript_path.exists():
            try:
                data = json.loads(transcript_path.read_text())
                return TranscribeResponse(  # type: ignore[call-arg]
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
