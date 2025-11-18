"""FastAPI application for PodX Web API Server.

This module provides the main FastAPI application instance with:
- Health check endpoints
- Request/response logging
- Error handling
- OpenAPI documentation
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from podx.logging import get_logger
from podx.server.exceptions import (
    PodXAPIException,
    general_exception_handler,
    http_exception_handler,
    podx_exception_handler,
)

logger = get_logger(__name__)

# Global worker instance (started in lifespan)
_worker = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Handles startup and shutdown events for the FastAPI application.

    Args:
        app: FastAPI application instance

    Yields:
        None during application runtime
    """
    # Startup
    logger.info("Starting PodX API Server...")

    # Initialize database
    from podx.server.database import init_db

    logger.info("Initializing database...")
    await init_db()
    logger.info("Database initialized")

    # Start background worker
    from podx.server.services import BackgroundWorker

    global _worker
    _worker = BackgroundWorker()
    await _worker.start()
    logger.info("Background worker started")

    logger.info("Server ready to accept requests")

    yield

    # Shutdown
    logger.info("Shutting down PodX API Server...")
    if _worker:
        await _worker.stop()
        logger.info("Background worker stopped")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    app = FastAPI(
        title="PodX API",
        description="Production-grade podcast processing API with real-time progress tracking",
        version="3.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS middleware - configurable via PODX_CORS_ORIGINS env var
    # Format: comma-separated origins, e.g., "http://localhost:3000,https://app.example.com"
    # Default: "*" (allow all origins for development)
    cors_origins_str = os.getenv("PODX_CORS_ORIGINS", "*")
    cors_origins = (
        [origin.strip() for origin in cors_origins_str.split(",")]
        if cors_origins_str != "*"
        else ["*"]
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    logger.info(f"CORS configured with origins: {cors_origins}")

    # Request logging middleware
    from podx.server.middleware.request_logging import RequestLoggingMiddleware

    app.add_middleware(RequestLoggingMiddleware)

    # Add authentication middleware (optional - enabled via PODX_API_KEY env var)
    from podx.server.middleware.auth import APIKeyAuthMiddleware

    app.add_middleware(APIKeyAuthMiddleware)

    # Register exception handlers
    app.add_exception_handler(PodXAPIException, podx_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    # Rate limiting exception handler
    from podx.server.middleware.rate_limit import limiter, rate_limit_exceeded_handler

    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    # Add limiter to app state for slowapi
    app.state.limiter = limiter

    # Register routes
    from podx.server.routes import health, jobs, processing, streaming, upload

    app.include_router(health.router, tags=["Health"])
    app.include_router(jobs.router, tags=["Jobs"])
    app.include_router(processing.router, tags=["Processing"])
    app.include_router(streaming.router, tags=["Streaming"])
    app.include_router(upload.router, tags=["Upload"])

    return app


# Application instance
app = create_app()
