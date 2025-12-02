"""Cloud acceleration for PodX.

Provides RunPod serverless GPU support for transcription,
reducing processing time from 60-90 minutes to 2-4 minutes
for a 1-hour podcast.

Usage:
    podx cloud setup           # Configure RunPod credentials
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

__all__ = [
    "CloudConfig",
    "CloudError",
    "CloudAuthError",
    "CloudTimeoutError",
    "EndpointNotFoundError",
    "JobFailedError",
    "UploadError",
    "RunPodClient",
]
