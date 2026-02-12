"""Cloud configuration for PodX.

Provides CloudConfig dataclass for RunPod + Cloudflare R2 settings,
with support for environment variables and validation.
"""

import os
from dataclasses import dataclass, field
from typing import Optional

from .exceptions import CloudError


@dataclass
class CloudConfig:
    """Configuration for RunPod cloud processing + R2 storage.

    Attributes:
        api_key: RunPod API key
        endpoint_id: RunPod serverless endpoint ID for transcription
        diarize_endpoint_id: RunPod serverless endpoint ID for diarization
        r2_account_id: Cloudflare account ID
        r2_access_key_id: R2 API token access key ID
        r2_secret_access_key: R2 API token secret access key
        r2_bucket_name: R2 bucket name for audio uploads
        timeout_seconds: Maximum time to wait for job completion (default: 1800s/30min)
        poll_interval_seconds: How often to check job status (default: 2.0s)
        enable_fallback: Whether to fall back to local on failure (default: True)
    """

    # RunPod
    api_key: Optional[str] = None
    endpoint_id: Optional[str] = None
    diarize_endpoint_id: Optional[str] = None

    # Cloudflare R2
    r2_account_id: Optional[str] = None
    r2_access_key_id: Optional[str] = None
    r2_secret_access_key: Optional[str] = None
    r2_bucket_name: Optional[str] = None

    # Settings
    timeout_seconds: int = 1800  # 30 minutes max (long podcasts can take 20+ min)
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
            R2_ACCOUNT_ID: Cloudflare account ID
            R2_ACCESS_KEY_ID: R2 API token access key
            R2_SECRET_ACCESS_KEY: R2 API token secret
            R2_BUCKET_NAME: R2 bucket name
            RUNPOD_TIMEOUT: Optional timeout in seconds (default: 1800)
            RUNPOD_POLL_INTERVAL: Optional poll interval (default: 2.0)
            RUNPOD_ENABLE_FALLBACK: Optional fallback flag (default: true)

        Returns:
            CloudConfig populated from environment
        """
        timeout_str = os.getenv("RUNPOD_TIMEOUT", "1800")
        poll_str = os.getenv("RUNPOD_POLL_INTERVAL", "2.0")
        fallback_str = os.getenv("RUNPOD_ENABLE_FALLBACK", "true").lower()

        return cls(
            api_key=os.getenv("RUNPOD_API_KEY"),
            endpoint_id=os.getenv("RUNPOD_ENDPOINT_ID"),
            diarize_endpoint_id=os.getenv("RUNPOD_DIARIZE_ENDPOINT_ID"),
            r2_account_id=os.getenv("R2_ACCOUNT_ID"),
            r2_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
            r2_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
            r2_bucket_name=os.getenv("R2_BUCKET_NAME"),
            timeout_seconds=int(timeout_str),
            poll_interval_seconds=float(poll_str),
            enable_fallback=fallback_str in ("true", "1", "yes"),
        )

    @classmethod
    def from_podx_config(cls) -> "CloudConfig":
        """Create configuration from podx's config system.

        Loads from env vars -> env.sh -> config.yaml (podx's priority order).

        Returns:
            CloudConfig populated from podx config
        """
        from podx.cli.config import _get_value

        api_key = _get_value("runpod-api-key")
        endpoint_id = _get_value("runpod-endpoint-id")
        diarize_endpoint_id = _get_value("runpod-diarize-endpoint-id")
        r2_account_id = _get_value("r2-account-id")
        r2_access_key_id = _get_value("r2-access-key-id")
        r2_secret_access_key = _get_value("r2-secret-access-key")
        r2_bucket_name = _get_value("r2-bucket-name")

        # Fall back to env vars for timeout/poll/fallback (not in podx config)
        timeout_str = os.getenv("RUNPOD_TIMEOUT", "1800")
        poll_str = os.getenv("RUNPOD_POLL_INTERVAL", "2.0")
        fallback_str = os.getenv("RUNPOD_ENABLE_FALLBACK", "true").lower()

        return cls(
            api_key=api_key or None,
            endpoint_id=endpoint_id or None,
            diarize_endpoint_id=diarize_endpoint_id or None,
            r2_account_id=r2_account_id or None,
            r2_access_key_id=r2_access_key_id or None,
            r2_secret_access_key=r2_secret_access_key or None,
            r2_bucket_name=r2_bucket_name or None,
            timeout_seconds=int(timeout_str),
            poll_interval_seconds=float(poll_str),
            enable_fallback=fallback_str in ("true", "1", "yes"),
        )

    def validate(self) -> None:
        """Validate that configuration is complete for transcription.

        Raises:
            CloudError: If required configuration is missing
        """
        if not self.api_key:
            raise CloudError(
                "RunPod API key not set. Run 'podx cloud setup' to configure.",
                recoverable=False,
            )
        if not self.endpoint_id:
            raise CloudError(
                "RunPod endpoint ID not set. Run 'podx cloud setup' to configure.",
                recoverable=False,
            )
        if not self.r2_account_id or not self.r2_bucket_name:
            raise CloudError(
                "Cloudflare R2 not configured. Run 'podx cloud setup' to configure.",
                recoverable=False,
            )
        if not self.r2_access_key_id or not self.r2_secret_access_key:
            raise CloudError(
                "R2 API credentials not set. Run 'podx cloud setup' to configure.",
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
        """Check if cloud is fully configured for transcription (RunPod + R2)."""
        return bool(
            self.api_key
            and self.endpoint_id
            and self.r2_account_id
            and self.r2_access_key_id
            and self.r2_secret_access_key
            and self.r2_bucket_name
        )

    @property
    def is_r2_configured(self) -> bool:
        """Check if R2 storage is configured."""
        return bool(
            self.r2_account_id
            and self.r2_access_key_id
            and self.r2_secret_access_key
            and self.r2_bucket_name
        )

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
    def r2_endpoint_url(self) -> str:
        """Get the R2 S3-compatible endpoint URL."""
        return f"https://{self.r2_account_id}.r2.cloudflarestorage.com"

    @property
    def headers(self) -> dict[str, str]:
        """Get HTTP headers for RunPod API requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
