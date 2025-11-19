# R2R Deployment on Google Kubernetes Engine (GKE)

Production-ready deployment of R2R on Google Cloud Platform using:
- **GKE** (Google Kubernetes Engine) for container orchestration
- **Cloud SQL** for PostgreSQL with pgvector
- **Cloud Storage** for document and embedding storage
- **Vertex AI** for embeddings and LLM operations
- **Workload Identity** for secure service account authentication

## 📋 Prerequisites

### Required Tools
- `gcloud` CLI (Google Cloud SDK) - [Install](https://cloud.google.com/sdk/docs/install)
- `kubectl` - Kubernetes command-line tool
- `kustomize` (optional, kubectl has built-in support)
- `jq` - JSON processor for scripts

### GCP Requirements
- GCP Project with billing enabled
- Sufficient quotas for:
  - GKE clusters (3-10 nodes)
  - Cloud SQL instance
  - Regional external IP address
- IAM permissions to create:
  - GKE clusters
  - Cloud SQL instances
  - Service accounts
  - Storage buckets

### Configuration Files
Ensure these files exist in the project root:
- `.env.production` - Environment variables and API keys
- `config.production.toml` - R2R configuration with Vertex AI settings
- `vertex-ai-key.production.json` - GCP service account key

## 🚀 Quick Start (15-20 minutes)

### Step 1: Create GCP Infrastructure

```bash
cd deployment/k8s-gcp/scripts

# Set your GCP project ID
export GCP_PROJECT_ID="your-project-id"

# Run infrastructure setup script
./01-create-gcp-infrastructure.sh
```

This script creates:
- ✅ GKE cluster (3-10 nodes, auto-scaling)
- ✅ Cloud SQL PostgreSQL 16 with pgvector
- ✅ Cloud Storage buckets for documents/embeddings/graphs
- ✅ Service account with Workload Identity
- ✅ Static IP for Load Balancer

**Duration**: 10-15 minutes

### Step 2: Update Configuration

After infrastructure creation, update the following values:

1. **Cloud SQL Private IP** in `overlays/production/kustomization.yaml`:
   ```yaml
   - POSTGRES_HOST=10.x.x.x  # Replace with actual IP from script output
   ```

2. **DNS A Record**: Point your domain to the Load Balancer IP from script output
   ```text
   r2r.yourdomain.com → [LOAD_BALANCER_IP]
   ```

3. **Domain in Ingress** (`overlays/production/kustomization.yaml`):
   ```yaml
   - op: replace
     path: /spec/domains/0
     value: "r2r.yourdomain.com"  # Your actual domain
   ```

### Step 3: Create Kubernetes Secrets

```bash
# Create secrets from production files
./02-create-secrets.sh
```

This creates:
- `r2r-secrets` - API keys and credentials from `.env.production`
- `r2r-config-toml` - R2R configuration from `config.production.toml`
- `vertex-ai-key` - GCP service account key

### Step 4: Deploy to GKE

```bash
# Deploy R2R to GKE
./03-deploy-to-gke.sh
```

This will:
1. Build Kustomize manifests
2. Show deployment preview
3. Apply all resources to GKE
4. Wait for deployments to be ready
5. Verify health of all services

**Duration**: 5-10 minutes

### Step 5: Verify Deployment

```bash
# Monitor deployment
./04-monitor.sh
# Select option 1 to see status
```

Check that all pods are running:
```bash
kubectl get pods -n r2r-system
```

Expected pods:
- `r2r-api-*` (2-3 replicas)
- `r2r-dashboard-*` (2 replicas)
- `hatchet-api-*` (2 replicas)
- `hatchet-grpc-*` (1 replica)
- `hatchet-controllers-*` (1 replica)
- `hatchet-scheduler-*` (1 replica)
- `hatchet-frontend-*` (1 replica)
- `rabbitmq-*` (1 replica)
- `unstructured-*` (2-3 replicas)
- `graph-clustering-*` (1 replica)

## 📖 Architecture Overview

### Components

```text
┌─────────────────────────────────────────────────────────┐
│            Google Cloud Load Balancer (HTTPS)            │
│                  (r2r.yourdomain.com)                    │
└─────────────────────────────────────────────────────────┘
                          │
            ┌─────────────┴─────────────┐
            │                           │
     ┌──────▼──────┐           ┌───────▼────────┐
     │  R2R API    │           │  R2R Dashboard │
     │  (7272)     │           │     (3000)     │
     │  2-10 pods  │           │    2-5 pods    │
     └──────┬──────┘           └────────────────┘
            │
     ┌──────┴──────────────────────────────┐
     │                                     │
┌────▼────┐  ┌──────────┐  ┌─────────┐   │
│Cloud SQL│  │Hatchet   │  │Unstruct │   │
│pgvector │  │Workflows │  │Parser   │   │
│(Managed)│  │Orchestr. │  │2-8 pods │   │
└─────────┘  └──────────┘  └─────────┘   │
     │                                     │
┌────▼────┐  ┌──────────┐  ┌─────────┐   │
│Cloud    │  │RabbitMQ  │  │Graph    │   │
│Storage  │  │Message Q │  │Cluster  │   │
│(GCS)    │  │1 pod     │  │1 pod    │   │
└─────────┘  └──────────┘  └─────────┘   │
     │                                     │
┌────▼────┐                                │
│Vertex AI│◄───────────────────────────────┘
│Gemini   │  (Workload Identity)
│Models   │
└─────────┘
```

### Key Features

1. **High Availability**
   - Multi-zone GKE cluster
   - Regional Cloud SQL with automatic failover
   - Load balancer with health checks
   - Anti-affinity rules for pod distribution

2. **Auto-scaling**
   - Horizontal Pod Autoscaling (HPA) for all services
   - GKE cluster autoscaling (3-10 nodes)
   - Scales based on CPU and memory usage

3. **Security**
   - Workload Identity for secure GCP service authentication
   - Private IP for Cloud SQL (no public exposure)
   - HTTPS with Google-managed SSL certificates
   - Secrets management in Kubernetes
   - Network policies (optional)

4. **Managed Services**
   - Cloud SQL (no manual database management)
   - Cloud Storage (scalable object storage)
   - Vertex AI (managed AI/ML endpoints)
   - Cloud Load Balancer (managed ingress)

## 🛠️ Management Commands

### Deployment Management

```bash
# View deployment status
kubectl get deployments -n r2r-system

# Scale R2R API
kubectl scale deployment r2r-api -n r2r-system --replicas=5

# Restart deployment
kubectl rollout restart deployment r2r-api -n r2r-system

# View rollout status
kubectl rollout status deployment r2r-api -n r2r-system
```

### Monitoring

```bash
# Interactive monitoring tool
./scripts/04-monitor.sh

# Or specific commands:
./scripts/04-monitor.sh status    # Deployment status
./scripts/04-monitor.sh health    # Health checks
./scripts/04-monitor.sh logs      # View logs
./scripts/04-monitor.sh resources # CPU/Memory usage
```

### Logs

```bash
# R2R API logs
kubectl logs -n r2r-system deployment/r2r-api -f

# Hatchet logs
kubectl logs -n r2r-system deployment/hatchet-api -f

# All pods logs
kubectl logs -n r2r-system -l app=r2r-api -f --max-log-requests=10
```

### Port Forwarding (Local Access)

```bash
# R2R API
kubectl port-forward -n r2r-system svc/r2r-api 7272:7272

# R2R Dashboard
kubectl port-forward -n r2r-system svc/r2r-dashboard 3000:3000

# Hatchet Dashboard
kubectl port-forward -n r2r-system svc/hatchet-frontend 8080:8080

# Then access at http://localhost:<port>
```

## 🔧 Configuration

### Environment Variables

Key environment variables in `configmap-gcp.yaml`:

```yaml
# Vertex AI
VERTEX_PROJECT: "r2r-full-deployment"
VERTEX_LOCATION: "us-central1"

# Cloud SQL
POSTGRES_HOST: "10.x.x.x"  # Private IP
POSTGRES_PORT: "5432"
POSTGRES_DB: "r2r"

# Cloud Storage
GCS_BUCKET_DOCUMENTS: "r2r-documents-{project-id}"
GCS_BUCKET_EMBEDDINGS: "r2r-embeddings-{project-id}"

# Critical: Enable automatic extraction
AUTOMATIC_EXTRACTION: "true"
AUTOMATIC_DEDUPLICATION: "true"
```

### Resource Limits

Default resource allocations:

| Component         | Requests (CPU/Memory) | Limits (CPU/Memory) | Replicas |
|-------------------|-----------------------|---------------------|----------|
| R2R API           | 1000m / 2Gi           | 2000m / 4Gi         | 2-10     |
| Dashboard         | 100m / 256Mi          | 500m / 512Mi        | 2-5      |
| Hatchet API       | 250m / 512Mi          | 500m / 1Gi          | 2        |
| Hatchet gRPC      | 250m / 512Mi          | 500m / 1Gi          | 1        |
| Unstructured      | 500m / 1Gi            | 1000m / 2Gi         | 2-8      |
| Graph Clustering  | 250m / 512Mi          | 500m / 1Gi          | 1        |

Adjust in `overlays/production/kustomization.yaml` as needed.

## 🐛 Troubleshooting

### Pods Not Starting

```bash
# Check pod status
kubectl get pods -n r2r-system

# Describe pod to see events
kubectl describe pod -n r2r-system <pod-name>

# Check init container logs
kubectl logs -n r2r-system <pod-name> -c <init-container-name>
```

Common issues:
- **Init containers waiting**: Dependencies (Cloud SQL, Hatchet) not ready
- **ImagePullBackOff**: Network issues or invalid image
- **CrashLoopBackOff**: Check logs for application errors

### Cloud SQL Connection Issues

```bash
# Verify Cloud SQL instance is running
gcloud sql instances describe r2r-postgres

# Check Cloud SQL proxy logs
kubectl logs -n r2r-system deployment/r2r-api -c cloud-sql-proxy

# Verify private IP is correct in ConfigMap
kubectl get configmap r2r-gcp-config -n r2r-system -o yaml | grep POSTGRES_HOST
```

### Workload Identity Issues

```bash
# Verify service account binding
gcloud iam service-accounts get-iam-policy \
  r2r-workload@${PROJECT_ID}.iam.gserviceaccount.com

# Check annotation on Kubernetes ServiceAccount
kubectl get sa r2r-ksa -n r2r-system -o yaml

# Test Vertex AI access from pod
kubectl exec -n r2r-system deployment/r2r-api -- \
  gcloud auth list
```

### Ingress/Load Balancer Issues

```bash
# Check ingress status
kubectl describe ingress r2r-ingress -n r2r-system

# View load balancer backends
gcloud compute backend-services list

# Check managed certificate status
kubectl describe managedcertificate r2r-cert -n r2r-system
```

SSL Certificate provisioning takes 15-30 minutes after DNS propagation.

### Automatic Extraction Not Working

```bash
# Check R2R logs for extraction errors
kubectl logs -n r2r-system deployment/r2r-api | grep -i extraction

# Verify automatic_extraction is enabled
kubectl exec -n r2r-system deployment/r2r-api -- \
  cat /app/r2r.toml | grep automatic_extraction

# Check Hatchet workflow registration
kubectl logs -n r2r-system deployment/hatchet-api | grep workflow

# Verify documents extraction status
kubectl exec -n r2r-system deployment/r2r-api -- \
  curl -X POST http://localhost:7272/v3/documents/list \
    -H "Content-Type: application/json" \
    -d '{"limit": 5}' | jq '.results[].extraction_status'
```

## 💰 Cost Optimization

### Estimated Monthly Costs

| Service             | Configuration                | Monthly Cost (USD) |
|---------------------|------------------------------|--------------------|
| GKE Cluster         | 3-10 n2-standard-4 nodes     | $200 - $650        |
| Cloud SQL           | db-n1-standard-2 (Regional)  | $150               |
| Cloud Storage       | 100GB with 1000 ops/day      | $10 - $50          |
| Load Balancer       | Global HTTPS LB              | $25                |
| Vertex AI           | Variable (pay per use)       | $100 - $500        |
| **Total**           |                              | **$485 - $1,375**  |

### Cost Reduction Tips

1. **Use Spot VMs for non-critical workloads** (70% discount)
   ```bash
   # Add to node pool configuration
   --spot
   ```

2. **Committed Use Discounts** (57% off for 3-year commitment)
   - Purchase in GCP Console

3. **Regional instead of multi-regional** where possible

4. **Auto-scaling to minimum during low traffic**
   ```bash
   # Scale down when idle
   kubectl scale deployment r2r-api -n r2r-system --replicas=2
   ```

5. **Cloud SQL automated backups retention**
   ```bash
   # Reduce backup retention from 7 to 3 days
   gcloud sql instances patch r2r-postgres --retained-backups-count=3
   ```

## 🔄 Updates and Maintenance

### Update R2R Image

```bash
# Edit kustomization.yaml
cd deployment/k8s-gcp/base
# Change: newTag: "3.4.0" → newTag: "3.5.0"

# Apply updates
kubectl apply -k ../overlays/production/

# Monitor rollout
kubectl rollout status deployment r2r-api -n r2r-system
```

### Database Migrations

```bash
# Backup database before migration
gcloud sql backups create --instance=r2r-postgres

# Run migrations (R2R handles this automatically on startup)
kubectl logs -n r2r-system deployment/r2r-api | grep migration
```

### SSL Certificate Renewal

Managed certificates auto-renew. Monitor status:
```bash
kubectl describe managedcertificate r2r-cert -n r2r-system
```

## 🗑️ Cleanup

### Delete R2R Deployment (Keep Infrastructure)

```bash
kubectl delete -k deployment/k8s-gcp/overlays/production/
```

### Delete Everything (Including GCP Resources)

```bash
# Delete GKE cluster
gcloud container clusters delete r2r-production --region=us-central1

# Delete Cloud SQL
gcloud sql instances delete r2r-postgres

# Delete buckets
gsutil rm -r gs://r2r-documents-${PROJECT_ID}
gsutil rm -r gs://r2r-embeddings-${PROJECT_ID}
gsutil rm -r gs://r2r-graphs-${PROJECT_ID}

# Delete static IP
gcloud compute addresses delete r2r-production-ip --global

# Delete service account
gcloud iam service-accounts delete r2r-workload@${PROJECT_ID}.iam.gserviceaccount.com
```

## 📚 Additional Resources

- [R2R Documentation](https://r2r-docs.sciphi.ai/)
- [GKE Best Practices](https://cloud.google.com/kubernetes-engine/docs/best-practices)
- [Cloud SQL for PostgreSQL](https://cloud.google.com/sql/docs/postgres)
- [Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs)
- [Workload Identity](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity)

## 🆘 Support

For issues and questions:
- **R2R Issues**: https://github.com/SciPhi-AI/R2R/issues
- **GCP Support**: https://cloud.google.com/support

---

**Version**: 1.0.0
**Last Updated**: 2025-01-20
**Maintainer**: R2R Team
