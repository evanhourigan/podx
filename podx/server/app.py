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

    # CORS middleware - allow all origins for now (can restrict later)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    from podx.server.routes import health, jobs, processing, upload

    app.include_router(health.router, tags=["Health"])
    app.include_router(jobs.router, tags=["Jobs"])
    app.include_router(processing.router, tags=["Processing"])
    app.include_router(upload.router, tags=["Upload"])

    return app


# Application instance
app = create_app()
