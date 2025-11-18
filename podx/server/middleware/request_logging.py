"""Request logging middleware for PodX API Server.

Logs all HTTP requests with method, path, status code, duration, and client IP.
"""

import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from podx.logging import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging all HTTP requests.

    Logs:
    - HTTP method
    - Request path
    - Status code
    - Response time (ms)
    - Client IP address
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log details.

        Args:
            request: Incoming request
            call_next: Next middleware/route handler

        Returns:
            Response from next handler
        """
        # Start timer
        start_time = time.time()

        # Get client IP
        client_ip = request.client.host if request.client else "unknown"

        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            # Log exception and re-raise
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"{request.method} {request.url.path} - ERROR - "
                f"{duration_ms:.2f}ms - {client_ip} - {str(e)}"
            )
            raise

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Log request
        log_message = (
            f"{request.method} {request.url.path} - "
            f"{status_code} - "
            f"{duration_ms:.2f}ms - "
            f"{client_ip}"
        )

        # Use different log levels based on status code
        if status_code >= 500:
            logger.error(log_message)
        elif status_code >= 400:
            logger.warning(log_message)
        else:
            logger.info(log_message)

        return response
