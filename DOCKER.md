# Docker Deployment Guide

Production-grade Docker deployment for the PodX API Server.

## Quick Start

### Using Docker Compose (Recommended)

```bash
# Start the server
docker-compose up -d

# View logs
docker-compose logs -f podx-server

# Stop the server
docker-compose down
```

The server will be available at `http://localhost:8000`

### Using Docker CLI

```bash
# Build the image
docker build -t podx-server:latest .

# Run the container
docker run -d \
  --name podx-server \
  -p 8000:8000 \
  -v podx-data:/data \
  podx-server:latest

# View logs
docker logs -f podx-server

# Stop the container
docker stop podx-server
docker rm podx-server
```

## Configuration

### Environment Variables

Configure the server using environment variables in `docker-compose.yml`:

```yaml
environment:
  # Database and Storage
  - PODX_DB_PATH=/data/server.db
  - PODX_UPLOAD_DIR=/data/uploads

  # CORS Configuration
  - PODX_CORS_ORIGINS=*  # Set to specific domains in production

  # API Authentication (optional)
  - PODX_API_KEY=your-secret-api-key-here

  # Cleanup Configuration
  - PODX_CLEANUP_MAX_AGE_DAYS=7
  - PODX_CLEANUP_INTERVAL_HOURS=24

  # Metrics (optional)
  - PODX_METRICS_ENABLED=true
```

### Volume Mounts

Data is persisted in the `podx-data` volume which contains:
- SQLite database (`/data/server.db`)
- Uploaded audio files (`/data/uploads/`)

To backup your data:
```bash
docker run --rm -v podx-data:/data -v $(pwd):/backup alpine tar czf /backup/podx-backup.tar.gz /data
```

To restore from backup:
```bash
docker run --rm -v podx-data:/data -v $(pwd):/backup alpine tar xzf /backup/podx-backup.tar.gz -C /
```

## Health Checks

The container includes built-in health checks:

- **Liveness probe**: `GET /health/live` (checks if server is running)
- **Readiness probe**: `GET /health/ready` (checks database connectivity)
- **Detailed health**: `GET /health` (comprehensive diagnostics)

Docker health check runs every 30 seconds:
```bash
# Check container health status
docker inspect --format='{{.State.Health.Status}}' podx-server
```

## Production Deployment

### Security Hardening

1. **Set API Key Authentication**:
   ```yaml
   environment:
     - PODX_API_KEY=use-a-strong-random-key-here
   ```

2. **Restrict CORS Origins**:
   ```yaml
   environment:
     - PODX_CORS_ORIGINS=https://your-app.com,https://admin.your-app.com
   ```

3. **Use Docker Secrets** (for Docker Swarm):
   ```yaml
   secrets:
     - podx_api_key

   services:
     podx-server:
       environment:
         - PODX_API_KEY_FILE=/run/secrets/podx_api_key
       secrets:
         - podx_api_key
   ```

### Resource Limits

The `docker-compose.yml` includes default resource limits:

```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 2G
    reservations:
      cpus: '0.5'
      memory: 512M
```

Adjust based on your workload:
- **Light workload**: 1 CPU, 1GB RAM
- **Medium workload**: 2 CPUs, 2GB RAM
- **Heavy workload**: 4+ CPUs, 4GB+ RAM

### Logging

Logs are configured with rotation:

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

View logs:
```bash
docker-compose logs -f --tail=100 podx-server
```

### Monitoring with Prometheus

Enable the metrics endpoint:

```yaml
environment:
  - PODX_METRICS_ENABLED=true
```

Metrics available at `http://localhost:8000/metrics`:
- `podx_http_requests_total` - Total HTTP requests by method/endpoint/status
- `podx_http_request_duration_seconds` - Request duration histogram
- `podx_jobs_total` - Total jobs created by type
- `podx_jobs_by_status` - Current job count by status
- `podx_active_workers` - Number of active background workers

Example Prometheus configuration:
```yaml
scrape_configs:
  - job_name: 'podx'
    static_configs:
      - targets: ['podx-server:8000']
    metrics_path: /metrics
    scrape_interval: 30s
```

## Troubleshooting

### Container won't start

Check logs:
```bash
docker-compose logs podx-server
```

Common issues:
- Port 8000 already in use: Change port mapping in `docker-compose.yml`
- Permission issues: Ensure volume has correct permissions

### Database locked errors

If you see "database is locked" errors:
1. Check that only one container instance is running
2. Ensure the database volume is not mounted in multiple containers
3. Verify no processes are holding locks on the database file

### Health check failing

```bash
# Check health status
docker inspect --format='{{.State.Health}}' podx-server

# Manually test health endpoint
docker exec podx-server curl http://localhost:8000/health/live
```

## Advanced Usage

### Multi-stage Development

Use different configurations for development vs production:

```yaml
# docker-compose.dev.yml
services:
  podx-server:
    environment:
      - PODX_CORS_ORIGINS=*
      - PODX_METRICS_ENABLED=true
    ports:
      - "8000:8000"

# docker-compose.prod.yml
services:
  podx-server:
    environment:
      - PODX_API_KEY=${PODX_API_KEY}
      - PODX_CORS_ORIGINS=https://your-app.com
    deploy:
      replicas: 3
```

Run with:
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Custom Build Arguments

Build with specific Python version or base image:

```dockerfile
ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim AS builder
```

Build command:
```bash
docker build --build-arg PYTHON_VERSION=3.11 -t podx-server:latest .
```

## Container Architecture

The Dockerfile uses a multi-stage build:

1. **Builder Stage**: Installs build dependencies and Python packages
2. **Runtime Stage**: Minimal production image with only runtime dependencies

This results in:
- Smaller image size (excludes build tools)
- Faster deployment
- Better security (fewer packages = smaller attack surface)

The container runs as a non-root user (`podx`) for security.

## Integration with Orchestration

See [KUBERNETES.md](./KUBERNETES.md) for Kubernetes deployment guide.

## API Documentation

Once running, access interactive API documentation at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`
