"""RunPod API client for cloud transcription.

Handles uploading audio, submitting jobs, polling for status,
and retrieving results from RunPod serverless endpoints.
"""

import base64
import time
from pathlib import Path
from typing import Any, Callable, Optional

import httpx

from ..logging import get_logger
from .config import CloudConfig
from .exceptions import (
    CloudAuthError,
    CloudTimeoutError,
    EndpointNotFoundError,
    JobFailedError,
    UploadError,
)

logger = get_logger(__name__)


class RunPodClient:
    """Client for interacting with RunPod serverless API.

    Handles the full lifecycle of a cloud transcription job:
    1. Upload audio (base64 encoded in request)
    2. Submit transcription job
    3. Poll for completion
    4. Return results

    Attributes:
        config: Cloud configuration with credentials and settings
    """

    # Job status constants
    STATUS_QUEUED = "IN_QUEUE"
    STATUS_IN_PROGRESS = "IN_PROGRESS"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_FAILED = "FAILED"

    def __init__(self, config: CloudConfig):
        """Initialize RunPod client.

        Args:
            config: Cloud configuration (must be validated)
        """
        self.config = config
        self._client: Optional[httpx.Client] = None

    @property
    def client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                timeout=httpx.Timeout(60.0, read=300.0),  # 5 min read for large files
                headers=self.config.headers,
            )
        return self._client

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "RunPodClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def submit_job(
        self,
        audio_path: Path,
        model: str = "large-v3-turbo",
        language: str = "auto",
    ) -> str:
        """Submit a transcription job with audio data.

        The audio is base64 encoded and sent inline with the request.
        This avoids the need for separate blob storage.

        Args:
            audio_path: Path to audio file
            model: Whisper model to use (default: large-v3-turbo)
            language: Language code or "auto" for detection

        Returns:
            Job ID for tracking

        Raises:
            UploadError: If audio encoding or upload fails
            CloudAuthError: If API key is invalid
            EndpointNotFoundError: If endpoint doesn't exist
        """
        if not audio_path.exists():
            raise UploadError(f"Audio file not found: {audio_path}")

        # Read and base64 encode audio
        try:
            audio_bytes = audio_path.read_bytes()
            audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
        except Exception as e:
            raise UploadError(f"Failed to read audio file: {e}", cause=e)

        file_size_mb = len(audio_bytes) / (1024 * 1024)
        logger.info(
            "Submitting transcription job",
            model=model,
            audio_size_mb=round(file_size_mb, 2),
            language=language,
        )

        # Build request payload
        payload = {
            "input": {
                "audio_base64": audio_base64,
                "model": model,
                "language": None if language == "auto" else language,
                "word_timestamps": True,
                "vad_filter": True,
            }
        }

        # Submit job
        try:
            response = self.client.post(
                f"{self.config.base_url}/run",
                json=payload,
            )
        except httpx.RequestError as e:
            raise UploadError(f"Network error: {e}", cause=e)

        # Handle response
        if response.status_code == 401:
            raise CloudAuthError("Invalid RunPod API key")
        if response.status_code == 404:
            raise EndpointNotFoundError(self.config.endpoint_id or "unknown")
        if response.status_code >= 400:
            raise UploadError(f"API error {response.status_code}: {response.text}")

        data = response.json()
        job_id = data.get("id")
        if not job_id:
            raise UploadError(f"No job ID in response: {data}")

        logger.info("Job submitted", job_id=job_id)
        return job_id

    def get_status(self, job_id: str) -> dict[str, Any]:
        """Get job status.

        Args:
            job_id: Job ID from submit_job

        Returns:
            Status dict with 'status' and optionally 'output' or 'error'

        Raises:
            CloudAuthError: If API key is invalid
            EndpointNotFoundError: If endpoint doesn't exist
        """
        try:
            response = self.client.get(f"{self.config.base_url}/status/{job_id}")
        except httpx.RequestError as e:
            logger.warning("Status check failed", job_id=job_id, error=str(e))
            return {"status": "UNKNOWN", "error": str(e)}

        if response.status_code == 401:
            raise CloudAuthError("Invalid RunPod API key")
        if response.status_code == 404:
            raise EndpointNotFoundError(self.config.endpoint_id or "unknown")

        return response.json()

    def wait_for_completion(
        self,
        job_id: str,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> dict[str, Any]:
        """Poll until job completes or times out.

        Args:
            job_id: Job ID from submit_job
            progress_callback: Optional callback for status updates

        Returns:
            Transcription result from the job output

        Raises:
            CloudTimeoutError: If job exceeds timeout
            JobFailedError: If job fails on the server
        """
        start_time = time.time()
        last_status = ""
        poll_count = 0

        while True:
            elapsed = time.time() - start_time
            if elapsed > self.config.timeout_seconds:
                raise CloudTimeoutError(job_id, self.config.timeout_seconds)

            status_data = self.get_status(job_id)
            status = status_data.get("status", "UNKNOWN")

            # Report progress on status change
            if status != last_status:
                last_status = status
                message = self._format_status_message(status, elapsed)
                if progress_callback:
                    progress_callback(message)
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
                    "Job completed",
                    job_id=job_id,
                    elapsed=round(elapsed, 1),
                )
                return output

            if status == self.STATUS_FAILED:
                error = status_data.get("error", "Unknown error")
                raise JobFailedError(job_id, error)

            # Wait before next poll
            poll_count += 1
            time.sleep(self.config.poll_interval_seconds)

    def _format_status_message(self, status: str, elapsed: float) -> str:
        """Format a human-readable status message."""
        elapsed_str = f"{int(elapsed)}s"

        if status == self.STATUS_QUEUED:
            return f"Waiting for GPU worker... ({elapsed_str})"
        if status == self.STATUS_IN_PROGRESS:
            return f"Transcribing on cloud GPU... ({elapsed_str})"
        if status == self.STATUS_COMPLETED:
            return f"Transcription complete ({elapsed_str})"
        if status == self.STATUS_FAILED:
            return "Transcription failed"

        return f"Status: {status} ({elapsed_str})"

    def test_connection(self) -> bool:
        """Test that the endpoint is accessible.

        Returns:
            True if endpoint responds, False otherwise
        """
        try:
            response = self.client.get(f"{self.config.base_url}/health")
            return response.status_code == 200
        except Exception as e:
            logger.debug("Health check failed", error=str(e))
            return False
