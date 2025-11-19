# R2R Makefile Reference

Universal interface for R2R development and deployment.

## Quick Start

```bash
# Local development
make dev        # Start R2R locally
make logs       # View logs
make stop       # Stop services

# GCP deployment
make run        # Deploy to Google Cloud (full automation)
make gcp-status # Check deployment status
make gcp-logs   # View production logs
```

## Getting Started

### Local Development (5 minutes)

```bash
# 1. Show quickstart guide
make quickstart-local

# 2. Start R2R
make dev

# 3. Check health
make health

# 4. Access services
# API:       http://localhost:7272
# Dashboard: http://localhost:7273
```

### GCP Deployment (5 minutes)

```bash
# 1. Configure project (one-time setup)
cd deployment/gcp
nano Makefile  # Set PROJECT_ID = your-gcp-project-id

# 2. Deploy everything
make run

# 3. Check status
make gcp-health
```

## Command Reference

### Essential Commands

| Command | Description |
|---------|-------------|
| `make run` | Deploy to GCP (production) |
| `make dev` | Start R2R locally |
| `make stop` | Stop local services |
| `make logs` | View R2R logs |
| `make health` | Check service health |
| `make test` | Run test suite |

### Local Development

| Command | Description |
|---------|-------------|
| `make dev` | Start R2R with Docker Compose |
| `make stop` | Stop all services |
| `make restart` | Restart services |
| `make clean` | Stop and remove volumes |
| `make logs` | Follow R2R logs |
| `make logs-all` | Show all service logs |
| `make status` | Show service status |
| `make health` | Check R2R API health |
| `make shell` | Open shell in R2R container |

### GCP Deployment

| Command | Description |
|---------|-------------|
| `make run` | Full deployment (VM + Docker + R2R) |
| `make gcp-deploy-full` | Full deployment (explicit) |
| `make gcp-status` | Check deployment status |
| `make gcp-health` | Check all service health |
| `make gcp-logs` | View R2R logs |
| `make gcp-ssh` | SSH to GCP VM |
| `make gcp-restart` | Restart R2R services |
| `make gcp-stop` | Stop VM (save costs) |
| `make gcp-start` | Start stopped VM |
| `make gcp-destroy` | Delete all resources |

### Testing & Quality

| Command | Description |
|---------|-------------|
| `make test` | Run all tests |
| `make test-unit` | Unit tests only |
| `make test-integration` | Integration tests |
| `make lint` | Run ruff linter |
| `make format` | Format code with ruff |
| `make type-check` | Run mypy type checker |
| `make quality` | All quality checks |

### Docker Operations

| Command | Description |
|---------|-------------|
| `make build` | Build R2R Docker image |
| `make pull` | Pull latest images |
| `make db-shell` | Open PostgreSQL shell |
| `make db-reset` | Reset R2R database |

### Utilities

| Command | Description |
|---------|-------------|
| `make help` | Show all commands |
| `make info` | System information |
| `make version` | R2R version |
| `make quickstart-local` | Local dev guide |
| `make quickstart-gcp` | GCP deployment guide |

### Aliases

| Alias | Equivalent to |
|-------|---------------|
| `make up` | `make dev` |
| `make down` | `make stop` |
| `make deploy` | `make gcp-deploy-full` |
| `make ps` | `make status` |

## Common Workflows

### Daily Development

```bash
make dev          # Start services
make logs         # Monitor logs
# ... do work ...
make test         # Run tests
make lint         # Check code quality
make stop         # Stop services
```

### Deploy to Production

```bash
make run          # Automated GCP deployment
make gcp-health   # Verify deployment
make gcp-logs     # Check logs
```

### Troubleshooting

```bash
# Check what's running
make status       # Local
make gcp-status   # GCP

# View logs
make logs         # Local R2R
make logs-all     # All local services
make gcp-logs     # GCP R2R

# Restart services
make restart      # Local
make gcp-restart  # GCP

# Clean restart
make clean && make dev    # Local
```

### Cost Optimization

```bash
# Stop VM when not in use
make gcp-stop

# Start VM when needed
make gcp-start

# Check what's running
make gcp-status
```

## GCP Deployment Details

### What `make run` Does

1. Creates Compute Engine VM (n1-standard-4)
2. Configures firewall rules
3. Installs Docker and Docker Compose
4. Clones R2R repository
5. Copies configuration
6. Starts all services

**Duration**: ~5-10 minutes
**Cost**: ~$120/month running 24/7

### Services Deployed

- **R2R API** (port 7272) - Main API
- **R2R Dashboard** (port 7273) - Web UI
- **Hatchet Dashboard** (port 7274) - Workflow orchestration
- **PostgreSQL** - Vector database
- **MinIO** - Object storage
- **RabbitMQ** - Message queue
- **Unstructured** - Document parsing
- **Graph Clustering** - Graph analysis

### Access URLs

After deployment, services are available at:

```text
http://YOUR_VM_IP:7272  # R2R API
http://YOUR_VM_IP:7273  # R2R Dashboard
http://YOUR_VM_IP:7274  # Hatchet Dashboard
```

Get VM IP: `make gcp-status`

## Configuration

### Local Configuration

Edit `docker/user_configs/gemini-openai.toml` for:
- LLM models
- Embedding models
- Auth providers
- Database settings

### GCP Configuration

Edit `deployment/gcp/Makefile` for:
- `PROJECT_ID` - Your GCP project
- `ZONE` - Compute region
- `MACHINE_TYPE` - VM size
- `DISK_SIZE` - Storage size

## Environment Variables

Required for GCP deployment:

```bash
# Vertex AI
export VERTEX_PROJECT=your-project-id
export VERTEX_LOCATION=us-central1

# Optional: OpenAI fallback
export OPENAI_API_KEY=sk-...
```

See `docker/env/r2r-full.env` for all variables.

## Troubleshooting

### Services won't start

```bash
make logs         # Check logs
make status       # Check status
make restart      # Try restart
make clean        # Clean restart
```

### GCP deployment fails

```bash
# Check VM status
make gcp-status

# SSH to VM
make gcp-ssh

# Check service logs
make gcp-logs

# Try redeploy
cd deployment/gcp && make r2r-redeploy
```

### Database issues

```bash
make db-reset     # Reset local database
make gcp-ssh      # SSH and manually fix
```

### Port conflicts

If ports 7272-7276 are in use locally:

```bash
# Stop conflicting services
lsof -ti:7272 | xargs kill -9

# Or change ports in docker-compose.yaml
```

## Advanced Usage

### Custom Docker Build

```bash
# Build local image
make build

# Update docker-compose to use r2r:local
# Then start services
make dev
```

### Database Operations

```bash
# Open psql shell
make db-shell

# Run SQL
make db-shell
\c r2r
SELECT COUNT(*) FROM documents;
```

### Testing Specific Components

```bash
# Unit tests for specific module
cd py && pytest tests/unit/test_embeddings.py

# Integration test with verbose output
cd py && pytest tests/integration/ -v
```

## Best Practices

### Development

1. Always `make dev` before starting work
2. Run `make test` before committing
3. Use `make lint` to catch issues early
4. `make logs` to monitor during development

### Deployment

1. Test locally with `make dev` first
2. Use `make run` for initial deployment
3. Monitor with `make gcp-health`
4. Check logs with `make gcp-logs`
5. Stop VM when not in use: `make gcp-stop`

### Cost Management

```bash
# Daily usage (~8 hours)
make gcp-start     # Morning
# ... work ...
make gcp-stop      # Evening

# Weekend
make gcp-stop      # Friday
make gcp-start     # Monday
```

**Savings**: ~70% reduction in VM costs

## Getting Help

```bash
make help              # All commands
make quickstart-local  # Local dev guide
make quickstart-gcp    # GCP guide
```

**Documentation**:
- Local: `docker/README.md`
- GCP: `deployment/gcp/QUICKSTART.md`
- Full: `deployment/gcp/DEPLOYMENT.md`

## Examples

### Example 1: Quick Local Test

```bash
make dev
make health
make logs
# Test your changes
make test
make stop
```

### Example 2: Deploy to Production

```bash
# First time setup
cd deployment/gcp
nano Makefile  # Set PROJECT_ID

cd ../..
make run       # Deploy

# Later updates
make gcp-restart
```

### Example 3: Debug Production Issue

```bash
make gcp-logs                    # Check logs
make gcp-ssh                     # SSH to VM
cd ~/R2R/docker
docker compose -f compose.full.yaml logs r2r  # Detailed logs
```

---

**Quick Reference Card**:

```text
Development:  make dev | make logs | make stop
Production:   make run | make gcp-logs | make gcp-status
Testing:      make test | make lint
Help:         make help | make quickstart-local | make quickstart-gcp
```
