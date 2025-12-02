"""Cloud-specific exceptions for PodX.

Provides a clear hierarchy of errors for cloud operations,
enabling specific error handling and helpful user messages.
"""

from typing import Optional


class CloudError(Exception):
    """Base exception for all cloud-related errors.

    Attributes:
        message: Human-readable error message
        recoverable: Whether fallback to local processing is possible
    """

    def __init__(self, message: str, recoverable: bool = True):
        super().__init__(message)
        self.message = message
        self.recoverable = recoverable


class CloudAuthError(CloudError):
    """Authentication or authorization failed.

    Raised when:
    - API key is missing or invalid
    - API key has insufficient permissions
    """

    def __init__(self, message: str = "Invalid or missing RunPod API key"):
        super().__init__(message, recoverable=False)


class EndpointNotFoundError(CloudError):
    """Endpoint not found or inaccessible.

    Raised when:
    - Endpoint ID is incorrect
    - Endpoint has been deleted
    - Endpoint is in a region not accessible
    """

    def __init__(self, endpoint_id: str):
        message = (
            f"Endpoint '{endpoint_id}' not found. "
            "It may have been deleted. Run 'podx cloud setup' to reconfigure."
        )
        super().__init__(message, recoverable=False)


class UploadError(CloudError):
    """Failed to upload audio to cloud storage.

    Raised when:
    - Network error during upload
    - File too large
    - Storage quota exceeded
    """

    def __init__(self, message: str, cause: Optional[Exception] = None):
        full_message = f"Failed to upload audio: {message}"
        super().__init__(full_message, recoverable=True)
        self.__cause__ = cause


class JobFailedError(CloudError):
    """Transcription job failed on the server.

    Raised when:
    - Worker encountered an error
    - Out of memory
    - Unsupported audio format
    """

    def __init__(self, job_id: str, error_message: str):
        message = f"Transcription job {job_id} failed: {error_message}"
        super().__init__(message, recoverable=True)
        self.job_id = job_id


class CloudTimeoutError(CloudError):
    """Job timed out waiting for completion.

    Raised when:
    - Job takes longer than configured timeout
    - Worker is stuck or unresponsive
    """

    def __init__(self, job_id: str, timeout_seconds: int):
        message = (
            f"Transcription job {job_id} timed out after {timeout_seconds} seconds. "
            "The endpoint may be experiencing high load."
        )
        super().__init__(message, recoverable=True)
        self.job_id = job_id
        self.timeout_seconds = timeout_seconds
