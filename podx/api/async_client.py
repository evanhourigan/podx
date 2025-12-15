"""Asynchronous API client for podx."""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Optional

from ..errors import ValidationError
from ..logging import get_logger
from .config import ClientConfig
from .models import CostEstimate, DiarizeResponse, ModelInfo, TranscribeResponse

logger = get_logger(__name__)


# Type alias for progress callbacks
ProgressCallback = Callable[[Dict[str, Any]], None]
AsyncProgressCallback = Callable[[Dict[str, Any]], Awaitable[None]]


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
        meta = AudioMeta(  # type: ignore[call-arg]
            audio_path=str(audio_path),
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
                return TranscribeResponse(  # type: ignore[call-arg]
                    transcript_path="",
                    duration_seconds=0,
                    success=False,
                    error=output_data.get("error", "Unknown error"),
                )

            transcript = output_data.get("transcript", {})
            return TranscribeResponse(  # type: ignore[call-arg]
                transcript_path=str(output_path),
                duration_seconds=int(transcript.get("duration", 0)),
                model_used=model,
                segments_count=len(transcript.get("segments", [])),
                audio_path=str(audio_path),
                success=True,
            )
        except Exception as e:
            logger.error("Async transcription failed", error=str(e))
            return TranscribeResponse(  # type: ignore[call-arg]
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
        progress_updates: List[Dict[str, Any]] = []

        async def callback(update: Dict[str, Any]) -> None:
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
        resolved_audio_path: Path
        if audio_path is None:
            transcript = Transcript.model_validate(json.loads(transcript_path.read_text()))
            if not transcript.audio_path:
                raise ValidationError("Transcript missing audio_path")
            resolved_audio_path = Path(transcript.audio_path)
        else:
            resolved_audio_path = Path(audio_path)

        if not resolved_audio_path.exists():
            raise ValidationError(f"Audio file not found: {resolved_audio_path}")

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
                return DiarizeResponse(  # type: ignore[call-arg]
                    transcript_path="",
                    speakers_found=0,
                    success=False,
                    error=output_data.get("error", "Unknown error"),
                )

            transcript_data = output_data.get("transcript", {})
            speakers: set[str] = set()
            for seg in transcript_data.get("segments", []):
                if isinstance(seg, dict) and seg.get("speaker"):
                    speakers.add(seg["speaker"])

            return DiarizeResponse(  # type: ignore[call-arg]
                transcript_path=str(output_path),
                speakers_found=len(speakers),
                transcript=transcript_data,
                success=True,
            )
        except Exception as e:
            logger.error("Async diarization failed", error=str(e))
            return DiarizeResponse(  # type: ignore[call-arg]
                transcript_path="",
                speakers_found=0,
                success=False,
                error=str(e),
            )

    async def cleanup(
        self,
        transcript_path: str | Path,
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
            >>> result = await client.cleanup(Path("transcript.json"))
            >>> print(f"Cleaned {result['original_segments']} -> {result['cleaned_segments']}")
        """
        from ..core.preprocess import PreprocessError, TranscriptPreprocessor

        transcript_path = Path(transcript_path)
        if not transcript_path.exists():
            raise ValidationError(f"Transcript file not found: {transcript_path}")

        # Run preprocessing in thread pool (sync operation)
        def _do_cleanup() -> Dict[str, Any]:
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

            return {
                "success": True,
                "transcript_path": str(out_path),
                "original_segments": original_count,
                "cleaned_segments": cleaned_count,
                "restored": restore,
            }

        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, _do_cleanup)
        except PreprocessError as e:
            logger.error("Failed to cleanup transcript", error=str(e))
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error("Failed to cleanup transcript", error=str(e))
            return {"success": False, "error": str(e)}

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
        progress_updates: List[Dict[str, Any]] = []

        async def callback(update: Dict[str, Any]) -> None:
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
        if stdin_data and process.stdin:
            process.stdin.write(stdin_data.encode())
            await process.stdin.drain()
            process.stdin.close()

        # Collect output
        stdout_lines: List[str] = []
        final_result: Optional[str] = None

        # Read stdout line by line for progress updates
        if process.stdout:
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
            stderr_output = ""
            if process.stderr:
                stderr_bytes = await process.stderr.read()
                stderr_output = stderr_bytes.decode()
            raise subprocess.CalledProcessError(process.returncode or 1, cmd, stderr=stderr_output)

        # Return final result or joined output
        if final_result:
            return final_result
        return "\n".join(stdout_lines)

    # =========================================================================
    # Model Catalog Methods (synchronous - no I/O)
    # =========================================================================

    def list_models(
        self,
        provider: Optional[str] = None,
        default_only: bool = False,
        capability: Optional[str] = None,
    ) -> list[ModelInfo]:
        """List available LLM models with optional filtering.

        Note: This method is synchronous (no async) as it only reads cached data.

        Args:
            provider: Filter by provider (e.g., "openai", "anthropic")
            default_only: If True, only include models shown in default CLI listings
            capability: Filter by capability (e.g., "vision", "function-calling")

        Returns:
            List of ModelInfo objects, sorted by provider then model ID

        Example:
            >>> client = AsyncPodxClient()
            >>> # List all OpenAI models
            >>> openai_models = client.list_models(provider="openai")
            >>> for model in openai_models:
            ...     print(f"{model.name}: ${model.pricing.input_per_1m}/M")
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

        Note: This method is synchronous (no async) as it only reads cached data.

        Args:
            model_id_or_alias: Model ID or alias (case-insensitive)

        Returns:
            ModelInfo with full model details including pricing

        Raises:
            KeyError: If model not found

        Example:
            >>> client = AsyncPodxClient()
            >>> model = client.get_model_info("gpt-5")
            >>> print(f"Price: ${model.pricing.input_per_1m}/M input")
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

        Note: This method is synchronous. For transcript_path, it reads the file
        synchronously. Use in async context with care for large files.

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
            >>> client = AsyncPodxClient()
            >>> estimate = client.estimate_cost(model="gpt-5", token_count=50000)
            >>> print(f"Estimated cost: ${estimate.total_cost_usd:.4f}")
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
