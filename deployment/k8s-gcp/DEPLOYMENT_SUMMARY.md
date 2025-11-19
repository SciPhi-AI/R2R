# R2R GKE Deployment - Implementation Summary

**Created:** 2025-11-20
**Status:** ✅ Complete and ready for deployment

## 🎯 What Was Created

Production-ready Kubernetes deployment for R2R on Google Kubernetes Engine (GKE) with full automation scripts and comprehensive documentation.

### Directory Structure

```text
deployment/k8s-gcp/
├── base/                              # Base Kubernetes manifests (16 files)
│   ├── namespace.yaml                 # r2r-system namespace
│   ├── serviceaccount.yaml            # Workload Identity ServiceAccount
│   ├── configmap-gcp.yaml             # GCP configuration (Vertex AI, Cloud SQL, GCS)
│   ├── secret-template.yaml           # Template for secrets (not committed)
│   ├── r2r-deployment.yaml            # R2R API with Cloud SQL proxy sidecar
│   ├── r2r-service.yaml               # R2R service with BackendConfig
│   ├── r2r-dashboard-deployment.yaml  # Frontend dashboard (2 replicas)
│   ├── unstructured-deployment.yaml   # Document parsing (2-8 replicas)
│   ├── graph-clustering-deployment.yaml # Graph clustering (1 replica)
│   ├── hatchet-rabbitmq.yaml          # RabbitMQ StatefulSet
│   ├── hatchet-api.yaml               # Hatchet API with Cloud SQL proxy
│   ├── hatchet-grpc.yaml              # Hatchet gRPC server
│   ├── hatchet-engine.yaml            # Controllers, scheduler, frontend
│   ├── ingress.yaml                   # GCP Load Balancer + ManagedCertificate
│   ├── hpa.yaml                       # Horizontal Pod Autoscalers
│   └── kustomization.yaml             # Base Kustomize config
├── overlays/production/
│   └── kustomization.yaml             # Production-specific overrides
├── scripts/                           # Automation scripts (4 files)
│   ├── 01-create-gcp-infrastructure.sh # Creates GKE, Cloud SQL, GCS, SA
│   ├── 02-create-secrets.sh           # Creates K8s secrets from .env.production
│   ├── 03-deploy-to-gke.sh            # Deploys R2R to GKE
│   └── 04-monitor.sh                  # Interactive monitoring tool
├── patches/                           # (Empty, reserved for custom patches)
├── README.md                          # Comprehensive deployment guide (400+ lines)
├── QUICKSTART.md                      # 15-20 minute quick start guide
└── DEPLOYMENT_SUMMARY.md              # This file
```

## 🏗️ Architecture Highlights

### GCP Managed Services Integration

1. **Cloud SQL for PostgreSQL 16** with pgvector
   - Regional high availability
   - Private IP only (no public exposure)
   - Cloud SQL Proxy sidecars for secure connections

2. **Cloud Storage (GCS)**
   - 3 buckets: documents, embeddings, graphs
   - Regional storage class
   - Workload Identity authentication

3. **Vertex AI**
   - Gemini 2.0 Flash for LLM operations
   - text-embedding-004 (768-dim) for embeddings
   - Workload Identity for authentication

4. **Google Cloud Load Balancer**
   - Global HTTPS load balancer
   - Managed SSL certificates (auto-renewing)
   - Health checks with BackendConfig

### Kubernetes Features

1. **High Availability**
   - Multi-zone GKE cluster (3-10 nodes)
   - Pod anti-affinity rules
   - Regional Cloud SQL with failover

2. **Auto-scaling**
   - Horizontal Pod Autoscaling (HPA)
   - GKE cluster autoscaling
   - Scales based on CPU/memory

3. **Security**
   - Workload Identity (no service account keys in pods)
   - Private Cloud SQL connections
   - Secrets management via Kubernetes
   - HTTPS with managed certificates

4. **Dependency Management**
   - Init containers for service readiness
   - Cloud SQL Proxy sidecars
   - Proper startup ordering

## 📋 Critical Configuration

### Automatic Knowledge Graph Extraction

**IMPORTANT:** The following configuration in `base/configmap-gcp.yaml` is CRITICAL for automatic extraction:

```yaml
AUTOMATIC_EXTRACTION: "true"
AUTOMATIC_DEDUPLICATION: "true"
```

Without these settings, documents will ingest but extraction status will remain "PENDING" forever.

### Cloud SQL Configuration

Must be updated in `overlays/production/kustomization.yaml` after infrastructure creation:

```yaml
- POSTGRES_HOST=10.x.x.x  # Replace with actual Cloud SQL private IP
```

### Domain Configuration

Update your domain in `overlays/production/kustomization.yaml`:

```yaml
patches:
  - target:
      kind: ManagedCertificate
      name: r2r-cert
    patch: |-
      - op: replace
        path: /spec/domains/0
        value: "r2r.yourdomain.com"
```

## 🚀 Deployment Process

### Prerequisites

✅ GCP account with billing enabled
✅ `gcloud` CLI installed and configured
✅ `kubectl` installed
✅ Production configuration files in project root:
  - `.env.production` (API keys, credentials)
  - `config.production.toml` (R2R config)
  - `vertex-ai-key.production.json` (GCP service account key)

### Step-by-Step Deployment

```bash
cd deployment/k8s-gcp/scripts

# 1. Create GCP infrastructure (10-15 minutes)
export GCP_PROJECT_ID="your-project-id"
./01-create-gcp-infrastructure.sh
# Outputs: Cloud SQL Private IP, Load Balancer IP

# 2. Update overlays/production/kustomization.yaml
#    - Replace POSTGRES_HOST with Cloud SQL IP
#    - Update domain name
#    - Update GCS bucket names
#    - Update project ID in Cloud SQL connection string

# 3. Point DNS to Load Balancer IP
#    r2r.yourdomain.com → [LOAD_BALANCER_IP]

# 4. Create Kubernetes secrets (1 minute)
./02-create-secrets.sh

# 5. Deploy to GKE (5-10 minutes)
./03-deploy-to-gke.sh

# 6. Monitor deployment
./04-monitor.sh
```

**Total deployment time:** 15-20 minutes

## 📊 Resource Allocation

| Component         | Replicas | CPU Request | Memory Request | CPU Limit | Memory Limit |
|-------------------|----------|-------------|----------------|-----------|--------------|
| R2R API           | 2-10     | 1000m       | 2Gi            | 2000m     | 4Gi          |
| R2R Dashboard     | 2-5      | 100m        | 256Mi          | 500m      | 512Mi        |
| Hatchet API       | 2        | 250m        | 512Mi          | 500m      | 1Gi          |
| Hatchet gRPC      | 1        | 250m        | 512Mi          | 500m      | 1Gi          |
| Unstructured      | 2-8      | 500m        | 1Gi            | 1000m     | 2Gi          |
| Graph Clustering  | 1        | 250m        | 512Mi          | 500m      | 1Gi          |
| RabbitMQ          | 1        | 200m        | 512Mi          | 500m      | 1Gi          |

**Total minimum resources:** ~3.6 vCPU, ~7.5 GB RAM
**Recommended node pool:** 3x n2-standard-4 (4 vCPU, 16 GB each)

## 💰 Estimated Costs

| Service             | Configuration            | Monthly Cost (USD) |
|---------------------|--------------------------|--------------------|
| GKE Cluster         | 3-10 n2-standard-4 nodes | $200 - $650        |
| Cloud SQL           | db-n1-standard-2         | $150               |
| Cloud Storage       | 100GB + operations       | $10 - $50          |
| Load Balancer       | Global HTTPS             | $25                |
| Vertex AI           | Pay per use              | $100 - $500        |
| **Total**           |                          | **$485 - $1,375**  |

## 🔧 Management Commands

### Monitoring

```bash
cd deployment/k8s-gcp/scripts
./04-monitor.sh  # Interactive menu

# Or specific commands:
kubectl get pods -n r2r-system
kubectl logs -n r2r-system deployment/r2r-api -f
kubectl top pods -n r2r-system
```

### Scaling

```bash
# Manual scaling
kubectl scale -n r2r-system deployment/r2r-api --replicas=5

# Check HPA status
kubectl get hpa -n r2r-system

# Edit HPA settings
kubectl edit hpa r2r-api-hpa -n r2r-system
```

### Updates

```bash
# Update R2R image version
cd deployment/k8s-gcp/base
# Edit kustomization.yaml: newTag: "3.4.0" → newTag: "3.5.0"

# Apply update
kubectl apply -k ../overlays/production/

# Monitor rollout
kubectl rollout status -n r2r-system deployment/r2r-api
```

## 🐛 Troubleshooting

### Common Issues

**Pods not starting:**
```bash
kubectl describe pod -n r2r-system <pod-name>
kubectl logs -n r2r-system <pod-name>
```

**Cloud SQL connection issues:**
```bash
kubectl logs -n r2r-system deployment/r2r-api -c cloud-sql-proxy
kubectl get configmap r2r-gcp-config -n r2r-system -o yaml | grep POSTGRES_HOST
```

**SSL certificate not provisioning:**
```bash
kubectl describe managedcertificate r2r-cert -n r2r-system
# Verify DNS points to Load Balancer IP
nslookup r2r.yourdomain.com
```

**Extraction not working:**
```bash
kubectl exec -n r2r-system deployment/r2r-api -- \
  curl -X POST http://localhost:7272/v3/documents/list \
    -H "Content-Type: application/json" \
    -d '{"limit": 5}' | jq '.results[].extraction_status'
```

## 📚 Documentation Reference

- **QUICKSTART.md** - 15-20 minute deployment guide with step-by-step instructions
- **README.md** - Comprehensive guide with architecture, troubleshooting, cost optimization
- **../gcp/QUICKSTART.md** - VM-based deployment (alternative to Kubernetes)
- **../../CLAUDE.md** - Project-wide R2R documentation

## ✅ Deployment Checklist

Before going to production:

- [ ] GCP project created with billing enabled
- [ ] Production configuration files ready (.env.production, config.production.toml, vertex-ai-key.production.json)
- [ ] Domain name registered and DNS configured
- [ ] Infrastructure created (GKE, Cloud SQL, GCS buckets)
- [ ] Kubernetes secrets created
- [ ] Production overlay updated with Cloud SQL IP and domain
- [ ] Deployment applied to GKE
- [ ] All pods running and healthy
- [ ] Health checks passing
- [ ] SSL certificate provisioned (15-30 min after DNS)
- [ ] Document ingestion tested
- [ ] Automatic extraction verified (extraction_status: "SUCCESS")
- [ ] Monitoring and alerting configured
- [ ] Backup strategy implemented for Cloud SQL

## 🎉 Next Steps

After successful deployment:

1. **Configure monitoring:** Set up Prometheus and Grafana for metrics
2. **Enable logging:** Configure Cloud Logging aggregation
3. **Set up backups:** Automate Cloud SQL and GCS backups
4. **Tune autoscaling:** Adjust HPA thresholds based on actual load
5. **Cost optimization:** Review resource usage and consider committed use discounts
6. **Security hardening:** Enable network policies, configure RBAC
7. **Disaster recovery:** Document and test recovery procedures

## 📞 Support

For issues:
- **R2R GitHub:** https://github.com/SciPhi-AI/R2R/issues
- **GCP Support:** https://cloud.google.com/support
- **Kubernetes docs:** https://kubernetes.io/docs/

---

**Created by:** Claude Code
**Date:** 2025-11-20
**R2R Version:** 3.4.0
**Deployment Type:** Production (GKE)
