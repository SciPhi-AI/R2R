# R2R Full Mode Deployment on Google Cloud Platform

Complete production deployment of R2R Full Mode using **Google Cloud Vertex AI** for LLM and embeddings.

## 🎯 Architecture

### Infrastructure
- **Platform**: Google Cloud Platform (GCP)
- **VM**: Compute Engine n1-standard-4 (us-central1-a)
- **Disk**: 200GB pd-balanced
- **External IP**: 136.119.36.216
- **Network**: Firewall rules for TCP 7272-7276, 22

### AI Configuration
- **LLM Provider**: Google Cloud Vertex AI
  - Quality LLM: `gemini-2.0-flash`
  - Fast LLM: `gemini-2.0-flash-lite`
  - Reasoning LLM: `gemini-2.0-flash-thinking-exp`
- **Embeddings**: Vertex AI `text-embedding-004` (768 dimensions)
- **Authentication**: Service Account JSON key
- **Project**: r2r-full-deployment
- **Region**: us-central1

### Services (9 containers)
1. **r2r** (7272) - Main R2R API
2. **r2r-dashboard** (7273) - Web Dashboard
3. **postgres** (5432) - PostgreSQL + pgvector
4. **hatchet-engine** (7077) - Workflow orchestration
5. **hatchet-dashboard** (7274) - Workflow UI
6. **hatchet-postgres** - Hatchet database
7. **hatchet-rabbitmq** (5673, 15673) - Message broker
8. **unstructured** (7275) - Document parsing
9. **graph_clustering** (7276) - Graph analysis

## 🚀 Quick Start

### Prerequisites
- Google Cloud SDK (`gcloud`) installed and configured
- Access to project `r2r-full-deployment`
- Vertex AI API enabled

### Using Makefile (Recommended)

```bash
cd /Users/laptop/dev/R2R/deployment/gcp

# View all available commands
make help

# Full deployment from scratch
make deploy-full

# Connect to VM
make vm-ssh

# View logs
make logs
make logs-follow

# Check status
make status
make health

# Restart services
make r2r-restart
```

### Manual Deployment

```bash
# 1. Create VM
gcloud compute instances create r2r-production \
  --project=r2r-full-deployment \
  --zone=us-central1-a \
  --machine-type=n1-standard-4 \
  --create-disk=auto-delete=yes,boot=yes,size=200,type=pd-balanced,image=ubuntu-2204-jammy-v20251111 \
  --tags=r2r-server,http-server

# 2. Create firewall rules
gcloud compute firewall-rules create allow-r2r-services \
  --project=r2r-full-deployment \
  --direction=INGRESS \
  --action=ALLOW \
  --rules=tcp:7272-7276,tcp:22 \
  --source-ranges=0.0.0.0/0 \
  --target-tags=r2r-server

# 3. SSH to VM
gcloud compute ssh r2r-production --zone=us-central1-a --project=r2r-full-deployment

# 4. Install Docker (on VM)
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# 5. Clone R2R
git clone https://github.com/SciPhi-AI/R2R.git ~/R2R

# 6. Start services
cd ~/R2R/docker
docker compose -f compose.full.yaml --profile postgres up -d
```

## 🔧 Configuration Files

### Vertex AI Configuration
**Location**: `~/R2R/docker/user_configs/gemini-openai.toml`

```toml
[app]
fast_llm = "vertex_ai/gemini-2.0-flash-lite"
quality_llm = "vertex_ai/gemini-2.0-flash"
reasoning_llm = "vertex_ai/gemini-2.0-flash-thinking-exp"

[embedding]
provider = "litellm"
base_model = "vertex_ai/text-embedding-004"
base_dimension = 768
```

### Environment Variables
**Location**: `~/R2R/docker/env/r2r-full.env`

```bash
R2R_CONFIG_PATH=/app/user_configs/gemini-openai.toml
VERTEX_PROJECT=r2r-full-deployment
VERTEX_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=/app/vertex-ai-key.json
```

### Service Account
**Created**: `r2r-vertex-ai@r2r-full-deployment.iam.gserviceaccount.com`
**Roles**: `roles/aiplatform.user`
**Key Location**: `~/R2R/docker/vertex-ai-key.json` (on VM)

## 📊 Monitoring

### Check Service Status
```bash
cd ~/R2R/docker
docker compose -f compose.full.yaml ps
```

### View Logs
```bash
# R2R logs
docker compose -f compose.full.yaml logs -f r2r

# All services
docker compose -f compose.full.yaml logs -f

# Specific service
docker compose -f compose.full.yaml logs -f hatchet-engine
```

### Health Checks
```bash
# R2R API
curl http://136.119.36.216:7272/v3/health

# Test search
curl -X POST "http://136.119.36.216:7272/v3/retrieval/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "your search query", "limit": 10}'
```

## 🌐 Access URLs

- **R2R API**: http://136.119.36.216:7272
- **R2R Dashboard**: http://136.119.36.216:7273
- **Hatchet Dashboard**: http://136.119.36.216:7274
- **API Documentation**: http://136.119.36.216:7272/docs

## 🔄 Common Operations

### Restart Services
```bash
cd ~/R2R/docker
docker compose -f compose.full.yaml down
docker compose -f compose.full.yaml --profile postgres up -d
```

### Update Configuration
```bash
# Edit config
nano user_configs/gemini-openai.toml

# Restart R2R to apply
docker compose -f compose.full.yaml up -d --force-recreate r2r
```

### Clean Restart (DESTRUCTIVE - deletes data)
```bash
cd ~/R2R/docker
docker compose -f compose.full.yaml --profile postgres down -v
docker volume prune -af
docker compose -f compose.full.yaml --profile postgres up -d
```

### Update Vertex AI Key
```bash
# Edit env file
nano env/r2r-full.env
# Update GEMINI_API_KEY or GOOGLE_APPLICATION_CREDENTIALS

# Restart R2R
docker compose -f compose.full.yaml up -d --force-recreate r2r
```

## 🧪 Testing

### Upload Document
```bash
curl -X POST "http://136.119.36.216:7272/v3/documents" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/document.pdf"
```

### Search
```bash
curl -X POST "http://136.119.36.216:7272/v3/retrieval/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "artificial intelligence", "limit": 5}'
```

### RAG Query
```bash
curl -X POST "http://136.119.36.216:7272/v3/retrieval/rag" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is artificial intelligence?"}'
```

## 🛠️ Troubleshooting

### Container Crashes
```bash
# Check logs
docker compose -f compose.full.yaml logs --tail=100 r2r

# Check for dimension mismatch (512 vs 768)
# If you see "Dimension mismatch", clean and restart:
docker compose -f compose.full.yaml --profile postgres down -v
docker compose -f compose.full.yaml --profile postgres up -d
```

### Vertex AI Authentication Errors
```bash
# Verify credentials file exists
docker exec docker-r2r-1 ls -lh /app/vertex-ai-key.json

# Check environment variables
docker exec docker-r2r-1 env | grep -E "(VERTEX|GOOGLE_APPLICATION_CREDENTIALS)"

# Verify service account permissions
gcloud projects get-iam-policy r2r-full-deployment \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:r2r-vertex-ai@*"
```

### Network Issues
```bash
# Check firewall rules
gcloud compute firewall-rules list --filter="targetTags:r2r-server"

# Check VM external IP
gcloud compute instances describe r2r-production \
  --zone=us-central1-a \
  --format="get(networkInterfaces[0].accessConfigs[0].natIP)"
```

## 💰 Cost Management

### Stop VM (when not in use)
```bash
gcloud compute instances stop r2r-production \
  --zone=us-central1-a \
  --project=r2r-full-deployment
```

### Start VM
```bash
gcloud compute instances start r2r-production \
  --zone=us-central1-a \
  --project=r2r-full-deployment
```

### Delete All Resources (DESTRUCTIVE)
```bash
# Delete VM
gcloud compute instances delete r2r-production \
  --zone=us-central1-a \
  --project=r2r-full-deployment

# Delete firewall rules
gcloud compute firewall-rules delete allow-r2r-services \
  --project=r2r-full-deployment
```

## 📝 Important Notes

1. **Embeddings Dimension**: Vertex AI uses 768-dim embeddings. If changing from OpenAI (512-dim), you must clean the database.

2. **Service Account Key**: Keep `vertex-ai-key.json` secure. It's mounted read-only in the container.

3. **Persistent Data**: PostgreSQL data is stored in Docker volumes. Use `--profile postgres` flag when restarting to avoid recreating volumes.

4. **Quota Limits**: Monitor Vertex AI quota in GCP Console. Default quotas may need adjustment for production loads.

5. **Firewall**: Current rules allow access from anywhere (0.0.0.0/0). Restrict to specific IPs in production.

## 📚 Additional Resources

- [R2R Documentation](https://r2r-docs.sciphi.ai/)
- [Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs)
- [Docker Compose Reference](https://docs.docker.com/compose/)
- [Makefile Commands](./Makefile) - Full list of automation commands

## 🤝 Support

For issues:
1. Check logs: `docker compose -f compose.full.yaml logs -f r2r`
2. Verify configuration: `cat user_configs/gemini-openai.toml`
3. Test connectivity: `curl http://localhost:7272/v3/health`

---

**Deployment Date**: 2025-11-13
**R2R Version**: Latest (sciphiai/r2r:latest)
**Status**: ✅ Production Ready with Vertex AI
