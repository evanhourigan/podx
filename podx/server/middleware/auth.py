"""Authentication middleware for PodX API Server.

Provides optional API key authentication via X-API-Key header.
Authentication is only enabled if PODX_API_KEY environment variable is set.
"""

import os
from typing import Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from podx.logging import get_logger

logger = get_logger(__name__)


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Middleware for API key authentication.

    Only enabled if PODX_API_KEY environment variable is set.
    Validates X-API-Key header on all /api/* endpoints.
    Excludes /health, /docs, /redoc, /openapi.json from authentication.
    """

    def __init__(self, app, api_key: Optional[str] = None):
        """Initialize auth middleware.

        Args:
            app: FastAPI application
            api_key: Optional API key (defaults to PODX_API_KEY env var)
        """
        super().__init__(app)
        self.api_key = api_key or os.getenv("PODX_API_KEY")
        self.enabled = bool(self.api_key)

        if self.enabled:
            logger.info("API key authentication enabled")
        else:
            logger.info("API key authentication disabled (PODX_API_KEY not set)")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and validate API key if enabled.

        Args:
            request: Incoming request
            call_next: Next middleware/route handler

        Returns:
            Response from next handler or 401/403 error
        """
        # Skip auth if disabled
        if not self.enabled:
            return await call_next(request)

        # Skip auth for public endpoints
        if self._is_public_endpoint(request.url.path):
            return await call_next(request)

        # Validate API key
        provided_key = request.headers.get("X-API-Key")

        if not provided_key:
            logger.warning(f"Missing API key for {request.method} {request.url.path}")
            return JSONResponse(
                status_code=401,
                content={
                    "error": "Authentication required",
                    "status_code": 401,
                    "details": {"message": "X-API-Key header is required"},
                },
            )

        if provided_key != self.api_key:
            logger.warning(f"Invalid API key for {request.method} {request.url.path}")
            return JSONResponse(
                status_code=403,
                content={
                    "error": "Invalid API key",
                    "status_code": 403,
                    "details": {"message": "The provided API key is not valid"},
                },
            )

        # API key valid, proceed
        return await call_next(request)

    def _is_public_endpoint(self, path: str) -> bool:
        """Check if an endpoint is public (no auth required).

        Args:
            path: Request path

        Returns:
            True if endpoint is public, False otherwise
        """
        public_paths = [
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
        ]

        # Exact match
        if path in public_paths:
            return True

        # Check for OpenAPI paths
        if path.startswith("/docs") or path.startswith("/redoc"):
            return True

        return False


def get_api_key() -> Optional[str]:
    """Get configured API key from environment.

    Returns:
        API key string or None if not configured
    """
    return os.getenv("PODX_API_KEY")


def is_auth_enabled() -> bool:
    """Check if authentication is enabled.

    Returns:
        True if PODX_API_KEY is set, False otherwise
    """
    return bool(get_api_key())
