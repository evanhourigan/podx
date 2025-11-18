# VPS Deployment Guide

Production deployment of PodX API Server on a VPS (DigitalOcean, Linode, AWS EC2, etc.) using systemd and Nginx.

## Overview

This guide covers deploying PodX on a Linux VPS with:
- **Systemd**: Process management and auto-restart
- **Nginx**: Reverse proxy with TLS/SSL
- **Let's Encrypt**: Free SSL certificates
- **UFW**: Firewall configuration

## Prerequisites

- VPS with Ubuntu 22.04 or Debian 12 (2GB RAM minimum, 4GB recommended)
- Root or sudo access
- Domain name pointing to your VPS IP (e.g., `api.podx.example.com`)
- SSH access to your server

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/evanhourigan/podx.git
cd podx
pip install -e ".[server]"

# 2. Set up systemd service
sudo cp examples/podx-server.service /etc/systemd/system/
sudo systemctl enable --now podx-server

# 3. Install and configure Nginx
sudo apt install nginx certbot python3-certbot-nginx
sudo cp examples/nginx-podx.conf /etc/nginx/sites-available/podx
sudo ln -s /etc/nginx/sites-available/podx /etc/nginx/sites-enabled/
sudo certbot --nginx -d api.podx.example.com
sudo systemctl reload nginx
```

## Detailed Setup

### Step 1: Server Preparation

Update your system:
```bash
sudo apt update && sudo apt upgrade -y
```

Install system dependencies:
```bash
# Python 3.12 (if not available, use 3.11+)
sudo apt install -y python3 python3-pip python3-venv

# System dependencies for PodX
sudo apt install -y ffmpeg git curl
```

Create a dedicated user for PodX:
```bash
sudo useradd -r -m -s /bin/bash podx
sudo mkdir -p /var/lib/podx/{uploads,backups}
sudo chown -R podx:podx /var/lib/podx
```

### Step 2: Install PodX

Clone the repository:
```bash
cd /opt
sudo git clone https://github.com/evanhourigan/podx.git
sudo chown -R podx:podx /opt/podx
```

Install as the podx user:
```bash
sudo -u podx bash << 'EOF'
cd /opt/podx
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -e ".[server]"
EOF
```

Verify installation:
```bash
sudo -u podx /opt/podx/venv/bin/podx --version
```

### Step 3: Configure Systemd Service

Copy the service file:
```bash
sudo cp /opt/podx/examples/podx-server.service /etc/systemd/system/
```

Create environment file for secrets:
```bash
sudo mkdir -p /etc/podx
sudo touch /etc/podx/server.env
sudo chmod 600 /etc/podx/server.env
sudo chown root:root /etc/podx/server.env
```

Add configuration to `/etc/podx/server.env`:
```bash
sudo nano /etc/podx/server.env
```

```bash
# /etc/podx/server.env
PODX_API_KEY=your-secret-api-key-here
PODX_CORS_ORIGINS=https://api.podx.example.com
```

Update the service file if needed:
```bash
sudo nano /etc/systemd/system/podx-server.service
```

Make sure `ExecStart` points to your venv:
```ini
ExecStart=/opt/podx/venv/bin/podx server start --host 0.0.0.0 --port 8000
```

Enable and start the service:
```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable podx-server

# Start the service
sudo systemctl start podx-server

# Check status
sudo systemctl status podx-server
```

View logs:
```bash
# Follow logs in real-time
sudo journalctl -u podx-server -f

# View recent logs
sudo journalctl -u podx-server -n 100 --no-pager
```

Test the server locally:
```bash
curl http://localhost:8000/health
```

### Step 4: Install and Configure Nginx

Install Nginx:
```bash
sudo apt install -y nginx
```

Copy Nginx configuration:
```bash
sudo cp /opt/podx/examples/nginx-podx.conf /etc/nginx/sites-available/podx
```

Update the configuration with your domain:
```bash
sudo nano /etc/nginx/sites-available/podx
```

Replace `api.podx.example.com` with your actual domain.

Enable the site:
```bash
# Remove default site (optional)
sudo rm /etc/nginx/sites-enabled/default

# Enable PodX site
sudo ln -s /etc/nginx/sites-available/podx /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

### Step 5: Configure Firewall

Install and configure UFW:
```bash
# Install UFW
sudo apt install -y ufw

# Allow SSH (important - don't lock yourself out!)
sudo ufw allow ssh

# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw --force enable

# Check status
sudo ufw status
```

### Step 6: SSL/TLS with Let's Encrypt

Install Certbot:
```bash
sudo apt install -y certbot python3-certbot-nginx
```

Obtain SSL certificate:
```bash
sudo certbot --nginx -d api.podx.example.com
```

Follow the prompts:
1. Enter your email address
2. Agree to Terms of Service
3. Choose whether to redirect HTTP to HTTPS (recommended: yes)

Certbot will automatically:
- Obtain the certificate
- Update your Nginx configuration
- Set up auto-renewal

Test auto-renewal:
```bash
sudo certbot renew --dry-run
```

Certificates will auto-renew via systemd timer. Check status:
```bash
sudo systemctl status certbot.timer
```

### Step 7: Verify Deployment

Check all services are running:
```bash
# PodX service
sudo systemctl status podx-server

# Nginx
sudo systemctl status nginx

# View logs
sudo journalctl -u podx-server -n 50
```

Test your API:
```bash
# Health check
curl https://api.podx.example.com/health

# API docs
curl https://api.podx.example.com/docs
```

Visit in your browser:
- `https://api.podx.example.com/health` - Health check
- `https://api.podx.example.com/docs` - Interactive API docs
- `https://api.podx.example.com/redoc` - ReDoc documentation

## Configuration

### Environment Variables

Configure in `/etc/podx/server.env`:

```bash
# Security
PODX_API_KEY=your-secret-key-here

# CORS (restrict to your domains)
PODX_CORS_ORIGINS=https://app.example.com,https://admin.example.com

# Storage paths
PODX_DB_PATH=/var/lib/podx/server.db
PODX_UPLOAD_DIR=/var/lib/podx/uploads

# Cleanup
PODX_CLEANUP_MAX_AGE_DAYS=7
PODX_CLEANUP_INTERVAL_HOURS=24

# Metrics (optional)
PODX_METRICS_ENABLED=true
```

After changing configuration:
```bash
sudo systemctl restart podx-server
```

### Nginx Tuning

For high-traffic deployments, tune Nginx in `/etc/nginx/nginx.conf`:

```nginx
worker_processes auto;
worker_rlimit_nofile 100000;

events {
    worker_connections 4096;
    use epoll;
    multi_accept on;
}

http {
    # Keepalive
    keepalive_timeout 65;
    keepalive_requests 100;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=100r/s;
    limit_req zone=api burst=200 nodelay;
}
```

## Maintenance

### Updating PodX

```bash
# Stop the service
sudo systemctl stop podx-server

# Backup database
sudo -u podx cp /var/lib/podx/server.db /var/lib/podx/backups/server-$(date +%Y%m%d).db

# Update code
cd /opt/podx
sudo -u podx git pull

# Update dependencies
sudo -u podx bash -c "source venv/bin/activate && pip install -e '.[server]'"

# Restart service
sudo systemctl start podx-server

# Check logs
sudo journalctl -u podx-server -f
```

### Backups

Create a backup script `/usr/local/bin/backup-podx.sh`:
```bash
#!/bin/bash
BACKUP_DIR="/var/lib/podx/backups"
DATE=$(date +%Y%m%d-%H%M%S)

# Backup database
cp /var/lib/podx/server.db "$BACKUP_DIR/server-$DATE.db"

# Backup uploads (optional - can be large)
# tar czf "$BACKUP_DIR/uploads-$DATE.tar.gz" /var/lib/podx/uploads

# Keep only last 30 days
find "$BACKUP_DIR" -name "server-*.db" -mtime +30 -delete

echo "Backup completed: $DATE"
```

Make it executable:
```bash
sudo chmod +x /usr/local/bin/backup-podx.sh
```

Add to cron (daily at 2 AM):
```bash
sudo crontab -e
```

Add line:
```
0 2 * * * /usr/local/bin/backup-podx.sh >> /var/log/podx-backup.log 2>&1
```

### Monitoring

View resource usage:
```bash
# CPU and memory
top -p $(pgrep -f podx)

# Disk usage
du -sh /var/lib/podx/*

# Service status
sudo systemctl status podx-server

# Recent errors
sudo journalctl -u podx-server -p err -n 50
```

## Troubleshooting

### Service won't start

```bash
# Check logs
sudo journalctl -u podx-server -n 100 --no-pager

# Check if port is in use
sudo netstat -tulpn | grep :8000

# Test manually
sudo -u podx /opt/podx/venv/bin/podx server start --host 0.0.0.0 --port 8000
```

### Nginx 502 Bad Gateway

```bash
# Check if PodX is running
sudo systemctl status podx-server

# Check Nginx error log
sudo tail -f /var/log/nginx/podx-error.log

# Test upstream
curl http://localhost:8000/health
```

### SSL certificate issues

```bash
# Check certificate expiry
sudo certbot certificates

# Force renewal
sudo certbot renew --force-renewal

# Check Nginx SSL config
sudo nginx -t
```

### Database locked errors

```bash
# Check if multiple processes are running
ps aux | grep podx

# Restart service
sudo systemctl restart podx-server

# If persistent, restore from backup
sudo systemctl stop podx-server
sudo -u podx cp /var/lib/podx/backups/server-YYYYMMDD.db /var/lib/podx/server.db
sudo systemctl start podx-server
```

### High CPU/memory usage

```bash
# Check running jobs
curl http://localhost:8000/jobs

# Adjust resource limits in systemd
sudo systemctl edit podx-server
```

Add override:
```ini
[Service]
MemoryLimit=2G
CPUQuota=150%
```

## Security Best Practices

1. **Use strong API keys**:
   ```bash
   # Generate secure key
   openssl rand -base64 32
   ```

2. **Restrict CORS origins**:
   ```bash
   # In /etc/podx/server.env
   PODX_CORS_ORIGINS=https://your-app.com
   ```

3. **Enable firewall**:
   ```bash
   sudo ufw enable
   sudo ufw status
   ```

4. **Regular updates**:
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

5. **Monitor logs**:
   ```bash
   sudo journalctl -u podx-server -f
   ```

6. **Use HTTPS only**: Ensure Nginx redirects HTTP to HTTPS

7. **Limit file upload size**: Set in Nginx config (`client_max_body_size`)

## Performance Optimization

### For high-traffic deployments:

1. **Run multiple workers** (modify systemd service):
   ```ini
   [Service]
   Environment="PODX_WORKERS=4"
   ExecStart=/opt/podx/venv/bin/uvicorn podx.server.app:app --host 0.0.0.0 --port 8000 --workers 4
   ```

2. **Enable Nginx caching** for static responses

3. **Use a CDN** for uploaded files

4. **Monitor with Prometheus + Grafana**:
   - Enable metrics: `PODX_METRICS_ENABLED=true`
   - Scrape `/metrics` endpoint

5. **Database optimization**:
   - Consider PostgreSQL for multi-worker setups
   - Regular VACUUM and ANALYZE

## Alternative: Docker Deployment on VPS

For a simpler deployment, use Docker instead:

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt install docker-compose-plugin

# Clone and deploy
git clone https://github.com/evanhourigan/podx.git
cd podx
docker-compose up -d

# Configure Nginx to proxy to localhost:8000
```

See [DOCKER.md](./DOCKER.md) for full Docker deployment guide.

## Getting Help

- **Documentation**: Check `/docs` endpoint for API documentation
- **Logs**: `sudo journalctl -u podx-server -f`
- **GitHub Issues**: https://github.com/evanhourigan/podx/issues
- **Health Check**: `curl https://api.podx.example.com/health`

## Next Steps

After deployment:
1. Test all endpoints with API documentation at `/docs`
2. Configure monitoring (Prometheus/Grafana)
3. Set up automated backups
4. Configure log rotation
5. Plan for scaling (load balancer, multiple instances)
