"""File upload endpoints for PodX API."""

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from podx.logging import get_logger
from podx.server.storage import save_upload_file

logger = get_logger(__name__)

router = APIRouter()


class UploadResponse(BaseModel):
    """Response for file upload."""

    file_path: str = Field(..., description="Path to uploaded file")
    filename: str = Field(..., description="Original filename")
    size: int = Field(..., description="File size in bytes")


@router.post("/api/v1/upload", response_model=UploadResponse, status_code=201)
async def upload_file(file: UploadFile = File(...)) -> UploadResponse:
    """Upload an audio file for processing.

    Args:
        file: Audio file to upload

    Returns:
        File upload information

    Raises:
        HTTPException: If upload fails
    """
    try:
        # Validate file type (optional - can add stricter validation)
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        # Save file
        file_path = save_upload_file(file.file, file.filename)

        # Get file size
        file.file.seek(0, 2)  # Seek to end
        size = file.file.tell()

        logger.info(f"Uploaded file: {file.filename} -> {file_path} ({size} bytes)")

        return UploadResponse(
            file_path=file_path,
            filename=file.filename,
            size=size,
        )

    except Exception as e:
        logger.error(f"Upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
