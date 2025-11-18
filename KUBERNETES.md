# Kubernetes Deployment Guide

Production-grade Kubernetes deployment for the PodX API Server.

## Overview

The PodX server can be deployed to Kubernetes with:
- **High availability**: Multiple replicas with auto-scaling
- **Health checks**: Liveness, readiness, and startup probes
- **Persistence**: Persistent volumes for database and uploads
- **Security**: Non-root containers, secrets management, RBAC
- **Monitoring**: Prometheus metrics endpoint
- **Auto-scaling**: Horizontal Pod Autoscaler based on CPU/memory

## Quick Start

### Prerequisites

- Kubernetes cluster (1.19+)
- `kubectl` configured to access your cluster
- Container image built and pushed to a registry

### Build and Push Image

```bash
# Build the image
docker build -t your-registry.com/podx-server:v3.0.0 .

# Push to registry
docker push your-registry.com/podx-server:v3.0.0

# Update k8s/deployment.yaml with your image
# Change: image: podx-server:latest
# To: image: your-registry.com/podx-server:v3.0.0
```

### Deploy to Kubernetes

```bash
# Create namespace (optional)
kubectl create namespace podx

# Apply all manifests
kubectl apply -f k8s/ -n podx

# Or apply individually in order:
kubectl apply -f k8s/configmap.yaml -n podx
kubectl apply -f k8s/secret.yaml -n podx
kubectl apply -f k8s/pvc.yaml -n podx
kubectl apply -f k8s/deployment.yaml -n podx
kubectl apply -f k8s/service.yaml -n podx
kubectl apply -f k8s/ingress.yaml -n podx
kubectl apply -f k8s/hpa.yaml -n podx
```

### Verify Deployment

```bash
# Check pod status
kubectl get pods -n podx

# Check deployment rollout
kubectl rollout status deployment/podx-server -n podx

# View logs
kubectl logs -f deployment/podx-server -n podx

# Check health
kubectl port-forward svc/podx-server 8000:8000 -n podx
curl http://localhost:8000/health
```

## Configuration

### ConfigMap (k8s/configmap.yaml)

Configure application settings:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: podx-config
data:
  cors-origins: "https://app.example.com,https://admin.example.com"
  cleanup-max-age-days: "7"
  cleanup-interval-hours: "24"
```

Update configuration:
```bash
kubectl edit configmap podx-config -n podx
kubectl rollout restart deployment/podx-server -n podx
```

### Secrets (k8s/secret.yaml)

Set API key for authentication:

```bash
# Generate a secure API key
API_KEY=$(openssl rand -base64 32)

# Create secret
kubectl create secret generic podx-secrets \
  --from-literal=api-key=$API_KEY \
  -n podx

# Or update existing secret
kubectl patch secret podx-secrets -n podx \
  -p "{\"stringData\":{\"api-key\":\"$API_KEY\"}}"
```

### Persistent Storage (k8s/pvc.yaml)

The deployment uses a PersistentVolumeClaim for database and uploads:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: podx-data-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
  storageClassName: standard  # Adjust for your cluster
```

**Important**: The PVC uses `ReadWriteOnce` which means:
- Only one pod can write at a time
- Suitable for SQLite database
- For multi-writer scenarios, consider using PostgreSQL instead

## Scaling

### Manual Scaling

```bash
# Scale to 5 replicas
kubectl scale deployment/podx-server --replicas=5 -n podx
```

### Auto-scaling (k8s/hpa.yaml)

The HorizontalPodAutoscaler automatically scales based on CPU and memory:

```yaml
spec:
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        averageUtilization: 80
```

View HPA status:
```bash
kubectl get hpa -n podx
kubectl describe hpa podx-server -n podx
```

## Ingress Configuration

### Basic Ingress (k8s/ingress.yaml)

Exposes the service with TLS:

```yaml
spec:
  tls:
  - hosts:
    - api.podx.example.com
    secretName: podx-tls
  rules:
  - host: api.podx.example.com
    http:
      paths:
      - path: /
        backend:
          service:
            name: podx-server
            port: 8000
```

Update the hostname:
```bash
# Edit ingress
kubectl edit ingress podx-server -n podx

# Or patch it
kubectl patch ingress podx-server -n podx \
  -p '{"spec":{"rules":[{"host":"api.your-domain.com"}]}}'
```

### TLS Certificate with cert-manager

If using cert-manager for automatic TLS:

```bash
# Install cert-manager (if not already installed)
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Create ClusterIssuer for Let's Encrypt
cat <<EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: your-email@example.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
EOF
```

The ingress annotation will trigger automatic certificate creation:
```yaml
annotations:
  cert-manager.io/cluster-issuer: letsencrypt-prod
```

## Monitoring

### Prometheus Metrics

The server exposes Prometheus metrics at `/metrics` when `PODX_METRICS_ENABLED=true`.

Available metrics:
- `podx_http_requests_total` - Total HTTP requests
- `podx_http_request_duration_seconds` - Request duration
- `podx_jobs_total` - Total jobs created
- `podx_jobs_by_status` - Jobs by status
- `podx_active_workers` - Active workers

### ServiceMonitor (for Prometheus Operator)

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: podx-server
  namespace: podx
spec:
  selector:
    matchLabels:
      app: podx-server
  endpoints:
  - port: http
    path: /metrics
    interval: 30s
```

Apply with:
```bash
kubectl apply -f k8s/servicemonitor.yaml -n podx
```

## Health Checks

The deployment includes comprehensive health checks:

### Liveness Probe
Checks if the container is alive:
```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: http
  initialDelaySeconds: 10
  periodSeconds: 30
```

### Readiness Probe
Checks if the container is ready to serve traffic:
```yaml
readinessProbe:
  httpGet:
    path: /health/ready
    port: http
  initialDelaySeconds: 5
  periodSeconds: 10
```

### Startup Probe
Gives the container time to start before liveness checks begin:
```yaml
startupProbe:
  httpGet:
    path: /health/live
    port: http
  failureThreshold: 30
  periodSeconds: 5
```

## Production Best Practices

### Resource Limits

Set appropriate resource requests and limits:

```yaml
resources:
  requests:
    cpu: 500m      # Guaranteed CPU
    memory: 512Mi  # Guaranteed memory
  limits:
    cpu: 2000m     # Maximum CPU
    memory: 2Gi    # Maximum memory
```

Adjust based on workload:
- **Light**: 250m CPU, 256Mi RAM
- **Medium**: 500m CPU, 512Mi RAM
- **Heavy**: 1000m+ CPU, 1Gi+ RAM

### Security Hardening

1. **Run as non-root**:
   ```yaml
   securityContext:
     runAsNonRoot: true
     runAsUser: 1000
     runAsGroup: 1000
   ```

2. **Enable API key authentication**:
   ```bash
   kubectl create secret generic podx-secrets \
     --from-literal=api-key=$(openssl rand -base64 32)
   ```

3. **Restrict CORS origins**:
   ```yaml
   data:
     cors-origins: "https://app.example.com,https://admin.example.com"
   ```

4. **Use Network Policies**:
   ```yaml
   apiVersion: networking.k8s.io/v1
   kind: NetworkPolicy
   metadata:
     name: podx-server
   spec:
     podSelector:
       matchLabels:
         app: podx-server
     policyTypes:
     - Ingress
     - Egress
     ingress:
     - from:
       - namespaceSelector:
           matchLabels:
             name: ingress-nginx
       ports:
       - protocol: TCP
         port: 8000
   ```

### High Availability

1. **Multiple replicas**: Run at least 3 replicas
2. **Pod Disruption Budget**:
   ```yaml
   apiVersion: policy/v1
   kind: PodDisruptionBudget
   metadata:
     name: podx-server
   spec:
     minAvailable: 2
     selector:
       matchLabels:
         app: podx-server
   ```

3. **Anti-affinity**: Spread pods across nodes
   ```yaml
   affinity:
     podAntiAffinity:
       preferredDuringSchedulingIgnoredDuringExecution:
       - weight: 100
         podAffinityTerm:
           labelSelector:
             matchLabels:
               app: podx-server
           topologyKey: kubernetes.io/hostname
   ```

## Troubleshooting

### Pods not starting

```bash
# Check pod status
kubectl get pods -n podx

# Describe pod for events
kubectl describe pod <pod-name> -n podx

# Check logs
kubectl logs <pod-name> -n podx
```

Common issues:
- **ImagePullBackOff**: Check image name and registry credentials
- **CrashLoopBackOff**: Check application logs
- **Pending**: Check resource availability and PVC binding

### Database locked errors

If using SQLite with multiple replicas:
- Reduce to 1 replica: `kubectl scale deployment/podx-server --replicas=1`
- Or migrate to PostgreSQL for multi-instance support

### Health checks failing

```bash
# Check health endpoint directly
kubectl port-forward <pod-name> 8000:8000 -n podx
curl http://localhost:8000/health

# Check readiness details
curl http://localhost:8000/health/ready
```

### Performance issues

```bash
# Check resource usage
kubectl top pods -n podx

# Check HPA status
kubectl get hpa -n podx

# Increase resources
kubectl edit deployment podx-server -n podx
```

## Cloud Provider Examples

### AWS EKS

```bash
# Create EKS cluster
eksctl create cluster --name podx --region us-west-2

# Configure storage class for EBS
kubectl apply -f - <<EOF
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: gp3
provisioner: ebs.csi.aws.com
parameters:
  type: gp3
  fsType: ext4
EOF

# Update PVC to use gp3
# Edit k8s/pvc.yaml: storageClassName: gp3
```

### Google GKE

```bash
# Create GKE cluster
gcloud container clusters create podx \
  --zone us-central1-a \
  --num-nodes 3

# Storage class is already configured (standard, premium)
# Use storageClassName: standard or premium in PVC
```

### Azure AKS

```bash
# Create AKS cluster
az aks create \
  --resource-group podx-rg \
  --name podx-cluster \
  --node-count 3 \
  --enable-addons monitoring

# Get credentials
az aks get-credentials --resource-group podx-rg --name podx-cluster

# Storage class is already configured (default, managed-premium)
```

## Maintenance

### Updating the Application

```bash
# Build and push new version
docker build -t your-registry.com/podx-server:v3.1.0 .
docker push your-registry.com/podx-server:v3.1.0

# Update deployment
kubectl set image deployment/podx-server \
  podx-server=your-registry.com/podx-server:v3.1.0 \
  -n podx

# Monitor rollout
kubectl rollout status deployment/podx-server -n podx

# Rollback if needed
kubectl rollout undo deployment/podx-server -n podx
```

### Backup and Restore

```bash
# Backup database
kubectl exec -n podx deployment/podx-server -- \
  tar czf - /data/server.db | cat > backup.tar.gz

# Restore database
cat backup.tar.gz | kubectl exec -i -n podx deployment/podx-server -- \
  tar xzf - -C /
```

## Next Steps

- Configure monitoring with Prometheus and Grafana
- Set up centralized logging with ELK/EFK stack
- Implement GitOps with ArgoCD or Flux
- Add tracing with Jaeger or Zipkin
- Set up disaster recovery and backup automation
