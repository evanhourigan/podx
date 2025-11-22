"""Tests for cloud storage integration - simplified."""

import tempfile
from pathlib import Path

import pytest

from podx.storage import StorageBackend, StorageError, StorageManager


class TestStorageManager:
    """Test StorageManager."""

    @pytest.fixture
    def temp_file(self):
        """Create temporary file for testing."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test content")
            temp_path = Path(f.name)

        yield temp_path

        # Cleanup
        if temp_path.exists():
            temp_path.unlink()

    def test_detect_backend_from_url(self):
        """Test backend detection from URLs."""
        manager = StorageManager()

        assert manager._detect_backend_from_url("s3://bucket/key") == StorageBackend.S3
        assert manager._detect_backend_from_url("gs://bucket/key") == StorageBackend.GCS
        assert (
            manager._detect_backend_from_url(
                "https://account.blob.core.windows.net/container/blob"
            )
            == StorageBackend.AZURE
        )
        assert manager._detect_backend_from_url("/local/path") == StorageBackend.LOCAL

    def test_upload_nonexistent_file(self):
        """Test upload with nonexistent file."""
        manager = StorageManager(backend=StorageBackend.S3, bucket="test-bucket")

        with pytest.raises(StorageError) as exc:
            manager.upload(Path("/nonexistent/file.txt"), "test/file.txt")

        assert "not found" in str(exc.value).lower()

    def test_initialization(self):
        """Test manager initialization."""
        manager = StorageManager(
            backend=StorageBackend.S3,
            bucket="my-bucket",
            region="us-west-2",
        )

        assert manager.backend == StorageBackend.S3
        assert manager.bucket == "my-bucket"
        assert manager.config["region"] == "us-west-2"

    def test_backend_enum_values(self):
        """Test StorageBackend enum values."""
        assert StorageBackend.S3.value == "s3"
        assert StorageBackend.GCS.value == "gcs"
        assert StorageBackend.AZURE.value == "azure"
        assert StorageBackend.LOCAL.value == "local"

    def test_missing_s3_dependency(self):
        """Test error handling when boto3 not installed."""
        manager = StorageManager(backend=StorageBackend.S3)

        # Should raise StorageError mentioning boto3 when trying to get client
        # (only if boto3 is not actually installed)
        try:
            import boto3  # noqa: F401

            # boto3 is installed, skip this test
            pytest.skip("boto3 is installed")
        except ImportError:
            with pytest.raises(StorageError) as exc:
                manager._get_s3_client()
            assert "boto3" in str(exc.value)

    def test_missing_gcs_dependency(self):
        """Test error handling when GCS library not installed."""
        manager = StorageManager(backend=StorageBackend.GCS)

        try:
            from google.cloud import storage  # noqa: F401

            pytest.skip("google-cloud-storage is installed")
        except ImportError:
            with pytest.raises(StorageError) as exc:
                manager._get_gcs_client()
            assert "google-cloud-storage" in str(exc.value)

    def test_missing_azure_dependency(self):
        """Test error handling when Azure library not installed."""
        manager = StorageManager(backend=StorageBackend.AZURE)

        try:
            from azure.storage.blob import BlobServiceClient  # noqa: F401

            pytest.skip("azure-storage-blob is installed")
        except ImportError:
            with pytest.raises(StorageError) as exc:
                manager._get_azure_client()
            assert "azure-storage-blob" in str(exc.value)
