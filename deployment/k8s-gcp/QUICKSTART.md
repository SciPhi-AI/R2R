# R2R GKE Quick Start Guide

Get R2R running on Google Kubernetes Engine in 15-20 minutes.

## ⚡ Prerequisites (5 minutes)

1. **Install required tools**:
   ```bash
   # Google Cloud SDK
   curl https://sdk.cloud.google.com | bash
   exec -l $SHELL
   gcloud init

   # kubectl (if not already installed)
   gcloud components install kubectl

   # jq for JSON processing
   brew install jq  # macOS
   sudo apt-get install jq  # Ubuntu
   ```

2. **Prepare configuration files**:
   ```bash
   # Ensure these files exist in project root:
   ls -lh ../../../.env.production
   ls -lh ../../../config.production.toml
   ls -lh ../../../vertex-ai-key.production.json
   ```

3. **Set GCP project**:
   ```bash
   export GCP_PROJECT_ID="your-project-id"
   gcloud config set project ${GCP_PROJECT_ID}
   ```

## 🚀 Deployment Steps

### Step 1: Create Infrastructure (10-15 minutes)

```bash
cd deployment/k8s-gcp/scripts

# Create GKE cluster, Cloud SQL, buckets, and service accounts
./01-create-gcp-infrastructure.sh
```

**What this does**:
- ✅ Creates GKE cluster (3 nodes, auto-scaling to 10)
- ✅ Creates Cloud SQL PostgreSQL 16 with pgvector
- ✅ Creates 3 Cloud Storage buckets
- ✅ Creates service account with Workload Identity
- ✅ Reserves static IP for Load Balancer

**Save these values from output**:
- Cloud SQL Private IP: `10.x.x.x`
- Load Balancer IP: `x.x.x.x`

### Step 2: Update Configuration (2 minutes)

1. **Edit** `deployment/k8s-gcp/overlays/production/kustomization.yaml`:
   ```yaml
   configMapGenerator:
     - name: r2r-gcp-config
       behavior: merge
       literals:
         # Replace with actual Cloud SQL IP from Step 1
         - POSTGRES_HOST=10.x.x.x
         - HATCHET_DATABASE_POSTGRES_HOST=10.x.x.x

         # Update bucket names with your project ID
         - GCS_BUCKET_DOCUMENTS=r2r-documents-your-project-id
         - GCS_BUCKET_EMBEDDINGS=r2r-embeddings-your-project-id
         - GCS_BUCKET_GRAPHS=r2r-graphs-your-project-id

   patches:
     # Update domain
     - target:
         kind: ManagedCertificate
         name: r2r-cert
       patch: |-
         - op: replace
           path: /spec/domains/0
           value: "r2r.yourdomain.com"  # Your domain

     # Update Cloud SQL connection
     - target:
         kind: Deployment
         labelSelector: "component=backend"
       patch: |-
         - op: replace
           path: /spec/template/spec/containers/0/args/2
           value: "your-project-id:us-central1:r2r-postgres"

     # Update ServiceAccount
     - target:
         kind: ServiceAccount
         name: r2r-ksa
       patch: |-
         - op: replace
           path: /metadata/annotations/iam.gke.io~1gcp-service-account
           value: "r2r-workload@your-project-id.iam.gserviceaccount.com"
   ```

2. **Point DNS** to Load Balancer IP:
   ```text
   r2r.yourdomain.com A record → [LOAD_BALANCER_IP from Step 1]
   ```

### Step 3: Create Secrets (1 minute)

```bash
cd deployment/k8s-gcp/scripts

# Create Kubernetes secrets from production files
./02-create-secrets.sh
```

Verify:
```bash
kubectl get secrets -n r2r-system
kubectl get configmaps -n r2r-system
```

### Step 4: Deploy to GKE (5-10 minutes)

```bash
# Deploy all resources
./03-deploy-to-gke.sh
```

**The script will**:
1. Build Kustomize manifests
2. Show preview and ask for confirmation
3. Apply to GKE cluster
4. Wait for all pods to be ready
5. Verify health checks

Watch deployment:
```bash
watch kubectl get pods -n r2r-system
```

Wait for all pods to show `Running` status.

### Step 5: Verify and Test (2 minutes)

```bash
# Monitor deployment
./04-monitor.sh

# Or manually:
kubectl get pods -n r2r-system
kubectl get svc -n r2r-system
kubectl get ingress -n r2r-system
```

**Port-forward for local testing**:
```bash
kubectl port-forward -n r2r-system svc/r2r-api 7272:7272 &
curl http://localhost:7272/v3/health | jq .
```

Expected output:
```json
{
  "status": "healthy",
  "version": "3.4.0"
}
```

**Test document ingestion**:
```bash
# Upload a test document
curl -X POST http://localhost:7272/v3/documents/create \
  -H "Content-Type: multipart/form-data" \
  -F "file=@test.pdf"

# Check extraction status (should automatically become SUCCESS)
curl -X POST http://localhost:7272/v3/documents/list \
  -H "Content-Type: application/json" \
  -d '{"limit": 1}' | jq '.results[0].extraction_status'
```

## 🎉 Success!

Your R2R deployment is now running on GKE!

### Access URLs

**While DNS/SSL provisioning** (use port-forward):
```bash
# R2R API
kubectl port-forward -n r2r-system svc/r2r-api 7272:7272
# → http://localhost:7272

# R2R Dashboard
kubectl port-forward -n r2r-system svc/r2r-dashboard 3000:3000
# → http://localhost:3000

# Hatchet Dashboard
kubectl port-forward -n r2r-system svc/hatchet-frontend 8080:8080
# → http://localhost:8080
```

**After DNS propagation and SSL cert** (~15-30 minutes):
```text
https://r2r.yourdomain.com
```

## 📊 Monitor Your Deployment

```bash
# Interactive monitoring tool
cd deployment/k8s-gcp/scripts
./04-monitor.sh

# Select from menu:
# 1 - Deployment status
# 2 - Health checks
# 3 - R2R logs
# 7 - CPU/Memory usage
```

## 🐛 Quick Troubleshooting

**Pods not starting?**
```bash
kubectl describe pod -n r2r-system <pod-name>
kubectl logs -n r2r-system <pod-name>
```

**Cloud SQL connection failed?**
```bash
# Check private IP is correct
kubectl get configmap r2r-gcp-config -n r2r-system -o yaml | grep POSTGRES_HOST

# Check Cloud SQL proxy logs
kubectl logs -n r2r-system deployment/r2r-api -c cloud-sql-proxy
```

**Extraction not working?**
```bash
# Check automatic_extraction is true
kubectl get configmap r2r-gcp-config -n r2r-system -o yaml | grep AUTOMATIC

# Check Hatchet workflows
kubectl logs -n r2r-system deployment/hatchet-api | grep workflow
```

**SSL certificate not provisioning?**
```bash
# Check certificate status (takes 15-30 min after DNS)
kubectl describe managedcertificate r2r-cert -n r2r-system

# Verify DNS is pointed to Load Balancer
nslookup r2r.yourdomain.com
```

## 💰 Cost Estimate

**Minimal** (3 nodes, minimal traffic): ~$485/month
- GKE: $200
- Cloud SQL: $150
- Storage: $10
- Load Balancer: $25
- Vertex AI: $100

**Typical** (5-7 nodes, moderate traffic): ~$750/month

**High traffic** (10 nodes, heavy usage): ~$1,375/month

## 🔧 Next Steps

1. **Set up monitoring**: Install Prometheus and Grafana
2. **Configure backups**: Automate Cloud SQL and GCS backups
3. **Enable logging**: Set up Cloud Logging aggregation
4. **Add custom domain**: Update ingress with your domain
5. **Tune resources**: Adjust HPA settings based on load

## 📚 Full Documentation

For comprehensive documentation, see:
- [Full README](./README.md)
- [Main R2R CLAUDE.md](../../CLAUDE.md)
- [GCP Deployment Guide](../../deployment/gcp/QUICKSTART.md)

## 🆘 Need Help?

- **Deployment script failed?** Check the logs in script output
- **Pods crashing?** Run `./04-monitor.sh` and select "logs"
- **Still stuck?** Open an issue on [GitHub](https://github.com/SciPhi-AI/R2R/issues)

---

**Deployment Time**: 15-20 minutes
**Difficulty**: Intermediate
**Cost**: $485-1,375/month
