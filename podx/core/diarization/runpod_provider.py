"""RunPod cloud diarization provider.

Provides cloud-accelerated diarization via RunPod serverless GPUs,
with optional fallback to local processing on failure.
"""

from __future__ import annotations

import base64
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import httpx

from ...cloud import CloudConfig, CloudError
from ...cloud.exceptions import (
    CloudAuthError,
    CloudTimeoutError,
    EndpointNotFoundError,
    JobFailedError,
    UploadError,
)
from ...logging import get_logger
from .base import (
    DiarizationConfig,
    DiarizationProvider,
    DiarizationProviderError,
    DiarizationResult,
)

if TYPE_CHECKING:
    from .local_provider import LocalDiarizationProvider

logger = get_logger(__name__)


class RunPodDiarizationProvider(DiarizationProvider):
    """Diarization provider using RunPod serverless GPUs.

    Offloads diarization to cloud GPUs for faster processing.
    Automatically falls back to local processing on failure
    (unless disabled).

    The cloud endpoint is expected to:
    1. Receive audio (base64) and transcript segments
    2. Run pyannote diarization
    3. Return speaker-labeled segments

    Features:
    - Cloud-accelerated pyannote diarization
    - Automatic retry with local fallback
    - Progress callbacks for status updates

    Environment Variables:
        RUNPOD_API_KEY: Required API key
        RUNPOD_DIARIZE_ENDPOINT_ID: Required diarization endpoint ID
    """

    # Job status constants (same as RunPodClient)
    STATUS_QUEUED = "IN_QUEUE"
    STATUS_IN_PROGRESS = "IN_PROGRESS"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_FAILED = "FAILED"

    def __init__(
        self,
        config: DiarizationConfig,
        cloud_config: Optional[CloudConfig] = None,
        enable_fallback: Optional[bool] = None,
    ):
        """Initialize RunPod diarization provider.

        Args:
            config: Diarization configuration
            cloud_config: Optional cloud config (defaults to from_env)
            enable_fallback: Override fallback setting from cloud config
        """
        super().__init__(config)

        # Load cloud config from environment if not provided
        self.cloud_config = cloud_config or CloudConfig.from_env()

        # Override fallback if specified
        if enable_fallback is not None:
            self.cloud_config.enable_fallback = enable_fallback

        # Validate configuration for diarization (raises CloudError if missing)
        self.cloud_config.validate_for_diarization()

        # Create HTTP client
        self._client: Optional[httpx.Client] = None

        # Lazy-init fallback provider
        self._fallback_provider: Optional["LocalDiarizationProvider"] = None

    @property
    def name(self) -> str:
        """Get provider name."""
        return "runpod"

    @property
    def client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                timeout=httpx.Timeout(60.0, read=300.0),
                headers=self.cloud_config.headers,
            )
        return self._client

    @property
    def fallback_provider(self) -> Optional["LocalDiarizationProvider"]:
        """Get fallback provider, creating if needed."""
        if not self.cloud_config.enable_fallback:
            return None
        if self._fallback_provider is None:
            from .local_provider import LocalDiarizationProvider

            self._fallback_provider = LocalDiarizationProvider(self.config)
        return self._fallback_provider

    def diarize(
        self,
        audio_path: Path,
        transcript_segments: List[Dict[str, Any]],
    ) -> DiarizationResult:
        """Diarize audio using RunPod cloud GPU.

        Uploads audio and transcript segments to RunPod, runs diarization,
        polls for completion, and returns results. Falls back to local
        processing on failure if enabled.

        Args:
            audio_path: Path to audio file
            transcript_segments: List of transcript segments with text and timing

        Returns:
            DiarizationResult with speaker-labeled segments

        Raises:
            DiarizationProviderError: If diarization fails and no fallback
            FileNotFoundError: If audio file doesn't exist
        """
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info(
            "Starting RunPod cloud diarization",
            audio=str(audio_path),
            segments_count=len(transcript_segments),
            fallback_enabled=self.cloud_config.enable_fallback,
        )

        try:
            return self._diarize_cloud(audio_path, transcript_segments)
        except CloudError as e:
            return self._handle_cloud_error(e, audio_path, transcript_segments)
        except Exception as e:
            logger.error("Unexpected error during cloud diarization", error=str(e))
            if self.fallback_provider:
                self._report_progress(f"Cloud error: {e}. Falling back to local...")
                return self.fallback_provider.diarize(audio_path, transcript_segments)
            raise DiarizationProviderError(f"Cloud diarization failed: {e}") from e

    def _diarize_cloud(
        self,
        audio_path: Path,
        transcript_segments: List[Dict[str, Any]],
    ) -> DiarizationResult:
        """Perform cloud diarization."""
        # Submit job with audio and segments
        self._report_progress("Uploading audio to RunPod...")
        job_id = self._submit_job(audio_path, transcript_segments)

        # Wait for completion
        self._report_progress("Diarizing on cloud GPU...")
        result = self._wait_for_completion(job_id)

        # Convert result to DiarizationResult
        return self._convert_result(result, audio_path)

    def _submit_job(
        self,
        audio_path: Path,
        transcript_segments: List[Dict[str, Any]],
    ) -> str:
        """Submit a diarization job with audio and transcript data.

        Args:
            audio_path: Path to audio file
            transcript_segments: Transcript segments with timing

        Returns:
            Job ID for tracking

        Raises:
            UploadError: If audio encoding or upload fails
            CloudAuthError: If API key is invalid
            EndpointNotFoundError: If endpoint doesn't exist
        """
        # Read and base64 encode audio
        try:
            audio_bytes = audio_path.read_bytes()
            audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
        except Exception as e:
            raise UploadError(f"Failed to read audio file: {e}", cause=e)

        file_size_mb = len(audio_bytes) / (1024 * 1024)
        logger.info(
            "Submitting diarization job",
            audio_size_mb=round(file_size_mb, 2),
            segments_count=len(transcript_segments),
        )

        # Build request payload
        payload = {
            "input": {
                "audio_base64": audio_base64,
                "transcript_segments": transcript_segments,
                "num_speakers": self.config.num_speakers,
                "min_speakers": self.config.min_speakers,
                "max_speakers": self.config.max_speakers,
                "language": self.config.language,
            }
        }

        # Submit job
        try:
            response = self.client.post(
                f"{self.cloud_config.diarize_base_url}/run",
                json=payload,
            )
        except httpx.RequestError as e:
            raise UploadError(f"Network error: {e}", cause=e)

        # Handle response
        if response.status_code == 401:
            raise CloudAuthError("Invalid RunPod API key")
        if response.status_code == 404:
            raise EndpointNotFoundError(self.cloud_config.diarize_endpoint_id or "unknown")
        if response.status_code >= 400:
            raise UploadError(f"API error {response.status_code}: {response.text}")

        data = response.json()
        job_id = data.get("id")
        if not job_id:
            raise UploadError(f"No job ID in response: {data}")

        logger.info("Diarization job submitted", job_id=job_id)
        return job_id

    def _get_status(self, job_id: str) -> Dict[str, Any]:
        """Get job status.

        Args:
            job_id: Job ID from submit_job

        Returns:
            Status dict with 'status' and optionally 'output' or 'error'
        """
        try:
            response = self.client.get(f"{self.cloud_config.diarize_base_url}/status/{job_id}")
        except httpx.RequestError as e:
            logger.warning("Status check failed", job_id=job_id, error=str(e))
            return {"status": "UNKNOWN", "error": str(e)}

        if response.status_code == 401:
            raise CloudAuthError("Invalid RunPod API key")
        if response.status_code == 404:
            raise EndpointNotFoundError(self.cloud_config.diarize_endpoint_id or "unknown")

        return response.json()

    def _wait_for_completion(
        self,
        job_id: str,
    ) -> Dict[str, Any]:
        """Poll until job completes or times out.

        Args:
            job_id: Job ID from submit_job

        Returns:
            Diarization result from the job output

        Raises:
            CloudTimeoutError: If job exceeds timeout
            JobFailedError: If job fails on the server
        """
        start_time = time.time()
        last_status = ""

        while True:
            elapsed = time.time() - start_time
            if elapsed > self.cloud_config.timeout_seconds:
                raise CloudTimeoutError(job_id, self.cloud_config.timeout_seconds)

            status_data = self._get_status(job_id)
            status = status_data.get("status", "UNKNOWN")

            # Report progress on status change
            if status != last_status:
                last_status = status
                message = self._format_status_message(status, elapsed)
                self._report_progress(message)
                logger.debug(
                    "Job status update",
                    job_id=job_id,
                    status=status,
                    elapsed=round(elapsed, 1),
                )

            # Check terminal states
            if status == self.STATUS_COMPLETED:
                output = status_data.get("output", {})
                logger.info(
                    "Diarization job completed",
                    job_id=job_id,
                    elapsed=round(elapsed, 1),
                )
                return output

            if status == self.STATUS_FAILED:
                error = status_data.get("error", "Unknown error")
                raise JobFailedError(job_id, error)

            # Wait before next poll
            time.sleep(self.cloud_config.poll_interval_seconds)

    def _format_status_message(self, status: str, elapsed: float) -> str:
        """Format a human-readable status message."""
        elapsed_str = f"{int(elapsed)}s"

        if status == self.STATUS_QUEUED:
            return f"Waiting for GPU worker... ({elapsed_str})"
        if status == self.STATUS_IN_PROGRESS:
            return f"Diarizing on cloud GPU... ({elapsed_str})"
        if status == self.STATUS_COMPLETED:
            return f"Diarization complete ({elapsed_str})"
        if status == self.STATUS_FAILED:
            return "Diarization failed"

        return f"Status: {status} ({elapsed_str})"

    def _convert_result(
        self,
        cloud_result: Dict[str, Any],
        audio_path: Path,
    ) -> DiarizationResult:
        """Convert RunPod result to DiarizationResult.

        Args:
            cloud_result: Raw result from RunPod API
            audio_path: Original audio path

        Returns:
            DiarizationResult in standard format
        """
        segments = cloud_result.get("segments", [])

        # Count speakers
        speakers = set()
        for seg in segments:
            if seg.get("speaker"):
                speakers.add(seg["speaker"])
            for word in seg.get("words", []):
                if word.get("speaker"):
                    speakers.add(word["speaker"])

        logger.info(
            "RunPod diarization completed",
            segments_count=len(segments),
            speakers_count=len(speakers),
        )

        self._report_progress(f"Diarization complete ({len(segments)} segments)")

        return DiarizationResult(
            audio_path=str(audio_path.resolve()),
            segments=segments,
            provider=self.name,
            speakers_count=len(speakers),
            language=self.config.language,
            chunked=False,  # Cloud handles chunking internally
            chunk_info=None,
        )

    def _handle_cloud_error(
        self,
        error: CloudError,
        audio_path: Path,
        transcript_segments: List[Dict[str, Any]],
    ) -> DiarizationResult:
        """Handle cloud error with optional fallback.

        Args:
            error: The cloud error that occurred
            audio_path: Audio file for fallback diarization
            transcript_segments: Segments for fallback

        Returns:
            DiarizationResult from fallback if enabled

        Raises:
            DiarizationProviderError: If no fallback and error is not recoverable
        """
        logger.warning(
            "Cloud diarization failed",
            error=str(error),
            recoverable=error.recoverable,
            fallback_enabled=self.cloud_config.enable_fallback,
        )

        if error.recoverable and self.fallback_provider:
            self._report_progress(f"Cloud failed: {error}. Falling back to local...")
            return self.fallback_provider.diarize(audio_path, transcript_segments)

        raise DiarizationProviderError(str(error)) from error

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "RunPodDiarizationProvider":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
