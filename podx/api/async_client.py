"""Asynchronous API client for podx."""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Dict, Optional

from ..errors import ValidationError
from ..logging import get_logger
from .config import ClientConfig
from .models import DiarizeResponse, TranscribeResponse

logger = get_logger(__name__)


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
