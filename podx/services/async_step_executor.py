"""Async step executor for running pipeline commands concurrently."""

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..errors import ValidationError
from ..logging import get_logger
from .command_builder import CommandBuilder

logger = get_logger(__name__)


class AsyncStepExecutor:
    """Async executor for pipeline steps via subprocess commands.

    This class provides async/await support for running CLI commands,
    enabling concurrent execution of independent pipeline steps.

    Examples:
        >>> executor = AsyncStepExecutor(verbose=True)
        >>> result = await executor.fetch(show="My Podcast", date="2024-10-01")
        >>> audio = await executor.transcode(meta=result, fmt="wav16", outdir=Path("./output"))

        # Run steps concurrently
        >>> async def process_multiple():
        ...     results = await asyncio.gather(
        ...         executor.fetch(show="Podcast 1"),
        ...         executor.fetch(show="Podcast 2"),
        ...         executor.fetch(show="Podcast 3"),
        ...     )
    """

    def __init__(self, verbose: bool = False):
        """Initialize async step executor.

        Args:
            verbose: Enable verbose output (shows JSON preview)
        """
        self.verbose = verbose

    async def _run(
        self,
        cmd: List[str],
        stdin_payload: Optional[Dict[str, Any]] = None,
        save_to: Optional[Path] = None,
        label: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run a CLI command asynchronously that outputs JSON to stdout.

        Args:
            cmd: Command list (e.g., ["podx-fetch", "--show", "Podcast"])
            stdin_payload: Optional JSON payload to pass via stdin
            save_to: Optional path to save raw JSON output
            label: Optional label for logging

        Returns:
            Parsed JSON dictionary from command output

        Raises:
            ValidationError: If command fails or returns invalid JSON
        """
        if label:
            logger.debug("Running async command", command=" ".join(cmd), label=label)

        # Prepare stdin if needed
        stdin_data = json.dumps(stdin_payload) if stdin_payload else None

        # Create subprocess
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE if stdin_data else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Communicate with process
        stdout, stderr = await process.communicate(
            input=stdin_data.encode() if stdin_data else None
        )

        # Check return code
        if process.returncode != 0:
            err = stderr.decode().strip() or stdout.decode().strip()
            logger.error(
                "Async command failed",
                command=" ".join(cmd),
                return_code=process.returncode,
                error=err,
            )
            raise ValidationError(f"Command failed: {' '.join(cmd)}\n{err}")

        # Parse JSON output
        out = stdout.decode()

        if self.verbose:
            # Show compact preview of JSON output
            preview = out[:200] + "..." if len(out) > 200 else out
            logger.info("Command output preview", output=preview)

        try:
            result = json.loads(out)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON output", error=str(e), output=out[:500])
            raise ValidationError(f"Invalid JSON from command: {' '.join(cmd)}\n{e}")

        # Save raw output if requested
        if save_to:
            save_to.parent.mkdir(parents=True, exist_ok=True)
            save_to.write_text(out, encoding="utf-8")
            if self.verbose:
                logger.info("Saved output", path=str(save_to))

        return result

    async def fetch(
        self,
        show: Optional[str] = None,
        rss_url: Optional[str] = None,
        date: Optional[str] = None,
        title_contains: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch podcast episode metadata asynchronously.

        Args:
            show: Podcast name for iTunes search
            rss_url: Direct RSS feed URL
            date: Filter episode by date (YYYY-MM-DD)
            title_contains: Filter episode by title substring

        Returns:
            Episode metadata dictionary

        Raises:
            ValidationError: If fetch fails or no source specified
        """
        cmd = CommandBuilder("podx-fetch")

        if show:
            cmd.add_option("--show", show)
        elif rss_url:
            cmd.add_option("--rss-url", rss_url)
        else:
            raise ValidationError("Either show or rss_url must be provided")

        if date:
            cmd.add_option("--date", date)
        if title_contains:
            cmd.add_option("--title-contains", title_contains)

        return await self._run(cmd.build(), label="fetch")

    async def transcode(
        self,
        meta: Dict[str, Any],
        fmt: str = "wav16",
        outdir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Transcode audio to target format asynchronously.

        Args:
            meta: Episode metadata containing audio_path
            fmt: Target format (wav16, mp3, aac)
            outdir: Output directory

        Returns:
            Audio metadata dictionary

        Raises:
            ValidationError: If transcode fails
        """
        cmd = CommandBuilder("podx-transcode").add_option("--to", fmt)

        if outdir:
            cmd.add_option("--outdir", str(outdir))

        return await self._run(cmd.build(), stdin_payload=meta, label="transcode")

    async def transcribe(
        self,
        audio: Dict[str, Any],
        model: str = "base",
        compute: str = "int8",
        asr_provider: str = "auto",
        preset: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Transcribe audio to text asynchronously.

        Args:
            audio: Audio metadata containing audio_path
            model: ASR model (base, large-v3-turbo, etc.)
            compute: Compute type (int8, float16, float32)
            asr_provider: ASR provider (auto, local, openai, hf)
            preset: ASR preset (balanced, precision, recall)

        Returns:
            Transcript dictionary

        Raises:
            ValidationError: If transcription fails
        """
        cmd = (
            CommandBuilder("podx-transcribe")
            .add_option("--model", model)
            .add_option("--compute", compute)
            .add_option("--asr-provider", asr_provider)
        )

        if preset:
            cmd.add_option("--preset", preset)

        return await self._run(cmd.build(), stdin_payload=audio, label="transcribe")

    async def align(self, transcript: Dict[str, Any]) -> Dict[str, Any]:
        """Perform word-level alignment asynchronously.

        Args:
            transcript: Transcript dictionary

        Returns:
            Aligned transcript dictionary

        Raises:
            ValidationError: If alignment fails
        """
        cmd = CommandBuilder("podx-align")
        return await self._run(cmd.build(), stdin_payload=transcript, label="align")

    async def diarize(self, transcript: Dict[str, Any]) -> Dict[str, Any]:
        """Perform speaker diarization asynchronously.

        Args:
            transcript: Transcript dictionary (preferably aligned)

        Returns:
            Diarized transcript dictionary

        Raises:
            ValidationError: If diarization fails
        """
        cmd = CommandBuilder("podx-diarize")
        return await self._run(cmd.build(), stdin_payload=transcript, label="diarize")

    async def preprocess(
        self,
        transcript: Dict[str, Any],
        restore: bool = False,
    ) -> Dict[str, Any]:
        """Preprocess transcript asynchronously.

        Args:
            transcript: Transcript dictionary
            restore: Enable semantic restore (LLM-based)

        Returns:
            Preprocessed transcript dictionary

        Raises:
            ValidationError: If preprocessing fails
        """
        cmd = CommandBuilder("podx-preprocess")
        if restore:
            cmd.add_flag("--restore")

        return await self._run(cmd.build(), stdin_payload=transcript, label="preprocess")

    async def deepcast(
        self,
        transcript: Dict[str, Any],
        model: str = "gpt-4",
        temperature: float = 0.7,
        analysis_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Perform AI analysis asynchronously.

        Args:
            transcript: Transcript dictionary
            model: LLM model for analysis
            temperature: Temperature for LLM calls
            analysis_type: Type of analysis to perform

        Returns:
            Deepcast analysis dictionary

        Raises:
            ValidationError: If analysis fails
        """
        cmd = (
            CommandBuilder("podx-deepcast")
            .add_option("--model", model)
            .add_option("--temperature", str(temperature))
        )

        if analysis_type:
            cmd.add_option("--analysis-type", analysis_type)

        return await self._run(cmd.build(), stdin_payload=transcript, label="deepcast")

    async def run_concurrent(
        self, *coroutines
    ) -> List[Any]:
        """Run multiple async operations concurrently.

        Args:
            *coroutines: Coroutines to run concurrently

        Returns:
            List of results in the same order as input coroutines

        Example:
            >>> results = await executor.run_concurrent(
            ...     executor.fetch(show="Podcast 1"),
            ...     executor.fetch(show="Podcast 2"),
            ...     executor.fetch(show="Podcast 3"),
            ... )
        """
        return await asyncio.gather(*coroutines)
