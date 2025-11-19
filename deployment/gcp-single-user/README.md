# R2R Single-User Deployment on GCP

Cost-optimized deployment for individual users: **$20-25/month** (vs $485-1,375 for GKE cluster).

## 📊 Overview

This deployment provides full R2R functionality on a single VM with Docker Compose, optimized for cost-efficiency while maintaining production-grade capabilities.

**Key Benefits:**
- 💰 **20-50x cheaper** than GKE deployment
- 🚀 **Full functionality** - PostgreSQL, pgvector, Vertex AI
- ⚡ **Quick setup** - 10 minutes from zero to running
- 📈 **Scalable** - Easy migration path to larger deployments
- 🔒 **Secure** - Vertex AI with service account, private networking

## 💰 Cost Breakdown

### Minimal Mode (Recommended for Single User)
| Component | Configuration | Monthly Cost |
|-----------|--------------|--------------|
| VM | e2-medium (4GB RAM, preemptible, 9h/day) | $13 |
| Disk | 50GB standard persistent | $2 |
| Vertex AI | Light usage (~1000 requests) | $5-10 |
| **Total** | | **$20-25** |

### Full Mode (With Hatchet)
- VM: e2-standard-2 (8GB RAM) - $40/month
- Total: **$40-50/month**

### Free Tier (Ultra Budget)
- VM: e2-micro (1GB RAM, Always Free) - $0
- Disk: 30GB (first 30GB free) - $0
- Total: **$0-5/month** (only AI API usage)

## 🏗️ Architecture

```text
┌─────────────────────────────────────────┐
│  GCP VM (e2-medium, 4GB RAM)            │
│  ┌───────────────────────────────────┐  │
│  │  Docker Compose Stack             │  │
│  │                                   │  │
│  │  ┌──────────┐  ┌───────────────┐ │  │
│  │  │ R2R API  │  │  PostgreSQL   │ │  │
│  │  │  (7272)  │  │  + pgvector   │ │  │
│  │  └────┬─────┘  └───────┬───────┘ │  │
│  │       │                │         │  │
│  │  ┌────▼────────────────▼─────┐   │  │
│  │  │  Shared Volumes (Local)   │   │  │
│  │  │  - Documents, Embeddings  │   │  │
│  │  └───────────────────────────┘   │  │
│  └───────────────────────────────────┘  │
│            │                            │
│     ┌──────▼───────┐                    │
│     │ Vertex AI SA │                    │
│     └──────┬───────┘                    │
└────────────┼────────────────────────────┘
             │
    ┌────────▼─────────┐
    │   Vertex AI      │
    │ Gemini Models    │
    │ text-embedding   │
    └──────────────────┘
```

## 📋 Prerequisites

1. **GCP Account** with billing enabled
2. **gcloud CLI** installed and configured
3. **Configuration files** in project root:
   - `.env.production` - API keys and credentials
   - `config.production.toml` - R2R configuration
   - `vertex-ai-key.production.json` - GCP service account key

## 🚀 Quick Start

See [QUICKSTART.md](./QUICKSTART.md) for step-by-step 10-minute deployment.

## 📂 Directory Structure

```sql
gcp-single-user/
├── docker-compose.yaml           # Minimal mode (recommended)
├── docker-compose.full.yaml      # Full mode with Hatchet
├── .env.template                 # Environment variables template
├── config.single-user.toml       # Optimized R2R configuration
├── init-db.sql                   # PostgreSQL initialization
├── scripts/
│   ├── 01-create-vm.sh          # Create GCP VM
│   ├── 02-install-docker.sh     # Install Docker on VM
│   ├── 03-deploy.sh             # Deploy R2R
│   ├── 04-backup.sh             # Backup data
│   └── manage-vm.sh             # VM management (start/stop/status)
├── QUICKSTART.md                 # 10-minute deployment guide
└── README.md                     # This file
```

## 🔧 Configuration Modes

### Minimal Mode (Default)
```yaml
services:
  - postgres (pgvector)
  - r2r (simple orchestration)
```

**Pros:**
- Lowest cost ($20-25/month)
- Lowest resource usage (2GB RAM for R2R)
- Sufficient for most single-user workloads

**Limitations:**
- No Hatchet workflows
- Manual workflow management
- Basic document parsing

### Full Mode
```yaml
services:
  - postgres (pgvector)
  - rabbitmq
  - hatchet (API, engine)
  - r2r (Hatchet orchestration)
```

**Pros:**
- Automatic workflows
- Better for complex document processing
- Hatchet dashboard for monitoring

**Requires:**
- Larger VM (e2-standard-2, 8GB RAM)
- Higher cost ($40-50/month)

## 💡 Cost Optimization Strategies

### 1. VM Scheduling (60% savings)
Stop VM when not in use:
```bash
# Using Cloud Scheduler
# Start: 9 AM, Stop: 6 PM (9h/day)
# Saves: ~60% on VM costs
```

### 2. Preemptible Instances (70% savings)
Use spot instances for non-critical workloads:
```bash
./01-create-vm.sh --preemptible
# Trade-off: Max 24h runtime, can be terminated
```

### 3. Disk Optimization
- Use standard persistent disk (not SSD)
- 50GB sufficient for most workloads
- Set retention policies for backups

### 4. AI Model Selection
Use cost-efficient models in `config.single-user.toml`:
```toml
fast_llm = "vertex_ai/gemini-2.0-flash-lite"  # Cheapest
quality_llm = "vertex_ai/gemini-2.0-flash"    # Balanced
```

### 5. Batch Operations
- Process documents in batches
- Cache embeddings
- Limit max_tokens_to_sample

## 🔐 Security

- Service account authentication for Vertex AI
- Private networking (no public PostgreSQL port)
- Firewall rules limit access
- Optional: Enable authentication in config

## 📈 Scaling Path

1. **Start:** Single-user minimal ($20-25/month)
2. **Grow:** Switch to full mode ($40-50/month)
3. **Team:** Move to larger VM ($60-80/month)
4. **Production:** Migrate to GKE deployment

Data remains compatible across all tiers.

## 🛠️ Management

### Start/Stop VM
```bash
./scripts/manage-vm.sh start   # Start VM
./scripts/manage-vm.sh stop    # Stop VM (cost savings)
./scripts/manage-vm.sh status  # Check status
```

### Backups
```bash
# Manual backup
./scripts/04-backup.sh

# Automated (add to crontab)
0 2 * * * /home/USER/r2r/scripts/04-backup.sh
```

### Monitoring
```bash
# View logs
docker compose logs -f r2r

# Check resource usage
docker stats

# Health check
curl http://localhost:7272/v3/health
```

## 🐛 Troubleshooting

### Common Issues

**1. Out of Memory**
- Upgrade to e2-standard-2 (8GB RAM)
- Or add swap file:
```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

**2. Slow Performance**
- Check VM resources: `docker stats`
- Review Vertex AI quotas
- Consider upgrading machine type

**3. Extraction Not Working**
- Verify `automatic_extraction = true` in config
- Check Vertex AI service account permissions
- Review R2R logs: `docker compose logs r2r`

## 📚 Additional Resources

- [R2R Documentation](https://r2r-docs.sciphi.ai/)
- [Vertex AI Pricing](https://cloud.google.com/vertex-ai/pricing)
- [GCP Free Tier](https://cloud.google.com/free)
- [Main CLAUDE.md](../../CLAUDE.md) - Project documentation

## 🆘 Support

- **Issues:** https://github.com/SciPhi-AI/R2R/issues
- **GCP Support:** https://cloud.google.com/support
- **Cost Estimator:** https://cloud.google.com/products/calculator

---

**Version:** 1.0.0
**Last Updated:** 2025-11-20
**Deployment Time:** 10 minutes
**Monthly Cost:** $20-25 (minimal) / $40-50 (full)
