"""RunPod API client for cloud transcription.

Handles submitting jobs, polling for status,
and retrieving results from RunPod serverless endpoints.
Audio is passed as a URL (hosted on R2) rather than inline.
"""

import time
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

# Retry configuration
MAX_SUBMIT_RETRIES = 3
RETRY_DELAY_SECONDS = 5

logger = get_logger(__name__)


class RunPodClient:
    """Client for interacting with RunPod serverless API.

    Handles the full lifecycle of a cloud transcription job:
    1. Submit job with audio URL (hosted on R2)
    2. Poll for completion
    3. Return results

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
        audio_url: str,
        model: str = "turbo",
        language: str = "auto",
    ) -> str:
        """Submit a transcription job with an audio URL.

        The RunPod worker downloads the audio from the URL and transcribes it.

        Args:
            audio_url: Presigned URL to audio file (hosted on R2)
            model: Whisper model to use (default: turbo)
            language: Language code or "auto" for detection

        Returns:
            Job ID for tracking

        Raises:
            UploadError: If submission fails
            CloudAuthError: If API key is invalid
            EndpointNotFoundError: If endpoint doesn't exist
        """
        logger.info(
            "Submitting transcription job",
            model=model,
            language=language,
        )

        # Build request payload
        payload = {
            "input": {
                "audio": audio_url,
                "model": model,
                "word_timestamps": True,
            }
        }

        # Only set language if not auto-detect
        if language != "auto":
            payload["input"]["language"] = language

        # Submit job with retry logic
        last_error: Optional[Exception] = None
        for attempt in range(MAX_SUBMIT_RETRIES):
            try:
                response = self.client.post(
                    f"{self.config.base_url}/run",
                    json=payload,
                )
                break  # Success
            except httpx.RequestError as e:
                last_error = e
                if attempt < MAX_SUBMIT_RETRIES - 1:
                    logger.warning(
                        "Job submission failed, retrying",
                        attempt=attempt + 1,
                        error=str(e),
                    )
                    time.sleep(RETRY_DELAY_SECONDS * (attempt + 1))
                else:
                    raise UploadError(
                        f"Network error after {MAX_SUBMIT_RETRIES} attempts: {e}",
                        cause=e,
                    )
        else:
            raise UploadError(f"Network error: {last_error}", cause=last_error)

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

            # Log on status change
            if status != last_status:
                last_status = status
                logger.debug(
                    "Job status update",
                    job_id=job_id,
                    status=status,
                    elapsed=round(elapsed, 1),
                )

            # Report progress on every poll so the UI stays fresh
            message = self._format_status_message(status, elapsed)
            if progress_callback:
                progress_callback(message)

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
