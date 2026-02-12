"""Cloudflare R2 storage for cloud audio uploads.

Uploads audio files to R2 and generates presigned URLs
for RunPod workers to download.
"""

import uuid
from pathlib import Path
from typing import Tuple

from ..logging import get_logger
from .config import CloudConfig
from .exceptions import UploadError

logger = get_logger(__name__)


class CloudStorage:
    """Upload audio to Cloudflare R2 and generate presigned URLs.

    Uses boto3's S3-compatible client to interact with R2.
    Files are uploaded with a unique key and a presigned GET URL
    is generated for the RunPod worker to download.
    """

    def __init__(self, config: CloudConfig):
        self.config = config
        self._client = None

    @property
    def client(self):
        """Get or create boto3 S3 client for R2."""
        if self._client is None:
            try:
                import boto3
                from botocore.config import Config as BotoConfig
            except ImportError:
                raise UploadError("boto3 not installed. Install with: pip install boto3")

            self._client = boto3.client(
                "s3",
                endpoint_url=self.config.r2_endpoint_url,
                aws_access_key_id=self.config.r2_access_key_id,
                aws_secret_access_key=self.config.r2_secret_access_key,
                region_name="auto",
                config=BotoConfig(signature_version="s3v4"),
            )
        return self._client

    def upload_and_presign(
        self,
        audio_path: Path,
        expires_in: int = 3600,
    ) -> Tuple[str, str]:
        """Upload audio file to R2 and return a presigned GET URL.

        Args:
            audio_path: Path to audio file to upload
            expires_in: URL expiration time in seconds (default: 1 hour)

        Returns:
            Tuple of (presigned_url, object_key) for download and cleanup

        Raises:
            UploadError: If upload fails
        """
        if not audio_path.exists():
            raise UploadError(f"Audio file not found: {audio_path}")

        key = f"podx/{uuid.uuid4().hex}/{audio_path.name}"
        bucket = self.config.r2_bucket_name
        file_size_mb = audio_path.stat().st_size / (1024 * 1024)

        logger.info(
            "Uploading to R2",
            bucket=bucket,
            key=key,
            size_mb=round(file_size_mb, 2),
        )

        try:
            self.client.upload_file(str(audio_path), bucket, key)
        except Exception as e:
            raise UploadError(f"R2 upload failed: {e}", cause=e)

        try:
            url = self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=expires_in,
            )
        except Exception as e:
            # Clean up the uploaded file if presign fails
            self._try_delete(bucket, key)
            raise UploadError(f"Failed to generate presigned URL: {e}", cause=e)

        logger.info("Upload complete, presigned URL generated", expires_in=expires_in)
        return url, key

    def delete(self, key: str) -> None:
        """Delete an uploaded file from R2.

        Args:
            key: Object key returned from upload_and_presign
        """
        self._try_delete(self.config.r2_bucket_name, key)

    def _try_delete(self, bucket: str, key: str) -> None:
        """Attempt to delete an object, logging but not raising on failure."""
        try:
            self.client.delete_object(Bucket=bucket, Key=key)
            logger.debug("Deleted R2 object", bucket=bucket, key=key)
        except Exception as e:
            logger.warning("Failed to delete R2 object", bucket=bucket, key=key, error=str(e))

    def test_connection(self) -> bool:
        """Test that R2 bucket is accessible.

        Returns:
            True if bucket can be accessed, False otherwise
        """
        try:
            self.client.head_bucket(Bucket=self.config.r2_bucket_name)
            return True
        except Exception as e:
            logger.debug("R2 connection test failed", error=str(e))
            return False
