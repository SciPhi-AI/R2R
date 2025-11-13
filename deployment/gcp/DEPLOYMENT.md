# R2R Full Mode GCP Deployment Guide

Complete step-by-step guide for deploying R2R Full Mode on Google Cloud Platform with Vertex AI.

## 📋 Prerequisites

1. **Google Cloud Account** with billing enabled
2. **gcloud CLI** installed and configured
   ```bash
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID
   ```
3. **APIs Enabled**:
   - Compute Engine API
   - Vertex AI API
   - IAM API

## 🔐 Security Setup

### 1. Protect Sensitive Files

```bash
cd /path/to/R2R/deployment/gcp

# Copy .env template
cp .env.example .env

# Edit with your values (DO NOT commit this file)
nano .env
```

### 2. Create Vertex AI Service Account

```bash
# Set your project ID
export GCP_PROJECT_ID=your-project-id

# Create service account
gcloud iam service-accounts create r2r-vertex-ai \
  --display-name="R2R Vertex AI Service Account" \
  --project=$GCP_PROJECT_ID

# Grant Vertex AI permissions
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member="serviceAccount:r2r-vertex-ai@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"

# Create JSON key
gcloud iam service-accounts keys create vertex-ai-key.json \
  --iam-account=r2r-vertex-ai@${GCP_PROJECT_ID}.iam.gserviceaccount.com \
  --project=$GCP_PROJECT_ID

# IMPORTANT: This file will NOT be committed to git (.gitignore)
ls -lh vertex-ai-key.json
```

## 🚀 Deployment Steps

### Option 1: Automated Deployment (Recommended)

```bash
cd /path/to/R2R/deployment/gcp

# Edit Makefile with your project details
nano Makefile
# Update: PROJECT_ID, ZONE, VM_NAME

# Full deployment
make deploy-full
```

This will:
1. Create Compute Engine VM
2. Create firewall rules
3. Install Docker
4. Clone R2R repository
5. Deploy all services with Vertex AI

### Option 2: Manual Deployment

#### Step 1: Create VM

```bash
gcloud compute instances create r2r-production \
  --project=YOUR_PROJECT_ID \
  --zone=us-central1-a \
  --machine-type=n1-standard-4 \
  --create-disk=auto-delete=yes,boot=yes,size=200,type=pd-balanced,image=projects/ubuntu-os-cloud/global/images/ubuntu-2204-jammy-v20251111 \
  --tags=r2r-server,http-server \
  --labels=env=production,app=r2r
```

#### Step 2: Create Firewall Rules

```bash
gcloud compute firewall-rules create allow-r2r-services \
  --project=YOUR_PROJECT_ID \
  --direction=INGRESS \
  --action=ALLOW \
  --rules=tcp:7272-7276,tcp:22 \
  --source-ranges=0.0.0.0/0 \
  --target-tags=r2r-server
```

#### Step 3: Install Docker on VM

```bash
# SSH to VM
gcloud compute ssh r2r-production --zone=us-central1-a

# Install Docker
sudo apt-get update -qq
sudo apt-get install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt-get update -qq
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Verify
docker --version
docker compose version
```

#### Step 4: Clone R2R and Configure

```bash
# Clone repository
git clone https://github.com/SciPhi-AI/R2R.git ~/R2R
cd ~/R2R/docker

# Create configuration directory
mkdir -p user_configs
```

#### Step 5: Upload Configuration Files

**From your local machine**:

```bash
# Upload Vertex AI config
gcloud compute scp config.template.toml \
  r2r-production:~/R2R/docker/user_configs/gemini-openai.toml \
  --zone=us-central1-a

# Upload service account key
gcloud compute scp vertex-ai-key.json \
  r2r-production:~/R2R/docker/vertex-ai-key.json \
  --zone=us-central1-a
```

#### Step 6: Configure Environment Variables

**On VM** (`~/R2R/docker/env/r2r-full.env`):

```bash
# SSH to VM
gcloud compute ssh r2r-production --zone=us-central1-a

cd ~/R2R/docker

# Edit environment file
nano env/r2r-full.env
```

Add these lines:

```bash
# R2R Configuration
R2R_CONFIG_PATH=/app/user_configs/gemini-openai.toml

# Vertex AI
VERTEX_PROJECT=YOUR_PROJECT_ID
VERTEX_LOCATION=us-central1
VERTEXAI_PROJECT=YOUR_PROJECT_ID
VERTEXAI_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=/app/vertex-ai-key.json

# API Keys (optional - fallback providers)
OPENAI_API_KEY=sk-...
GROQ_API_KEY=gsk_...
```

Remove conflicting line:
```bash
# Remove or comment out:
# R2R_CONFIG_NAME=full
```

#### Step 7: Update Docker Compose

Add volume mount for service account key:

```bash
nano compose.full.yaml
```

Find the `r2r:` service `volumes:` section and add:

```yaml
volumes:
  - ./user_configs:/app/user_configs
  - ./vertex-ai-key.json:/app/vertex-ai-key.json:ro  # Add this line
  - ./user_tools:/app/user_tools
```

#### Step 8: Deploy Services

```bash
cd ~/R2R/docker

# Start all services
docker compose -f compose.full.yaml --profile postgres up -d

# Wait 1-2 minutes for initialization
sleep 120

# Check status
docker compose -f compose.full.yaml ps

# Check health
curl http://localhost:7272/v3/health
```

## ✅ Verification

### 1. Check Services Status

```bash
make status
# or
cd ~/R2R/docker && docker compose -f compose.full.yaml ps
```

Expected output: All 9 services running/healthy

### 2. Test API Health

```bash
curl http://YOUR_VM_IP:7272/v3/health
```

Expected: `{"results":{"message":"ok"}}`

### 3. Test Document Upload

```bash
echo "Test document about AI" > test.txt

curl -X POST "http://YOUR_VM_IP:7272/v3/documents" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@test.txt"
```

Wait 30 seconds, then test search:

```bash
curl -X POST "http://YOUR_VM_IP:7272/v3/retrieval/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "artificial intelligence", "limit": 5}'
```

## 🔧 Configuration Details

### Vertex AI Models Used

| Purpose | Model |
|---------|-------|
| Quality LLM | `gemini-2.0-flash` |
| Fast LLM | `gemini-2.0-flash-lite` |
| Reasoning | `gemini-2.0-flash-thinking-exp` |
| Vision | `gemini-2.0-flash` |
| Embeddings | `text-embedding-004` (768-dim) |

### Service Ports

| Service | Port | Description |
|---------|------|-------------|
| R2R API | 7272 | Main REST API |
| R2R Dashboard | 7273 | Web UI |
| Hatchet Dashboard | 7274 | Workflow monitoring |
| Unstructured | 7275 | Document parsing |
| Graph Clustering | 7276 | Graph analysis |

## 🛠️ Management Commands

### Using Makefile

```bash
make help          # Show all commands
make status        # Service status
make logs          # View R2R logs
make logs-follow   # Follow logs in real-time
make health        # Health checks
make r2r-restart   # Restart R2R service
make r2r-clean     # Clean restart (deletes data)
```

### Manual Commands

```bash
# SSH to VM
make vm-ssh
# or
gcloud compute ssh r2r-production --zone=us-central1-a

# View logs
cd ~/R2R/docker
docker compose -f compose.full.yaml logs -f r2r

# Restart service
docker compose -f compose.full.yaml restart r2r

# Stop all
docker compose -f compose.full.yaml down

# Start all
docker compose -f compose.full.yaml --profile postgres up -d
```

## 🔍 Troubleshooting

### Issue: Dimension Mismatch Error

```text
ValueError: Dimension mismatch: Table 'r2r_default.chunks' was created with dimension 512, but 768 was provided.
```

**Solution**: Clean database and restart

```bash
cd ~/R2R/docker
docker compose -f compose.full.yaml --profile postgres down -v
docker compose -f compose.full.yaml --profile postgres up -d
```

### Issue: Vertex AI Authentication Error

```text
google.auth.exceptions.DefaultCredentialsError: File was not found.
```

**Solution**: Verify credentials file

```bash
# Check file exists
docker exec docker-r2r-1 ls -lh /app/vertex-ai-key.json

# Check environment variable
docker exec docker-r2r-1 env | grep GOOGLE_APPLICATION_CREDENTIALS

# Recreate container
docker compose -f compose.full.yaml up -d --force-recreate r2r
```

### Issue: Service Not Starting

```bash
# Check logs
docker compose -f compose.full.yaml logs --tail=100 r2r

# Check Docker resources
docker stats --no-stream

# Restart VM if needed
gcloud compute instances stop r2r-production --zone=us-central1-a
gcloud compute instances start r2r-production --zone=us-central1-a
```

## 📊 Monitoring

### View Logs

```bash
# All services
make logs-all

# Specific service
docker compose -f compose.full.yaml logs -f hatchet-engine

# Last 100 lines with timestamps
docker compose -f compose.full.yaml logs --tail=100 -t
```

### Resource Usage

```bash
# Container stats
docker stats --no-stream

# VM resources
gcloud compute instances describe r2r-production \
  --zone=us-central1-a \
  --format="table(name,status,machineType,networkInterfaces[0].accessConfigs[0].natIP)"
```

### Health Monitoring

```bash
# API health
curl http://YOUR_VM_IP:7272/v3/health

# All endpoints
make health-all
```

## 💰 Cost Optimization

### Stop VM When Not in Use

```bash
# Stop
make vm-stop
# or
gcloud compute instances stop r2r-production --zone=us-central1-a

# Start
make vm-start
# or
gcloud compute instances start r2r-production --zone=us-central1-a
```

### Clean Up Resources

```bash
# Delete everything (DESTRUCTIVE)
make destroy-all

# Or manually
gcloud compute instances delete r2r-production --zone=us-central1-a
gcloud compute firewall-rules delete allow-r2r-services
```

## 🔒 Security Best Practices

1. **Restrict Firewall Access**:
   ```bash
   gcloud compute firewall-rules update allow-r2r-services \
     --source-ranges=YOUR_IP_ADDRESS/32
   ```

2. **Rotate Service Account Keys** regularly:
   ```bash
   # Create new key
   gcloud iam service-accounts keys create new-key.json \
     --iam-account=r2r-vertex-ai@PROJECT_ID.iam.gserviceaccount.com

   # Delete old key
   gcloud iam service-accounts keys delete KEY_ID \
     --iam-account=r2r-vertex-ai@PROJECT_ID.iam.gserviceaccount.com
   ```

3. **Enable Cloud Audit Logs** for API access tracking

4. **Use Secret Manager** for production:
   ```bash
   # Store API key in Secret Manager
   echo -n "your-api-key" | gcloud secrets create vertex-api-key --data-file=-
   ```

## 📚 Additional Resources

- [R2R Documentation](https://r2r-docs.sciphi.ai/)
- [Vertex AI Pricing](https://cloud.google.com/vertex-ai/pricing)
- [Compute Engine Pricing](https://cloud.google.com/compute/pricing)
- [GCP Best Practices](https://cloud.google.com/docs/enterprise/best-practices-for-enterprise-organizations)

## 🎯 Next Steps

1. **Set up monitoring**: Configure Cloud Monitoring alerts
2. **Enable backups**: Automate PostgreSQL backups
3. **Configure SSL**: Add HTTPS with Let's Encrypt
4. **Scale up**: Increase VM size for production loads
5. **Add authentication**: Implement R2R authentication layer

---

**Deployment Status**: ✅ Production Ready with Vertex AI
**Last Updated**: 2025-11-13
**Maintained By**: R2R GCP Deployment Team
