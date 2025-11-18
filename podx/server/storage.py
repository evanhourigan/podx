"""File storage utilities for PodX server.

Handles uploading and storing audio files for processing.
"""

import os
import uuid
from pathlib import Path
from typing import BinaryIO

from podx.logging import get_logger

logger = get_logger(__name__)

# Default upload directory
DEFAULT_UPLOAD_DIR = Path.home() / ".podx" / "uploads"


def get_upload_dir() -> Path:
    """Get the upload directory path.

    Returns:
        Path to upload directory
    """
    upload_dir = os.environ.get("PODX_UPLOAD_DIR")
    if upload_dir:
        return Path(upload_dir)
    return DEFAULT_UPLOAD_DIR


def ensure_upload_dir() -> Path:
    """Ensure upload directory exists.

    Returns:
        Path to upload directory
    """
    upload_dir = get_upload_dir()
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def save_upload_file(file: BinaryIO, filename: str) -> str:
    """Save an uploaded file to disk.

    Args:
        file: File object to save
        filename: Original filename

    Returns:
        Path to saved file (absolute path as string)
    """
    # Ensure upload directory exists
    upload_dir = ensure_upload_dir()

    # Generate unique filename to avoid collisions
    file_ext = Path(filename).suffix
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = upload_dir / unique_filename

    # Save file
    logger.info(f"Saving uploaded file to {file_path}")
    with open(file_path, "wb") as f:
        content = file.read()
        f.write(content)

    logger.info(f"Saved {len(content)} bytes to {file_path}")
    return str(file_path)


def delete_upload_file(file_path: str) -> None:
    """Delete an uploaded file.

    Args:
        file_path: Path to file to delete
    """
    try:
        path = Path(file_path)
        if path.exists():
            path.unlink()
            logger.info(f"Deleted upload file: {file_path}")
    except Exception as e:
        logger.warning(f"Failed to delete upload file {file_path}: {e}")
