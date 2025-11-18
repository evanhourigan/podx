"""Background worker for processing jobs."""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from podx.logging import get_logger

logger = get_logger(__name__)


class BackgroundWorker:
    """Processes jobs in the background.

    Uses AsyncPodxClient to run actual processing tasks and updates
    job progress in the database.
    """

    def __init__(self):
        """Initialize worker."""
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the background worker."""
        if self._running:
            logger.warning("Worker already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info("Background worker started")

    async def stop(self) -> None:
        """Stop the background worker."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Background worker stopped")

    async def _run(self) -> None:
        """Main worker loop."""
        from podx.server.database import async_session_factory

        while self._running:
            try:
                # Create new session for this iteration
                async with async_session_factory() as session:
                    from podx.server.services.job_manager import JobManager

                    job_manager = JobManager(session)

                    # Get next queued job
                    jobs, _ = await job_manager.list_jobs(status="queued", limit=1)

                    if jobs:
                        job = jobs[0]
                        logger.info(f"Processing job {job.id} ({job.job_type})")
                        await self.process_job(job.id)
                    else:
                        # No jobs, sleep for a bit
                        await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Worker error: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def process_job(self, job_id: str) -> None:
        """Process a single job.

        Args:
            job_id: Job ID to process
        """
        from podx.server.database import async_session_factory
        from podx.server.services.job_manager import JobManager

        try:
            # Create session for this job
            async with async_session_factory() as session:
                job_manager = JobManager(session)

                # Get job
                job = await job_manager.get_job(job_id)
                if not job:
                    logger.error(f"Job {job_id} not found")
                    return

                # Mark as running
                await job_manager.update_job(
                    job_id,
                    status="running",
                    started_at=datetime.now(timezone.utc),
                )

                # Route to appropriate handler
                if job.job_type == "transcribe":
                    await self.run_transcribe(job_id, job.input_params or {})
                elif job.job_type == "diarize":
                    await self.run_diarize(job_id, job.input_params or {})
                elif job.job_type == "deepcast":
                    await self.run_deepcast(job_id, job.input_params or {})
                elif job.job_type == "pipeline":
                    await self.run_pipeline(job_id, job.input_params or {})
                else:
                    raise ValueError(f"Unknown job type: {job.job_type}")

        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}", exc_info=True)
            async with async_session_factory() as session:
                job_manager = JobManager(session)
                await job_manager.update_job(
                    job_id,
                    status="failed",
                    error=str(e),
                    completed_at=datetime.now(timezone.utc),
                )

    async def run_transcribe(self, job_id: str, params: Dict[str, Any]) -> None:
        """Run transcription job.

        Args:
            job_id: Job ID
            params: Job parameters
        """
        from podx.server.database import async_session_factory

        def progress_callback(percentage: float, message: str) -> None:
            """Update job progress (sync callback)."""
            # Schedule async update with new session
            async def update():
                async with async_session_factory() as session:
                    from podx.server.services.job_manager import JobManager

                    job_manager = JobManager(session)
                    await job_manager.update_job(
                        job_id,
                        progress={"percentage": percentage, "message": message},
                    )

            asyncio.create_task(update())

        try:
            from podx.api import AsyncPodxClient

            # Create client with progress callback
            async with AsyncPodxClient(progress_callback=progress_callback) as client:
                # Extract params
                audio_url = params.get("audio_url")
                model = params.get("model", "base")

                if not audio_url:
                    raise ValueError("audio_url is required")

                # Run transcription
                result = await client.transcribe(audio_path=audio_url, model=model)

                # Mark as completed with new session
                async with async_session_factory() as session:
                    from podx.server.services.job_manager import JobManager

                    job_manager = JobManager(session)
                    await job_manager.update_job(
                        job_id,
                        status="completed",
                        result={"transcript_path": str(result)},
                        completed_at=datetime.now(timezone.utc),
                    )

        except Exception as e:
            raise RuntimeError(f"Transcription failed: {e}") from e

    async def run_diarize(self, job_id: str, params: Dict[str, Any]) -> None:
        """Run diarization job.

        Args:
            job_id: Job ID
            params: Job parameters
        """
        from podx.server.database import async_session_factory

        # Placeholder for diarization
        await asyncio.sleep(0.1)
        async with async_session_factory() as session:
            from podx.server.services.job_manager import JobManager

            job_manager = JobManager(session)
            await job_manager.update_job(
                job_id,
                status="completed",
                result={"message": "Diarization not yet implemented"},
                completed_at=datetime.now(timezone.utc),
            )

    async def run_deepcast(self, job_id: str, params: Dict[str, Any]) -> None:
        """Run deepcast job.

        Args:
            job_id: Job ID
            params: Job parameters
        """
        from podx.server.database import async_session_factory

        # Placeholder for deepcast
        await asyncio.sleep(0.1)
        async with async_session_factory() as session:
            from podx.server.services.job_manager import JobManager

            job_manager = JobManager(session)
            await job_manager.update_job(
                job_id,
                status="completed",
                result={"message": "Deepcast not yet implemented"},
                completed_at=datetime.now(timezone.utc),
            )

    async def run_pipeline(self, job_id: str, params: Dict[str, Any]) -> None:
        """Run full pipeline job.

        Args:
            job_id: Job ID
            params: Job parameters
        """
        from podx.server.database import async_session_factory

        # Placeholder for pipeline
        await asyncio.sleep(0.1)
        async with async_session_factory() as session:
            from podx.server.services.job_manager import JobManager

            job_manager = JobManager(session)
            await job_manager.update_job(
                job_id,
                status="completed",
                result={"message": "Pipeline not yet implemented"},
                completed_at=datetime.now(timezone.utc),
            )
