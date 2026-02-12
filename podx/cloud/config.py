"""Cloud configuration for PodX.

Provides CloudConfig dataclass for RunPod settings,
with support for environment variables and validation.
"""

import os
from dataclasses import dataclass, field
from typing import Optional

from .exceptions import CloudError


@dataclass
class CloudConfig:
    """Configuration for RunPod cloud processing.

    Attributes:
        api_key: RunPod API key (from RUNPOD_API_KEY env var)
        endpoint_id: RunPod serverless endpoint ID for transcription (from RUNPOD_ENDPOINT_ID env var)
        diarize_endpoint_id: RunPod serverless endpoint ID for diarization (from RUNPOD_DIARIZE_ENDPOINT_ID env var)
        timeout_seconds: Maximum time to wait for job completion (default: 600s/10min)
        poll_interval_seconds: How often to check job status (default: 2.0s)
        enable_fallback: Whether to fall back to local on failure (default: True)
    """

    api_key: Optional[str] = None
    endpoint_id: Optional[str] = None
    diarize_endpoint_id: Optional[str] = None
    timeout_seconds: int = 600  # 10 minutes max
    poll_interval_seconds: float = 2.0
    enable_fallback: bool = True

    # Internal tracking
    _validated: bool = field(default=False, repr=False)

    @classmethod
    def from_env(cls) -> "CloudConfig":
        """Create configuration from environment variables.

        Environment variables:
            RUNPOD_API_KEY: Required API key
            RUNPOD_ENDPOINT_ID: Required endpoint ID for transcription
            RUNPOD_DIARIZE_ENDPOINT_ID: Optional endpoint ID for diarization
            RUNPOD_TIMEOUT: Optional timeout in seconds (default: 600)
            RUNPOD_POLL_INTERVAL: Optional poll interval (default: 2.0)
            RUNPOD_ENABLE_FALLBACK: Optional fallback flag (default: true)

        Returns:
            CloudConfig populated from environment
        """
        timeout_str = os.getenv("RUNPOD_TIMEOUT", "600")
        poll_str = os.getenv("RUNPOD_POLL_INTERVAL", "2.0")
        fallback_str = os.getenv("RUNPOD_ENABLE_FALLBACK", "true").lower()

        return cls(
            api_key=os.getenv("RUNPOD_API_KEY"),
            endpoint_id=os.getenv("RUNPOD_ENDPOINT_ID"),
            diarize_endpoint_id=os.getenv("RUNPOD_DIARIZE_ENDPOINT_ID"),
            timeout_seconds=int(timeout_str),
            poll_interval_seconds=float(poll_str),
            enable_fallback=fallback_str in ("true", "1", "yes"),
        )

    def validate(self) -> None:
        """Validate that configuration is complete.

        Raises:
            CloudError: If required configuration is missing
        """
        if not self.api_key:
            raise CloudError(
                "RUNPOD_API_KEY not set. Run 'podx cloud setup' to configure.",
                recoverable=False,
            )
        if not self.endpoint_id:
            raise CloudError(
                "RUNPOD_ENDPOINT_ID not set. Run 'podx cloud setup' to configure.",
                recoverable=False,
            )
        self._validated = True

    def validate_for_diarization(self) -> None:
        """Validate that configuration is complete for diarization.

        Raises:
            CloudError: If required configuration is missing
        """
        if not self.api_key:
            raise CloudError(
                "RUNPOD_API_KEY not set. Run 'podx cloud setup' to configure.",
                recoverable=False,
            )
        if not self.diarize_endpoint_id:
            raise CloudError(
                "RUNPOD_DIARIZE_ENDPOINT_ID not set. "
                "Set the environment variable or run 'podx cloud setup' to configure.",
                recoverable=False,
            )
        self._validated = True

    @property
    def is_configured(self) -> bool:
        """Check if cloud is configured for transcription (has API key and endpoint)."""
        return bool(self.api_key and self.endpoint_id)

    @property
    def is_diarization_configured(self) -> bool:
        """Check if cloud is configured for diarization."""
        return bool(self.api_key and self.diarize_endpoint_id)

    @property
    def base_url(self) -> str:
        """Get the RunPod API base URL for transcription endpoint."""
        return f"https://api.runpod.ai/v2/{self.endpoint_id}"

    @property
    def diarize_base_url(self) -> str:
        """Get the RunPod API base URL for diarization endpoint."""
        return f"https://api.runpod.ai/v2/{self.diarize_endpoint_id}"

    @property
    def headers(self) -> dict[str, str]:
        """Get HTTP headers for RunPod API requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
