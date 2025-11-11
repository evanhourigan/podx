"""High-level API client for podx.

This module provides a clean, type-safe interface for podcast processing operations.
"""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Dict, Optional

from ..errors import AIError, AudioError, NetworkError, ValidationError
from ..logging import get_logger
from .models import (
    APIError,
    DeepcastResponse,
    DiarizeResponse,
    ExistsCheckResponse,
    ExportResponse,
    FetchResponse,
    NotionResponse,
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
                raise ValidationError(f"Invalid inputs: {', '.join(validation.errors)}")

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

            return FetchResponse(
                episode_meta=result["meta"],
                audio_meta=result.get("audio_meta"),
                audio_path=str(result["audio_path"]),
                metadata_path=str(result.get("meta_path")),
                success=True,
            )
        except Exception as e:
            logger.error("Failed to fetch episode", error=str(e))
            return FetchResponse(
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
                    raise ValidationError(
                        "audio_path must be provided or exist in transcript JSON"
                    )
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
            speakers = set()
            for seg in diarized_segments:
                if seg.get("speaker"):
                    speakers.add(seg["speaker"])

            return DiarizeResponse(
                transcript_path=str(diarized_path),
                speakers_found=len(speakers),
                transcript=diarized_data,
                success=True,
            )
        except Exception as e:
            logger.error("Failed to diarize transcript", error=str(e))
            return DiarizeResponse(
                transcript_path="",
                speakers_found=0,
                success=False,
                error=str(e),
            )

    def export(
        self,
        transcript_path: Path,
        formats: list[str] = None,
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

            return ExportResponse(
                output_files=result,
                formats=formats,
                success=True,
            )
        except Exception as e:
            logger.error("Failed to export transcript", error=str(e))
            return ExportResponse(
                output_files={},
                formats=formats,
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
            raise ValidationError(
                "NOTION_TOKEN must be provided or set as environment variable"
            )

        try:
            # Load deepcast data
            deepcast_data = json.loads(deepcast_path.read_text())
            markdown = deepcast_data.get("markdown", "")
            metadata = deepcast_data.get("metadata", {})

            # Extract episode info
            episode_title = (
                metadata.get("episode_title")
                or metadata.get("title")
                or "Podcast Notes"
            )
            podcast_name = metadata.get("show") or "Unknown Podcast"
            date_iso = metadata.get("episode_published") or metadata.get("date")

            # Publish to Notion
            engine = NotionEngine(api_token=token)
            page_id = engine.create_page(
                database_id=database_id,
                title=episode_title,
                podcast_name=podcast_name,
                date=date_iso,
                markdown=markdown,
            )

            page_url = f"https://notion.so/{page_id.replace('-', '')}"

            return NotionResponse(
                page_url=page_url,
                page_id=page_id,
                database_id=database_id,
                success=True,
            )
        except Exception as e:
            logger.error("Failed to publish to Notion", error=str(e))
            return NotionResponse(
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


# Type alias for progress callbacks
ProgressCallback = Callable[[Dict[str, Any]], None]
AsyncProgressCallback = Callable[[Dict[str, Any]], asyncio.Future[None]]


class AsyncPodxClient:
    """Async client for podx API with real-time progress updates.

    This class provides async versions of long-running operations with progress
    callback support. It wraps CLI commands that support --progress-json to
    provide real-time updates for web UIs and monitoring tools.

    Examples:
        Callback-based progress:
        >>> async def on_progress(update: dict):
        ...     print(f"Progress: {update.get('message', '')}")
        ...
        >>> client = AsyncPodxClient()
        >>> result = await client.transcribe(
        ...     "audio.mp3",
        ...     progress_callback=on_progress
        ... )

        Streaming progress (async generator):
        >>> async for update in client.transcribe_stream("audio.mp3"):
        ...     if "percent" in update:
        ...         print(f"{update['percent']}%")
        ...     else:
        ...         result = update  # Final TranscribeResponse

        Async diarization:
        >>> result = await client.diarize(
        ...     transcript_path="transcript.json",
        ...     progress_callback=lambda u: print(u["message"])
        ... )
    """

    def __init__(self, config: Optional[ClientConfig] = None):
        """Initialize the async client.

        Args:
            config: Client configuration (uses defaults if not provided)
        """
        self.config = config or ClientConfig()

    async def transcribe(
        self,
        audio_path: str | Path,
        model: Optional[str] = None,
        asr_provider: str = "auto",
        compute: str = "auto",
        output_dir: Optional[Path] = None,
        progress_callback: Optional[AsyncProgressCallback] = None,
    ) -> TranscribeResponse:
        """Transcribe audio file with progress updates.

        Args:
            audio_path: Path to audio file
            model: ASR model to use (default: config default)
            asr_provider: ASR provider (auto, local, openai, hf)
            compute: Compute type for faster-whisper
            output_dir: Output directory (default: audio file directory)
            progress_callback: Optional async callback for progress updates

        Returns:
            TranscribeResponse with transcript data

        Raises:
            ValidationError: If inputs are invalid
            AudioError: If audio processing fails
        """
        from ..schemas import AudioMeta
        from ..utils import sanitize_model_name

        # Prepare input
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise ValidationError(f"Audio file not found: {audio_path}")

        # Create AudioMeta
        meta = AudioMeta(
            audio_path=str(audio_path),
            format="unknown",
            duration=0,
            sample_rate=0,
        )

        # Determine model
        model = model or self.config.default_model
        safe_model = sanitize_model_name(model)

        # Determine output directory
        if output_dir is None:
            output_dir = audio_path.parent

        output_path = output_dir / f"transcript-{safe_model}.json"

        # Build command
        cmd = [
            "podx-transcribe",
            "--model",
            model,
            "--asr-provider",
            asr_provider,
            "--compute",
            compute,
            "--output",
            str(output_path),
        ]

        if progress_callback:
            cmd.append("--progress-json")

        # Run command with progress streaming
        try:
            result = await self._run_command_with_progress(
                cmd,
                stdin_data=json.dumps(meta.model_dump()),
                progress_callback=progress_callback,
            )

            # Parse result
            output_data = json.loads(result)
            if not output_data.get("success"):
                return TranscribeResponse(
                    transcript_path="",
                    duration_seconds=0,
                    success=False,
                    error=output_data.get("error", "Unknown error"),
                )

            transcript = output_data.get("transcript", {})
            return TranscribeResponse(
                transcript_path=str(output_path),
                duration_seconds=int(transcript.get("duration", 0)),
                model_used=model,
                segments_count=len(transcript.get("segments", [])),
                audio_path=str(audio_path),
                success=True,
            )
        except Exception as e:
            logger.error("Async transcription failed", error=str(e))
            return TranscribeResponse(
                transcript_path="",
                duration_seconds=0,
                success=False,
                error=str(e),
            )

    async def transcribe_stream(
        self,
        audio_path: str | Path,
        model: Optional[str] = None,
        asr_provider: str = "auto",
        compute: str = "auto",
        output_dir: Optional[Path] = None,
    ) -> AsyncIterator[Dict[str, Any] | TranscribeResponse]:
        """Stream transcription progress as async generator.

        Yields progress updates as dicts with "type": "progress", then final
        TranscribeResponse when complete.

        Args:
            audio_path: Path to audio file
            model: ASR model to use
            asr_provider: ASR provider
            compute: Compute type
            output_dir: Output directory

        Yields:
            Progress update dicts, then final TranscribeResponse

        Example:
            >>> async for update in client.transcribe_stream("audio.mp3"):
            ...     if isinstance(update, dict):
            ...         print(f"Progress: {update['message']}")
            ...     else:
            ...         print(f"Done: {update.transcript_path}")
        """
        progress_updates = []

        async def callback(update: Dict[str, Any]):
            progress_updates.append(update)

        # Start transcription in background
        task = asyncio.create_task(
            self.transcribe(
                audio_path=audio_path,
                model=model,
                asr_provider=asr_provider,
                compute=compute,
                output_dir=output_dir,
                progress_callback=callback,
            )
        )

        # Yield progress updates as they arrive
        last_yielded = 0
        while not task.done():
            # Yield any new progress updates
            if len(progress_updates) > last_yielded:
                for update in progress_updates[last_yielded:]:
                    yield update
                last_yielded = len(progress_updates)

            await asyncio.sleep(0.1)

        # Get final result
        result = await task
        yield result

    async def diarize(
        self,
        transcript_path: str | Path,
        audio_path: Optional[str | Path] = None,
        num_speakers: Optional[int] = None,
        min_speakers: Optional[int] = None,
        max_speakers: Optional[int] = None,
        output_dir: Optional[Path] = None,
        progress_callback: Optional[AsyncProgressCallback] = None,
    ) -> DiarizeResponse:
        """Diarize transcript with speaker identification.

        Args:
            transcript_path: Path to transcript JSON file
            audio_path: Path to audio file (auto-detected if not provided)
            num_speakers: Exact number of speakers (if known)
            min_speakers: Minimum number of speakers
            max_speakers: Maximum number of speakers
            output_dir: Output directory
            progress_callback: Optional async callback for progress updates

        Returns:
            DiarizeResponse with diarized transcript

        Raises:
            ValidationError: If inputs are invalid
        """
        from ..schemas import Transcript

        # Validate transcript exists
        transcript_path = Path(transcript_path)
        if not transcript_path.exists():
            raise ValidationError(f"Transcript not found: {transcript_path}")

        # Load transcript to get audio path if needed
        if audio_path is None:
            transcript = Transcript.model_validate(
                json.loads(transcript_path.read_text())
            )
            audio_path = Path(transcript.audio_path)
        else:
            audio_path = Path(audio_path)

        if not audio_path.exists():
            raise ValidationError(f"Audio file not found: {audio_path}")

        # Determine output directory
        if output_dir is None:
            output_dir = transcript_path.parent

        output_path = output_dir / "transcript-diarized.json"

        # Build command
        cmd = ["podx-diarize", "--output", str(output_path)]

        if num_speakers:
            cmd.extend(["--num-speakers", str(num_speakers)])
        if min_speakers:
            cmd.extend(["--min-speakers", str(min_speakers)])
        if max_speakers:
            cmd.extend(["--max-speakers", str(max_speakers)])

        if progress_callback:
            cmd.append("--progress-json")

        # Run command with progress streaming
        try:
            result = await self._run_command_with_progress(
                cmd,
                stdin_data=transcript_path.read_text(),
                progress_callback=progress_callback,
            )

            # Parse result
            output_data = json.loads(result)
            if not output_data.get("success"):
                return DiarizeResponse(
                    transcript_path="",
                    speakers_found=0,
                    success=False,
                    error=output_data.get("error", "Unknown error"),
                )

            transcript = output_data.get("transcript", {})
            speakers = set()
            for seg in transcript.get("segments", []):
                if seg.get("speaker"):
                    speakers.add(seg["speaker"])

            return DiarizeResponse(
                transcript_path=str(output_path),
                speakers_found=len(speakers),
                transcript=transcript,
                success=True,
            )
        except Exception as e:
            logger.error("Async diarization failed", error=str(e))
            return DiarizeResponse(
                transcript_path="",
                speakers_found=0,
                success=False,
                error=str(e),
            )

    async def diarize_stream(
        self,
        transcript_path: str | Path,
        audio_path: Optional[str | Path] = None,
        num_speakers: Optional[int] = None,
        min_speakers: Optional[int] = None,
        max_speakers: Optional[int] = None,
        output_dir: Optional[Path] = None,
    ) -> AsyncIterator[Dict[str, Any] | DiarizeResponse]:
        """Stream diarization progress as async generator.

        Yields progress updates as dicts, then final DiarizeResponse.

        Args:
            transcript_path: Path to transcript JSON file
            audio_path: Path to audio file
            num_speakers: Exact number of speakers
            min_speakers: Minimum number of speakers
            max_speakers: Maximum number of speakers
            output_dir: Output directory

        Yields:
            Progress update dicts, then final DiarizeResponse
        """
        progress_updates = []

        async def callback(update: Dict[str, Any]):
            progress_updates.append(update)

        # Start diarization in background
        task = asyncio.create_task(
            self.diarize(
                transcript_path=transcript_path,
                audio_path=audio_path,
                num_speakers=num_speakers,
                min_speakers=min_speakers,
                max_speakers=max_speakers,
                output_dir=output_dir,
                progress_callback=callback,
            )
        )

        # Yield progress updates as they arrive
        last_yielded = 0
        while not task.done():
            if len(progress_updates) > last_yielded:
                for update in progress_updates[last_yielded:]:
                    yield update
                last_yielded = len(progress_updates)

            await asyncio.sleep(0.1)

        # Get final result
        result = await task
        yield result

    async def _run_command_with_progress(
        self,
        cmd: list[str],
        stdin_data: Optional[str] = None,
        progress_callback: Optional[AsyncProgressCallback] = None,
    ) -> str:
        """Run CLI command and stream progress updates.

        Args:
            cmd: Command and arguments to run
            stdin_data: Optional data to send to stdin
            progress_callback: Optional callback for progress updates

        Returns:
            Final stdout output (JSON result)

        Raises:
            subprocess.CalledProcessError: If command fails
        """
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE if stdin_data else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Send stdin data if provided
        if stdin_data:
            process.stdin.write(stdin_data.encode())
            process.stdin.close()

        # Collect output
        stdout_lines = []
        final_result = None

        # Read stdout line by line for progress updates
        while True:
            line = await process.stdout.readline()
            if not line:
                break

            line_str = line.decode().strip()
            if not line_str:
                continue

            # Try to parse as JSON
            try:
                data = json.loads(line_str)

                # Check if this is a progress update
                if data.get("type") == "progress" and progress_callback:
                    await progress_callback(data)
                else:
                    # This might be the final result
                    final_result = line_str
            except json.JSONDecodeError:
                # Not JSON, might be final output or error
                stdout_lines.append(line_str)

        # Wait for process to complete
        await process.wait()

        # Check exit code
        if process.returncode != 0:
            stderr = await process.stderr.read()
            raise subprocess.CalledProcessError(
                process.returncode, cmd, stderr=stderr.decode()
            )

        # Return final result or joined output
        if final_result:
            return final_result
        return "\n".join(stdout_lines)
