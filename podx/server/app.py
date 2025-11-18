"""FastAPI application for PodX Web API Server.

This module provides the main FastAPI application instance with:
- Health check endpoints
- Request/response logging
- Error handling
- OpenAPI documentation
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from podx.logging import get_logger

logger = get_logger(__name__)


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
    logger.info("Server ready to accept requests")

    yield

    # Shutdown
    logger.info("Shutting down PodX API Server...")


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

    # CORS middleware - allow all origins for now (can restrict later)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    from podx.server.routes import health
    app.include_router(health.router, tags=["Health"])

    return app


# Application instance
app = create_app()
