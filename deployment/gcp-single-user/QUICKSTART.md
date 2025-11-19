# R2R Single-User Quick Start

Get R2R running on Google Cloud in 10 minutes for **$20-25/month**.

## 💰 Cost Comparison

| Deployment | Monthly Cost | Best For |
|------------|--------------|----------|
| **Single-User (this guide)** | **$20-25** | 1 user, moderate usage |
| GKE Full Deployment | $485-1,375 | Team, high availability |
| VM Full Mode | $60-80 | 1-3 users, full features |

## 📋 Prerequisites (2 minutes)

1. **GCP Account** with billing enabled
2. **gcloud CLI** installed:
   ```bash
   curl https://sdk.cloud.google.com | bash
   exec -l $SHELL
   gcloud init
   ```

3. **Configuration files** in project root:
   ```bash
   ls -lh ../../../{.env.production,config.production.toml,vertex-ai-key.production.json}
   ```

## 🚀 Deployment (10 minutes)

### Step 1: Create VM (3 minutes)

```bash
cd deployment/gcp-single-user/scripts

# Set project
export GCP_PROJECT_ID="your-project-id"

# Create cost-optimized VM (e2-medium with preemptible)
./01-create-vm.sh \
  --project="${GCP_PROJECT_ID}" \
  --machine-type=e2-medium \
  --preemptible

# Save the External IP shown in output!
```

**What this does:**
- ✅ Creates e2-medium VM (4GB RAM, 2 vCPU) - $8/month with preemptible
- ✅ 50GB disk - $2/month
- ✅ Service account for Vertex AI
- ✅ Firewall rules for HTTP/HTTPS

### Step 2: Install Docker (2 minutes)

```bash
# Remote installation
./02-install-docker.sh --instance=r2r-single-user --zone=us-central1-a

# OR SSH and install locally
gcloud compute ssh r2r-single-user --zone=us-central1-a
cd /tmp
# Copy installation script to VM, then:
./02-install-docker.sh --local
exit
```

### Step 3: Configure Environment (2 minutes)

```bash
# Copy files to VM
gcloud compute scp \
  ../../../.env.production \
  ../../../config.production.toml \
  ../../../vertex-ai-key.production.json \
  r2r-single-user:~/r2r/ \
  --zone=us-central1-a

# Copy deployment files
gcloud compute scp \
  ../.env.template \
  ../docker-compose.yaml \
  ../config.single-user.toml \
  ../init-db.sql \
  r2r-single-user:~/r2r/ \
  --zone=us-central1-a

# SSH to VM
gcloud compute ssh r2r-single-user --zone=us-central1-a

# On VM: Configure
cd ~/r2r
cp .env.production .env.production  # Already copied
# Edit if needed: nano .env.production
```

### Step 4: Deploy R2R (3 minutes)

```bash
# On VM:
cd ~/r2r

# Start R2R (minimal mode)
docker compose up -d

# Check health
curl http://localhost:7272/v3/health | jq .

# View logs
docker compose logs -f r2r
```

## ✅ Verify Deployment

```bash
# Health check
curl http://localhost:7272/v3/health

# Test document upload
curl -X POST http://localhost:7272/v3/documents/create \
  -F "file=@test.pdf"

# Check extraction status (should become SUCCESS automatically)
curl -X POST http://localhost:7272/v3/documents/list \
  -H "Content-Type: application/json" \
  -d '{"limit": 1}' | jq '.results[0].extraction_status'
```

## 🌐 Access R2R

**From VM (port-forward):**
```bash
# On local machine:
gcloud compute ssh r2r-single-user --zone=us-central1-a -- -L 7272:localhost:7272

# Then open: http://localhost:7272
```

**From internet (optional):**
```bash
# Enable external access (security: use with auth!)
# Edit .env.production and restart:
docker compose restart r2r
```

## 💰 Cost Optimization

### Schedule VM (save 60%)

```bash
# On local machine, create Cloud Scheduler jobs:
# Start VM at 9 AM
gcloud scheduler jobs create app-engine r2r-start \
  --schedule="0 9 * * *" \
  --time-zone="America/New_York" \
  --http-method=POST \
  --uri="https://compute.googleapis.com/compute/v1/projects/${GCP_PROJECT_ID}/zones/us-central1-a/instances/r2r-single-user/start" \
  --oauth-service-account-email=YOUR_SERVICE_ACCOUNT

# Stop VM at 6 PM
gcloud scheduler jobs create app-engine r2r-stop \
  --schedule="0 18 * * *" \
  --time-zone="America/New_York" \
  --http-method=POST \
  --uri="https://compute.googleapis.com/compute/v1/projects/${GCP_PROJECT_ID}/zones/us-central1-a/instances/r2r-single-user/stop" \
  --oauth-service-account-email=YOUR_SERVICE_ACCOUNT
```

**Result:** VM runs 9 hours/day = ~$13/month instead of $26

### Use Free Tier (extreme budget)

```bash
# Create e2-micro (1GB RAM - limited performance)
./01-create-vm.sh \
  --project="${GCP_PROJECT_ID}" \
  --machine-type=e2-micro

# Cost: $0/month (Always Free tier)
# Trade-off: Limited to ~100 documents, slower processing
```

## 🛠️ Management

```bash
# On local machine:
cd deployment/gcp-single-user/scripts

# Start VM
./manage-vm.sh start

# Stop VM (cost savings!)
./manage-vm.sh stop

# Check status
./manage-vm.sh status

# SSH to VM
./manage-vm.sh ssh

# View logs
./manage-vm.sh logs
```

## 📊 Usage Modes

### Minimal Mode (default) - $20-25/month
- R2R API + PostgreSQL
- Simple orchestration (no Hatchet)
- Local file storage
- 4GB RAM e2-medium VM

### Full Mode - $40-50/month
```bash
# Requires e2-standard-2 (8GB RAM)
# On VM:
docker compose -f docker-compose.full.yaml up -d
```
- Includes Hatchet orchestration
- RabbitMQ message queue
- Better for complex workflows

## 🐛 Troubleshooting

**VM not accessible:**
```bash
# Check firewall
gcloud compute firewall-rules list | grep r2r

# Check VM status
gcloud compute instances describe r2r-single-user --zone=us-central1-a
```

**R2R not starting:**
```bash
# SSH to VM
gcloud compute ssh r2r-single-user --zone=us-central1-a

# Check logs
docker compose logs r2r
docker compose logs postgres

# Restart
docker compose restart
```

**Extraction not working:**
```bash
# Check config
docker exec r2r-api cat /app/r2r.toml | grep automatic_extraction
# Should show: automatic_extraction = true

# Check Vertex AI credentials
docker exec r2r-api ls -l /app/credentials/
```

## 🎉 Success!

Your R2R is now running for **$20-25/month** with:
- ✅ Full PostgreSQL with pgvector
- ✅ Vertex AI integration
- ✅ Automatic knowledge graph extraction
- ✅ Auto-scaling (via Docker resource limits)
- ✅ Daily backups (optional)

## 📚 Next Steps

1. **Set up backups:**
   ```bash
   # On VM:
   cd ~/r2r
   ./04-backup.sh

   # Add to crontab for daily backups
   crontab -e
   # Add: 0 2 * * * /home/USER/r2r/04-backup.sh
   ```

2. **Enable SSL (optional):**
   - Point domain to VM IP
   - Install Nginx with Let's Encrypt
   - See README.md for details

3. **Monitor costs:**
   ```bash
   # View billing
   gcloud billing budgets list
   ```

## 💡 Cost Breakdown

| Component | Configuration | Monthly Cost |
|-----------|--------------|--------------|
| VM (e2-medium, preemptible) | 2 vCPU, 4GB RAM | $8 |
| VM (9h/day schedule) | 50% usage | $13 |
| Disk | 50GB standard | $2 |
| Vertex AI | Light usage | $5-10 |
| **TOTAL (24/7)** | | **$15-20** |
| **TOTAL (9h/day)** | | **$20-25** |

---

**Deployment Time:** 10 minutes
**Monthly Cost:** $20-25 (vs $485+ for GKE)
**Perfect for:** Single user, moderate document processing
