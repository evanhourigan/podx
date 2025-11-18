"""Custom exceptions for PodX Web API Server.

This module defines custom exception types and FastAPI exception handlers.
"""

from typing import Any, Dict

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse

from podx.logging import get_logger

logger = get_logger(__name__)


class PodXAPIException(Exception):
    """Base exception for all PodX API errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: Dict[str, Any] | None = None,
    ):
        """Initialize exception.

        Args:
            message: Error message
            status_code: HTTP status code
            details: Additional error details
        """
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class JobNotFoundException(PodXAPIException):
    """Raised when a job is not found."""

    def __init__(self, job_id: str):
        """Initialize exception.

        Args:
            job_id: The job ID that was not found
        """
        super().__init__(
            message=f"Job {job_id} not found",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"job_id": job_id},
        )


class InvalidInputException(PodXAPIException):
    """Raised when input validation fails."""

    def __init__(self, message: str, field: str | None = None):
        """Initialize exception.

        Args:
            message: Error message
            field: Field name that failed validation
        """
        details = {"field": field} if field else {}
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class FileUploadException(PodXAPIException):
    """Raised when file upload fails."""

    def __init__(self, message: str, filename: str | None = None):
        """Initialize exception.

        Args:
            message: Error message
            filename: The file that failed to upload
        """
        details = {"filename": filename} if filename else {}
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class JobProcessingException(PodXAPIException):
    """Raised when job processing fails."""

    def __init__(self, message: str, job_id: str | None = None):
        """Initialize exception.

        Args:
            message: Error message
            job_id: The job ID that failed
        """
        details = {"job_id": job_id} if job_id else {}
        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


# Exception handlers for FastAPI


async def podx_exception_handler(
    request: Request, exc: PodXAPIException
) -> JSONResponse:
    """Handle PodX custom exceptions.

    Args:
        request: FastAPI request
        exc: The exception that was raised

    Returns:
        JSON error response
    """
    from podx.server.middleware.request_id import get_request_id

    request_id = get_request_id(request)

    logger.error(
        f"{exc.status_code} {request.method} {request.url.path}: {exc.message}",
        extra={"details": exc.details, "request_id": request_id},
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.message,
            "status_code": exc.status_code,
            "details": exc.details,
            "request_id": request_id,
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI HTTP exceptions.

    Args:
        request: FastAPI request
        exc: The exception that was raised

    Returns:
        JSON error response
    """
    from podx.server.middleware.request_id import get_request_id

    request_id = get_request_id(request)

    logger.error(
        f"{exc.status_code} {request.method} {request.url.path}: {exc.detail}",
        extra={"request_id": request_id},
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": str(exc.detail),
            "status_code": exc.status_code,
            "request_id": request_id,
        },
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions.

    Args:
        request: FastAPI request
        exc: The exception that was raised

    Returns:
        JSON error response
    """
    from podx.server.middleware.request_id import get_request_id

    request_id = get_request_id(request)

    logger.error(
        f"500 {request.method} {request.url.path}: Unexpected error: {exc}",
        exc_info=True,
        extra={"request_id": request_id},
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "message": "An unexpected error occurred. Please contact support if the problem persists.",
            "request_id": request_id,
        },
    )
