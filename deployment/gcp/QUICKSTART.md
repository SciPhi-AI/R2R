# R2R GCP Quick Start

5-minute guide to deploy R2R Full Mode with Vertex AI on Google Cloud Platform.

## Prerequisites

- Google Cloud account with billing enabled
- `gcloud` CLI configured
- Project with Vertex AI API enabled

## 1. Setup Service Account (2 minutes)

```bash
export GCP_PROJECT_ID=your-project-id

# Create service account
gcloud iam service-accounts create r2r-vertex-ai \
  --display-name="R2R Vertex AI" \
  --project=$GCP_PROJECT_ID

# Grant permissions
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
  --member="serviceAccount:r2r-vertex-ai@${GCP_PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"

# Create key
gcloud iam service-accounts keys create vertex-ai-key.json \
  --iam-account=r2r-vertex-ai@${GCP_PROJECT_ID}.iam.gserviceaccount.com
```

## 2. Deploy with Makefile (3 minutes)

```bash
cd /path/to/R2R/deployment/gcp

# Edit Makefile - update PROJECT_ID
nano Makefile

# Full automated deployment
make deploy-full
```

That's it! Access your R2R instance at `http://YOUR_VM_IP:7272`

## 3. Verify

```bash
# Check status
make status

# Test health
make health

# View logs
make logs
```

## Quick Commands

```bash
make help           # All commands
make vm-ssh         # SSH to VM
make logs-follow    # Live logs
make r2r-restart    # Restart R2R
make health-all     # Check all services
```

## What You Get

- ✅ R2R API (port 7272)
- ✅ R2R Dashboard (port 7273)
- ✅ Hatchet Dashboard (port 7274)
- ✅ Vertex AI Gemini 2.0 Flash
- ✅ Vertex AI text-embedding-004
- ✅ 9 services fully configured

## Troubleshooting

**Services not healthy?**
```bash
make logs
```

**Need to restart?**
```bash
make r2r-restart
```

**Clean restart?**
```bash
make r2r-clean
```

## Next Steps

- Read [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed configuration
- Read [README.md](./README.md) for architecture overview
- Check [Makefile](./Makefile) for all available commands

## Costs

**Approximate monthly costs** (us-central1):
- VM n1-standard-4: ~$120/month running 24/7
- 200GB pd-balanced disk: ~$16/month
- Vertex AI: Pay-per-use (varies by usage)

**Cost saving**: Use `make vm-stop` when not in use.

---

**Questions?** See full documentation in [DEPLOYMENT.md](./DEPLOYMENT.md)
