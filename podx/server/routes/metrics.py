"""Prometheus metrics endpoint for monitoring."""

import os

from fastapi import APIRouter, Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from sqlalchemy import select, func

from podx.server.database import async_session_factory
from podx.server.models.database import Job

router = APIRouter()

# Define metrics
http_requests_total = Counter(
    "podx_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

http_request_duration_seconds = Histogram(
    "podx_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
)

jobs_total = Counter(
    "podx_jobs_total",
    "Total number of jobs created",
    ["job_type"],
)

jobs_by_status = Gauge(
    "podx_jobs_by_status",
    "Number of jobs by status",
    ["status"],
)

active_workers = Gauge(
    "podx_active_workers",
    "Number of active background workers",
)


def is_metrics_enabled() -> bool:
    """Check if metrics endpoint is enabled via environment variable.

    Returns:
        True if PODX_METRICS_ENABLED is set to 'true' or '1'
    """
    enabled = os.getenv("PODX_METRICS_ENABLED", "false").lower()
    return enabled in ("true", "1", "yes")


async def update_job_metrics() -> None:
    """Update job-related metrics from database.

    This should be called periodically or on-demand to keep
    job metrics up to date.
    """
    async with async_session_factory() as session:
        # Get job counts by status
        stmt = select(Job.status, func.count(Job.id)).group_by(Job.status)
        result = await session.execute(stmt)
        status_counts = result.all()

        # Update gauges
        for status, count in status_counts:
            jobs_by_status.labels(status=status).set(count)


@router.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint.

    Returns metrics in Prometheus exposition format.
    This endpoint is only available if PODX_METRICS_ENABLED=true.

    Returns:
        Prometheus-formatted metrics
    """
    if not is_metrics_enabled():
        return Response(
            content="Metrics endpoint is disabled. Set PODX_METRICS_ENABLED=true to enable.",
            status_code=404,
        )

    # Update job metrics before returning
    await update_job_metrics()

    # Generate Prometheus metrics
    metrics_data = generate_latest()

    return Response(content=metrics_data, media_type=CONTENT_TYPE_LATEST)
