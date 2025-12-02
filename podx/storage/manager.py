"""Cloud storage manager with S3, GCS, and Azure support."""

from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from podx.logging import get_logger

logger = get_logger(__name__)


class StorageBackend(str, Enum):
    """Supported cloud storage backends."""

    S3 = "s3"
    GCS = "gcs"
    AZURE = "azure"
    LOCAL = "local"


class StorageError(Exception):
    """Raised when storage operations fail."""

    pass


class StorageManager:
    """Unified cloud storage manager.

    Supports S3, Google Cloud Storage, and Azure Blob Storage.
    Automatically detects backend from URL scheme.
    """

    def __init__(
        self,
        backend: Optional[StorageBackend] = None,
        bucket: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize storage manager.

        Args:
            backend: Storage backend (auto-detected from URL if not specified)
            bucket: Bucket/container name
            **kwargs: Backend-specific configuration
        """
        self.backend = backend
        self.bucket = bucket
        self.config = kwargs
        self._client = None

    def _get_s3_client(self) -> Any:
        """Get boto3 S3 client."""
        try:
            import boto3

            return boto3.client(
                "s3",
                aws_access_key_id=self.config.get("aws_access_key_id"),
                aws_secret_access_key=self.config.get("aws_secret_access_key"),
                region_name=self.config.get("region", "us-east-1"),
            )
        except ImportError:
            raise StorageError("boto3 not installed. Install with: pip install boto3")

    def _get_gcs_client(self) -> Any:
        """Get GCS client."""
        try:
            from google.cloud import storage

            credentials_path = self.config.get("credentials_path")
            if credentials_path:
                return storage.Client.from_service_account_json(credentials_path)
            return storage.Client()
        except ImportError:
            raise StorageError(
                "google-cloud-storage not installed. "
                "Install with: pip install google-cloud-storage"
            )

    def _get_azure_client(self) -> Any:
        """Get Azure Blob Storage client."""
        try:
            from azure.storage.blob import BlobServiceClient

            connection_string = self.config.get("connection_string")
            if connection_string:
                return BlobServiceClient.from_connection_string(connection_string)

            account_url = self.config.get(
                "account_url",
                f"https://{self.config.get('account_name')}.blob.core.windows.net",
            )
            credential = self.config.get("credential")
            return BlobServiceClient(account_url=account_url, credential=credential)
        except ImportError:
            raise StorageError(
                "azure-storage-blob not installed. "
                "Install with: pip install azure-storage-blob"
            )

    def _detect_backend_from_url(self, url: str) -> StorageBackend:
        """Detect storage backend from URL scheme.

        Args:
            url: Storage URL (s3://, gs://, or https://...)

        Returns:
            Detected StorageBackend
        """
        parsed = urlparse(url)

        if parsed.scheme == "s3":
            return StorageBackend.S3
        elif parsed.scheme == "gs":
            return StorageBackend.GCS
        elif "blob.core.windows.net" in parsed.netloc:
            return StorageBackend.AZURE
        else:
            return StorageBackend.LOCAL

    def upload(
        self,
        local_path: Path,
        remote_path: str,
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """Upload file to cloud storage.

        Args:
            local_path: Local file path
            remote_path: Remote object key/path
            metadata: Optional metadata dict

        Returns:
            URL of uploaded file

        Raises:
            StorageError: If upload fails
        """
        if not local_path.exists():
            raise StorageError(f"Local file not found: {local_path}")

        # Auto-detect backend if not set
        if self.backend is None:
            self.backend = self._detect_backend_from_url(remote_path)

        try:
            if self.backend == StorageBackend.S3:
                return self._upload_s3(local_path, remote_path, metadata)
            elif self.backend == StorageBackend.GCS:
                return self._upload_gcs(local_path, remote_path, metadata)
            elif self.backend == StorageBackend.AZURE:
                return self._upload_azure(local_path, remote_path, metadata)
            else:
                raise StorageError(f"Unsupported backend: {self.backend}")

        except Exception as e:
            logger.error("Upload failed", error=str(e), backend=self.backend.value)
            raise StorageError(f"Upload failed: {e}") from e

    def _upload_s3(
        self, local_path: Path, remote_path: str, metadata: Optional[Dict[str, str]]
    ) -> str:
        """Upload to S3."""
        client = self._get_s3_client()

        extra_args = {}
        if metadata:
            extra_args["Metadata"] = metadata

        client.upload_file(
            str(local_path),
            self.bucket,
            remote_path,
            ExtraArgs=extra_args if extra_args else None,
        )

        url = f"s3://{self.bucket}/{remote_path}"
        logger.info("Uploaded to S3", url=url, size=local_path.stat().st_size)
        return url

    def _upload_gcs(
        self, local_path: Path, remote_path: str, metadata: Optional[Dict[str, str]]
    ) -> str:
        """Upload to GCS."""
        client = self._get_gcs_client()
        bucket = client.bucket(self.bucket)
        blob = bucket.blob(remote_path)

        if metadata:
            blob.metadata = metadata

        blob.upload_from_filename(str(local_path))

        url = f"gs://{self.bucket}/{remote_path}"
        logger.info("Uploaded to GCS", url=url, size=local_path.stat().st_size)
        return url

    def _upload_azure(
        self, local_path: Path, remote_path: str, metadata: Optional[Dict[str, str]]
    ) -> str:
        """Upload to Azure Blob Storage."""
        client = self._get_azure_client()
        blob_client = client.get_blob_client(container=self.bucket, blob=remote_path)

        with open(local_path, "rb") as data:
            blob_client.upload_blob(data, metadata=metadata, overwrite=True)

        url = blob_client.url
        logger.info("Uploaded to Azure", url=url, size=local_path.stat().st_size)
        return url

    def download(self, remote_path: str, local_path: Path) -> Path:
        """Download file from cloud storage.

        Args:
            remote_path: Remote object key/path or full URL
            local_path: Local destination path

        Returns:
            Path to downloaded file

        Raises:
            StorageError: If download fails
        """
        # Auto-detect backend from URL
        if self.backend is None:
            self.backend = self._detect_backend_from_url(remote_path)

        # Create parent directory
        local_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if self.backend == StorageBackend.S3:
                return self._download_s3(remote_path, local_path)
            elif self.backend == StorageBackend.GCS:
                return self._download_gcs(remote_path, local_path)
            elif self.backend == StorageBackend.AZURE:
                return self._download_azure(remote_path, local_path)
            else:
                raise StorageError(f"Unsupported backend: {self.backend}")

        except Exception as e:
            logger.error("Download failed", error=str(e), backend=self.backend.value)
            raise StorageError(f"Download failed: {e}") from e

    def _download_s3(self, remote_path: str, local_path: Path) -> Path:
        """Download from S3."""
        client = self._get_s3_client()

        # Extract bucket and key from s3:// URL if needed
        if remote_path.startswith("s3://"):
            parsed = urlparse(remote_path)
            bucket: str = parsed.netloc
            key = parsed.path.lstrip("/")
        else:
            bucket = self.bucket or ""
            key = remote_path

        client.download_file(bucket, key, str(local_path))

        logger.info("Downloaded from S3", path=str(local_path))
        return local_path

    def _download_gcs(self, remote_path: str, local_path: Path) -> Path:
        """Download from GCS."""
        client = self._get_gcs_client()

        # Extract bucket and blob from gs:// URL if needed
        if remote_path.startswith("gs://"):
            parsed = urlparse(remote_path)
            bucket_name: str = parsed.netloc
            blob_name = parsed.path.lstrip("/")
        else:
            bucket_name = self.bucket or ""
            blob_name = remote_path

        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.download_to_filename(str(local_path))

        logger.info("Downloaded from GCS", path=str(local_path))
        return local_path

    def _download_azure(self, remote_path: str, local_path: Path) -> Path:
        """Download from Azure Blob Storage."""
        client = self._get_azure_client()

        # Extract container and blob from URL if needed
        if "blob.core.windows.net" in remote_path:
            parsed = urlparse(remote_path)
            parts = parsed.path.lstrip("/").split("/", 1)
            container: str = parts[0]
            blob_name = parts[1] if len(parts) > 1 else ""
        else:
            container = self.bucket or ""
            blob_name = remote_path

        blob_client = client.get_blob_client(container=container, blob=blob_name)

        with open(local_path, "wb") as f:
            download_stream = blob_client.download_blob()
            f.write(download_stream.readall())

        logger.info("Downloaded from Azure", path=str(local_path))
        return local_path

    def exists(self, remote_path: str) -> bool:
        """Check if object exists in cloud storage.

        Args:
            remote_path: Remote object key/path

        Returns:
            True if object exists, False otherwise
        """
        # Auto-detect backend
        if self.backend is None:
            self.backend = self._detect_backend_from_url(remote_path)

        try:
            if self.backend == StorageBackend.S3:
                client = self._get_s3_client()
                client.head_object(Bucket=self.bucket, Key=remote_path)
                return True
            elif self.backend == StorageBackend.GCS:
                client = self._get_gcs_client()
                bucket = client.bucket(self.bucket)
                blob = bucket.blob(remote_path)
                return blob.exists()
            elif self.backend == StorageBackend.AZURE:
                client = self._get_azure_client()
                blob_client = client.get_blob_client(
                    container=self.bucket, blob=remote_path
                )
                return blob_client.exists()
            else:
                return False

        except Exception:
            return False
