"""Async pipeline service for concurrent step execution."""

import asyncio
import inspect
import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from ..domain import PipelineConfig, PipelineResult
from ..logging import get_logger
from .async_step_executor import AsyncStepExecutor

logger = get_logger(__name__)


class AsyncPipelineService:
    """Async pipeline orchestration service with concurrent execution support.

    This service enables non-blocking pipeline execution and concurrent
    processing of independent steps, making it ideal for:
    - Web applications (FastAPI, aiohttp)
    - WebSocket streaming
    - Batch processing multiple episodes
    - Real-time progress updates

    Examples:
        >>> config = PipelineConfig(show="My Podcast", deepcast=True)
        >>> service = AsyncPipelineService(config)
        >>> result = await service.execute()

        # Process multiple episodes concurrently
        >>> configs = [
        ...     PipelineConfig(show="Podcast 1", date="2024-10-01"),
        ...     PipelineConfig(show="Podcast 2", date="2024-10-01"),
        ... ]
        >>> results = await asyncio.gather(*[
        ...     AsyncPipelineService(cfg).execute() for cfg in configs
        ... ])
    """

    def __init__(
        self,
        config: PipelineConfig,
        executor: Optional[AsyncStepExecutor] = None,
    ):
        """Initialize async pipeline service.

        Args:
            config: Pipeline configuration
            executor: Optional async executor (created if not provided)
        """
        self.config = config
        self.executor = executor or AsyncStepExecutor(verbose=config.verbose)
        self.start_time = 0.0

    async def _call_progress(
        self,
        callback: Optional[Callable[[str, str], None]],
        step: str,
        status: str,
    ) -> None:
        """Call progress callback, handling both sync and async callbacks."""
        if callback is None:
            return

        # Check if callback is async
        if inspect.iscoroutinefunction(callback):
            await callback(step, status)
        else:
            callback(step, status)

    async def execute(
        self,
        progress_callback: Optional[Callable[[str, str], None]] = None,
    ) -> PipelineResult:
        """Execute the complete pipeline asynchronously.

        This method runs the pipeline steps asynchronously, enabling:
        - Non-blocking execution (doesn't block event loop)
        - Progress updates via callbacks
        - Graceful cancellation support

        Args:
            progress_callback: Optional callback for progress updates (step_name, status)

        Returns:
            PipelineResult with execution details

        Raises:
            ValidationError: If configuration is invalid or execution fails
            asyncio.CancelledError: If execution is cancelled

        Example:
            >>> async def on_progress(step: str, status: str):
            ...     print(f"[{step}] {status}")
            >>> result = await service.execute(progress_callback=on_progress)
        """
        self.start_time = time.time()
        result = PipelineResult(workdir=Path("."))

        try:
            # 1. Fetch episode metadata
            await self._call_progress(progress_callback, "fetch", "Fetching episode metadata...")

            meta = await self._execute_fetch()

            # 2. Determine working directory
            workdir = self._determine_workdir(meta)
            result.workdir = workdir
            workdir.mkdir(parents=True, exist_ok=True)

            # Save metadata
            (workdir / "episode-meta.json").write_text(json.dumps(meta, indent=2))
            result.artifacts["meta"] = str(workdir / "episode-meta.json")
            result.steps_completed.append("fetch")

            # 3. Transcode audio
            await self._call_progress(progress_callback, "transcode", "Transcoding audio...")

            audio_meta_file = workdir / "audio-meta.json"
            if audio_meta_file.exists():
                audio = json.loads(audio_meta_file.read_text())
                await self._call_progress(progress_callback, "transcode", "Using existing transcoded audio")
            else:
                audio = await self.executor.transcode(
                    meta=meta,
                    fmt=self.config.fmt,
                    outdir=workdir,
                )
                audio_meta_file.write_text(json.dumps(audio, indent=2))

            result.artifacts["audio"] = str(audio_meta_file)
            result.steps_completed.append("transcode")

            # 4. Transcribe audio
            await self._call_progress(progress_callback, "transcribe", "Transcribing audio...")

            transcript = await self.executor.transcribe(
                audio=audio,
                model=self.config.model,
                compute=self.config.compute,
                asr_provider=self.config.asr_provider or "auto",
                preset=self.config.preset,
            )

            transcript_file = workdir / f"transcript-{self.config.model}.json"
            transcript_file.write_text(json.dumps(transcript, indent=2))
            result.artifacts["transcript"] = str(transcript_file)
            result.steps_completed.append("transcribe")

            # 5. Enhancement pipeline (can run some steps concurrently)
            latest_transcript = transcript

            if self.config.preprocess:
                await self._call_progress(progress_callback, "preprocess", "Preprocessing transcript...")

                latest_transcript = await self.executor.preprocess(
                    transcript=latest_transcript,
                    restore=self.config.restore,
                )
                preprocess_file = workdir / f"transcript-preprocessed-{self.config.model}.json"
                preprocess_file.write_text(json.dumps(latest_transcript, indent=2))
                result.artifacts["preprocessed"] = str(preprocess_file)
                result.steps_completed.append("preprocess")

            # Run align and diarize concurrently if both enabled
            # (they can run independently on the same input)
            if self.config.align and self.config.diarize:
                await self._call_progress(progress_callback, "enhance", "Running alignment and diarization concurrently...")

                aligned_coro = self.executor.align(latest_transcript)
                diarized_coro = self.executor.diarize(latest_transcript)

                aligned, diarized = await asyncio.gather(aligned_coro, diarized_coro)

                # Save both
                aligned_file = workdir / f"transcript-aligned-{self.config.model}.json"
                aligned_file.write_text(json.dumps(aligned, indent=2))
                result.artifacts["aligned"] = str(aligned_file)

                diarized_file = workdir / f"transcript-diarized-{self.config.model}.json"
                diarized_file.write_text(json.dumps(diarized, indent=2))
                result.artifacts["diarized"] = str(diarized_file)

                # Use diarized as latest (has both alignment and speaker info)
                latest_transcript = diarized
                result.steps_completed.extend(["align", "diarize"])

            elif self.config.align:
                await self._call_progress(progress_callback, "align", "Aligning transcript...")

                latest_transcript = await self.executor.align(latest_transcript)
                aligned_file = workdir / f"transcript-aligned-{self.config.model}.json"
                aligned_file.write_text(json.dumps(latest_transcript, indent=2))
                result.artifacts["aligned"] = str(aligned_file)
                result.steps_completed.append("align")

            elif self.config.diarize:
                await self._call_progress(progress_callback, "diarize", "Diarizing transcript...")

                latest_transcript = await self.executor.diarize(latest_transcript)
                diarized_file = workdir / f"transcript-diarized-{self.config.model}.json"
                diarized_file.write_text(json.dumps(latest_transcript, indent=2))
                result.artifacts["diarized"] = str(diarized_file)
                result.steps_completed.append("diarize")

            # Save latest.json
            (workdir / "latest.json").write_text(json.dumps(latest_transcript, indent=2))
            result.artifacts["latest"] = str(workdir / "latest.json")

            # 6. Deepcast analysis
            if self.config.deepcast:
                await self._call_progress(progress_callback, "deepcast", "Running AI analysis...")

                deepcast_result = await self.executor.deepcast(
                    transcript=latest_transcript,
                    model=self.config.deepcast_model,
                    temperature=self.config.deepcast_temp,
                    analysis_type=self.config.analysis_type,
                )

                model_suffix = self.config.deepcast_model.replace(".", "_").replace("-", "_")
                deepcast_file = workdir / f"deepcast-brief-{model_suffix}.json"
                deepcast_file.write_text(json.dumps(deepcast_result, indent=2))
                result.artifacts["deepcast"] = str(deepcast_file)
                result.steps_completed.append("deepcast")

            # Update duration
            result.duration = time.time() - self.start_time

            await self._call_progress(progress_callback, "complete", f"Pipeline completed in {result.duration:.2f}s")

            return result

        except asyncio.CancelledError:
            logger.info("Pipeline execution cancelled")
            raise
        except Exception as e:
            result.errors.append(str(e))
            result.duration = time.time() - self.start_time
            logger.error("Pipeline execution failed", error=str(e))
            raise

    async def _execute_fetch(self) -> Dict[str, Any]:
        """Execute fetch step asynchronously."""
        from ..errors import ValidationError

        # YouTube URL mode
        if self.config.youtube_url:
            from ..youtube import is_youtube_url, get_youtube_metadata

            if not is_youtube_url(self.config.youtube_url):
                raise ValidationError(f"Invalid YouTube URL: {self.config.youtube_url}")

            meta = get_youtube_metadata(self.config.youtube_url)
            return {
                "show": meta["channel"],
                "episode_title": meta["title"],
                "episode_published": meta["upload_date"],
            }

        # RSS/Podcast mode
        return await self.executor.fetch(
            show=self.config.show,
            rss_url=self.config.rss_url,
            date=self.config.date,
            title_contains=self.config.title_contains,
        )

    def _determine_workdir(self, meta: Dict[str, Any]) -> Path:
        """Determine working directory from metadata."""
        from ..utils import generate_workdir

        if self.config.workdir:
            return self.config.workdir

        show_name = meta.get("show", "Unknown")
        episode_date = meta.get("episode_published", "unknown")

        return generate_workdir(show_name, episode_date)

    @staticmethod
    async def process_batch(
        configs: list[PipelineConfig],
        max_concurrent: int = 3,
        progress_callback: Optional[Callable[[int, str, str], None]] = None,
    ) -> list[PipelineResult]:
        """Process multiple episodes concurrently with concurrency limit.

        Args:
            configs: List of pipeline configurations
            max_concurrent: Maximum number of concurrent executions (default: 3)
            progress_callback: Optional callback (index, step, status)

        Returns:
            List of PipelineResults in same order as configs

        Example:
            >>> configs = [
            ...     PipelineConfig(show="Podcast 1", date="2024-10-01"),
            ...     PipelineConfig(show="Podcast 2", date="2024-10-01"),
            ...     PipelineConfig(show="Podcast 3", date="2024-10-01"),
            ... ]
            >>> results = await AsyncPipelineService.process_batch(
            ...     configs, max_concurrent=2
            ... )
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_with_semaphore(idx: int, config: PipelineConfig):
            async with semaphore:
                service = AsyncPipelineService(config)

                def callback(step: str, status: str):
                    if progress_callback:
                        progress_callback(idx, step, status)

                return await service.execute(progress_callback=callback)

        tasks = [
            process_with_semaphore(i, cfg)
            for i, cfg in enumerate(configs)
        ]

        return await asyncio.gather(*tasks)
