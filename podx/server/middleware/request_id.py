"""Request ID middleware for PodX API Server.

Adds a unique request ID to every request for distributed tracing and debugging.
The request ID is included in response headers and can be referenced in logs and error messages.
"""

import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from podx.logging import get_logger

logger = get_logger(__name__)

# Header name for request ID
REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware for adding unique request IDs to all requests.

    Request IDs are:
    - Generated as UUIDs for new requests
    - Preserved from X-Request-ID header if provided by client
    - Added to response headers
    - Available for logging and error tracking
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and add request ID.

        Args:
            request: Incoming request
            call_next: Next middleware/route handler

        Returns:
            Response with X-Request-ID header
        """
        # Get request ID from header or generate new one
        request_id = request.headers.get(REQUEST_ID_HEADER)
        if not request_id:
            request_id = str(uuid.uuid4())

        # Store request ID in request state for access in routes
        request.state.request_id = request_id

        # Process request
        response = await call_next(request)

        # Add request ID to response headers
        response.headers[REQUEST_ID_HEADER] = request_id

        return response


def get_request_id(request: Request) -> str:
    """Get the request ID from a request.

    Args:
        request: FastAPI request object

    Returns:
        Request ID string
    """
    return getattr(request.state, "request_id", "unknown")
