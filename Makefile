# R2R Universal Makefile
# Unified interface for local development and GCP deployment

.DEFAULT_GOAL := help

# Colors for output
GREEN  := \033[0;32m
YELLOW := \033[0;33m
BLUE   := \033[0;34m
RED    := \033[0;31m
NC     := \033[0m  # No Color

.PHONY: help
help:  ## Show this help message
	@echo "$(BLUE)R2R - Universal Development & Deployment Commands$(NC)"
	@echo ""
	@echo "$(GREEN)Quick Start:$(NC)"
	@echo "  make run          Deploy R2R to Google Cloud (production)"
	@echo "  make dev          Start R2R locally with Docker"
	@echo "  make test         Run test suite"
	@echo ""
	@echo "$(GREEN)Available Commands:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(BLUE)%-18s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(YELLOW)For GCP-specific commands:$(NC)"
	@echo "  cd deployment/gcp && make help"

## === Quick Commands ===

.PHONY: run
run:  ## Deploy to GCP (alias for gcp-deploy-full)
	@echo "$(GREEN)🚀 Deploying R2R to Google Cloud Platform...$(NC)"
	@cd deployment/gcp && make deploy-full

.PHONY: dev
dev:  ## Start R2R locally (light mode)
	@echo "$(GREEN)🔧 Starting R2R in development mode...$(NC)"
	@cd docker && docker compose -f compose.full.yaml up -d postgres minio unstructured graph_clustering
	@echo "$(YELLOW)⏳ Waiting for services to start...$(NC)"
	@sleep 10
	@cd docker && docker compose -f compose.full.yaml up -d r2r r2r-dashboard
	@echo ""
	@echo "$(GREEN)✅ R2R is starting!$(NC)"
	@echo "  API:       http://localhost:7272"
	@echo "  Dashboard: http://localhost:7273"
	@echo ""
	@echo "Check logs: $(BLUE)make logs$(NC)"

.PHONY: stop
stop:  ## Stop local R2R services
	@echo "$(YELLOW)🛑 Stopping R2R services...$(NC)"
	@cd docker && docker compose -f compose.full.yaml down
	@echo "$(GREEN)✅ Services stopped$(NC)"

.PHONY: restart
restart: stop dev  ## Restart local R2R

.PHONY: clean
clean:  ## Stop and remove all volumes (clean state)
	@echo "$(RED)🗑️  Stopping and cleaning all volumes...$(NC)"
	@cd docker && docker compose -f compose.full.yaml down -v
	@echo "$(GREEN)✅ Clean complete$(NC)"

## === GCP Deployment (Delegated to deployment/gcp/Makefile) ===

.PHONY: gcp-deploy-full
gcp-deploy-full:  ## Full GCP deployment from scratch
	@cd deployment/gcp && make deploy-full

.PHONY: gcp-status
gcp-status:  ## Check GCP deployment status
	@cd deployment/gcp && make status

.PHONY: gcp-health
gcp-health:  ## Check GCP service health
	@cd deployment/gcp && make health-all

.PHONY: gcp-logs
gcp-logs:  ## View GCP R2R logs
	@cd deployment/gcp && make logs

.PHONY: gcp-ssh
gcp-ssh:  ## SSH to GCP VM
	@cd deployment/gcp && make vm-ssh

.PHONY: gcp-restart
gcp-restart:  ## Restart R2R on GCP
	@cd deployment/gcp && make r2r-restart

.PHONY: gcp-stop
gcp-stop:  ## Stop GCP VM
	@cd deployment/gcp && make vm-stop

.PHONY: gcp-start
gcp-start:  ## Start GCP VM
	@cd deployment/gcp && make vm-start

.PHONY: gcp-destroy
gcp-destroy:  ## Destroy all GCP resources
	@cd deployment/gcp && make destroy-all

## === Development ===

.PHONY: logs
logs:  ## Show R2R logs (local)
	@cd docker && docker compose -f compose.full.yaml logs --tail=50 -f r2r

.PHONY: logs-all
logs-all:  ## Show all service logs (local)
	@cd docker && docker compose -f compose.full.yaml logs --tail=30

.PHONY: status
status:  ## Show service status (local)
	@cd docker && docker compose -f compose.full.yaml ps

.PHONY: health
health:  ## Check R2R health (local)
	@curl -s http://localhost:7272/v3/health | jq . || echo "$(RED)❌ R2R not responding$(NC)"

.PHONY: shell
shell:  ## Open shell in R2R container (local)
	@cd docker && docker compose -f compose.full.yaml exec r2r bash

## === Testing & Quality ===

.PHONY: test
test:  ## Run test suite
	@echo "$(BLUE)🧪 Running tests...$(NC)"
	@cd py && pytest tests/

.PHONY: test-unit
test-unit:  ## Run unit tests only
	@cd py && pytest tests/unit/

.PHONY: test-integration
test-integration:  ## Run integration tests
	@cd py && pytest tests/integration/

.PHONY: lint
lint:  ## Run linters (ruff)
	@echo "$(BLUE)🔍 Running linters...$(NC)"
	@cd py && ruff check .

.PHONY: format
format:  ## Format code (ruff)
	@echo "$(BLUE)✨ Formatting code...$(NC)"
	@cd py && ruff format .

.PHONY: type-check
type-check:  ## Run type checking (mypy)
	@echo "$(BLUE)🔬 Type checking...$(NC)"
	@cd py && mypy .

.PHONY: quality
quality: lint type-check  ## Run all quality checks

## === Docker ===

.PHONY: build
build:  ## Build R2R Docker image
	@echo "$(BLUE)🏗️  Building R2R Docker image...$(NC)"
	@docker build -f py/Dockerfile -t r2r:local py/
	@echo "$(GREEN)✅ Build complete: r2r:local$(NC)"

.PHONY: pull
pull:  ## Pull latest R2R images
	@echo "$(BLUE)📥 Pulling latest images...$(NC)"
	@cd docker && docker compose -f compose.full.yaml pull

## === Database ===

.PHONY: db-shell
db-shell:  ## Open PostgreSQL shell
	@cd docker && docker compose -f compose.full.yaml exec postgres psql -U postgres

.PHONY: db-reset
db-reset:  ## Reset R2R database
	@echo "$(RED)⚠️  Resetting R2R database...$(NC)"
	@cd docker && docker compose -f compose.full.yaml exec postgres psql -U postgres -c "DROP DATABASE IF EXISTS r2r; CREATE DATABASE r2r;"
	@cd docker && docker compose -f compose.full.yaml exec postgres psql -U postgres -d r2r -c "CREATE EXTENSION IF NOT EXISTS vector;"
	@echo "$(GREEN)✅ Database reset complete$(NC)"

## === Info ===

.PHONY: info
info:  ## Show system information
	@echo "$(BLUE)R2R Environment Information$(NC)"
	@echo ""
	@echo "$(GREEN)Docker:$(NC)"
	@docker --version
	@docker compose version
	@echo ""
	@echo "$(GREEN)Python:$(NC)"
	@python3 --version || echo "Python not found"
	@echo ""
	@echo "$(GREEN)GCloud CLI:$(NC)"
	@gcloud --version 2>/dev/null || echo "gcloud not installed"
	@echo ""
	@echo "$(GREEN)Current Project:$(NC)"
	@gcloud config get-value project 2>/dev/null || echo "No project configured"

.PHONY: version
version:  ## Show R2R version
	@echo "R2R Version: $(shell cd py && python -c 'import core; print(getattr(core, \"__version__\", \"unknown\"))' 2>/dev/null || echo 'unknown')"

## === Quickstart Guides ===

.PHONY: quickstart-local
quickstart-local:  ## Quick start guide for local development
	@echo "$(BLUE)📘 R2R Local Development Quickstart$(NC)"
	@echo ""
	@echo "$(GREEN)1. Start services:$(NC)"
	@echo "   make dev"
	@echo ""
	@echo "$(GREEN)2. Check health:$(NC)"
	@echo "   make health"
	@echo ""
	@echo "$(GREEN)3. View logs:$(NC)"
	@echo "   make logs"
	@echo ""
	@echo "$(GREEN)4. Stop services:$(NC)"
	@echo "   make stop"
	@echo ""
	@echo "$(YELLOW)Documentation:$(NC) See docker/README.md"

.PHONY: quickstart-gcp
quickstart-gcp:  ## Quick start guide for GCP deployment
	@echo "$(BLUE)📘 R2R GCP Deployment Quickstart$(NC)"
	@echo ""
	@echo "$(GREEN)1. Configure GCP project:$(NC)"
	@echo "   Edit deployment/gcp/Makefile - set PROJECT_ID"
	@echo ""
	@echo "$(GREEN)2. Deploy everything:$(NC)"
	@echo "   make run"
	@echo ""
	@echo "$(GREEN)3. Check status:$(NC)"
	@echo "   make gcp-status"
	@echo "   make gcp-health"
	@echo ""
	@echo "$(GREEN)4. View logs:$(NC)"
	@echo "   make gcp-logs"
	@echo ""
	@echo "$(YELLOW)Documentation:$(NC) See deployment/gcp/QUICKSTART.md"

## === Aliases ===

.PHONY: up
up: dev  ## Alias for 'make dev'

.PHONY: down
down: stop  ## Alias for 'make stop'

.PHONY: deploy
deploy: gcp-deploy-full  ## Alias for 'make gcp-deploy-full'

.PHONY: ps
ps: status  ## Alias for 'make status'
