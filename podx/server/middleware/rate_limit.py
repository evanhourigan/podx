"""Rate limiting middleware for PodX API Server.

Provides configurable rate limiting using slowapi to prevent abuse.
"""

import os

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import JSONResponse

from podx.logging import get_logger

logger = get_logger(__name__)


def get_rate_limit_config() -> tuple[str, str]:
    """Get rate limit configuration from environment.

    Returns:
        Tuple of (general_limit, upload_limit) as strings
        Example: ("100/minute", "10/hour")
    """
    general_limit = os.getenv("PODX_RATE_LIMIT_PER_MINUTE", "100/minute")
    upload_limit = os.getenv("PODX_UPLOAD_LIMIT_PER_HOUR", "10/hour")

    logger.info(f"Rate limiting configured: {general_limit} general, {upload_limit} uploads")
    return general_limit, upload_limit


def create_limiter() -> Limiter:
    """Create and configure the rate limiter.

    Returns:
        Configured Limiter instance
    """
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[],  # No default limits, we'll apply per-route
        storage_uri="memory://",  # In-memory storage (use Redis for production cluster)
    )

    logger.info("Rate limiter created with in-memory storage")
    return limiter


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Handle rate limit exceeded errors.

    Args:
        request: The request that exceeded the rate limit
        exc: The rate limit exception

    Returns:
        JSON response with 429 status code
    """
    logger.warning(
        f"Rate limit exceeded for {get_remote_address(request)} on {request.url.path}"
    )

    return JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "status_code": 429,
            "details": {
                "message": str(exc),
                "retry_after": getattr(exc, "retry_after", None),
            },
        },
        headers={"Retry-After": str(getattr(exc, "retry_after", 60))},
    )


# Global limiter instance
limiter = create_limiter()
