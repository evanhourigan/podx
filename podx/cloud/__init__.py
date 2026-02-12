"""Cloud acceleration for PodX.

Provides RunPod serverless GPU support for transcription,
with Cloudflare R2 storage for audio uploads.

Usage:
    podx cloud setup           # Configure RunPod + R2 credentials
    podx transcribe --model runpod:large-v3-turbo ./episode/
"""

from .config import CloudConfig
from .exceptions import (
    CloudAuthError,
    CloudError,
    CloudTimeoutError,
    EndpointNotFoundError,
    JobFailedError,
    UploadError,
)
from .runpod_client import RunPodClient
from .storage import CloudStorage

__all__ = [
    "CloudConfig",
    "CloudError",
    "CloudAuthError",
    "CloudTimeoutError",
    "EndpointNotFoundError",
    "JobFailedError",
    "UploadError",
    "RunPodClient",
    "CloudStorage",
]
