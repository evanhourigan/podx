# syntax=docker/dockerfile:1.4
# PodX Server - Production-Grade Podcast Processing API
# Multi-stage build for optimal image size and security

# ============================================================================
# Stage 1: Builder - Install dependencies and build wheels
# ============================================================================
FROM python:3.12-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy dependency files
COPY pyproject.toml /tmp/
WORKDIR /tmp

# Install Python dependencies
# Install server extras for the API server
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -e ".[server]"

# ============================================================================
# Stage 2: Runtime - Minimal production image
# ============================================================================
FROM python:3.12-slim AS runtime

# Install runtime system dependencies
# ffmpeg: Required for audio processing
# ca-certificates: For HTTPS requests
# tini: Proper init system for container signal handling
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    ca-certificates \
    tini \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r podx && useradd -r -g podx podx

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=podx:podx podx/ /app/podx/
COPY --chown=podx:podx pyproject.toml /app/

# Install the package in editable mode
RUN pip install --no-cache-dir -e .

# Create data directory for database and uploads
RUN mkdir -p /data && chown -R podx:podx /data

# Switch to non-root user
USER podx

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PODX_DB_PATH=/data/server.db \
    PODX_UPLOAD_DIR=/data/uploads \
    PODX_CORS_ORIGINS=* \
    PODX_CLEANUP_MAX_AGE_DAYS=7 \
    PODX_CLEANUP_INTERVAL_HOURS=24

# Expose port
EXPOSE 8000

# Health check using the liveness endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/live')"

# Use tini as init system for proper signal handling
ENTRYPOINT ["/usr/bin/tini", "--"]

# Start server with uvicorn
CMD ["uvicorn", "podx.server.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
