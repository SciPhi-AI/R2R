#!/bin/bash
# ========================================
# Deploy R2R using Docker Compose
# ========================================
set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
MODE="${1:-minimal}"  # minimal or full
ENABLE_DASHBOARD="${ENABLE_DASHBOARD:-false}"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}R2R Deployment${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Mode: ${YELLOW}${MODE}${NC}"
echo ""

# Check .env file
if [[ ! -f ".env.production" ]]; then
  echo -e "${RED}Error: .env.production not found${NC}"
  echo "Create it from template: cp .env.template .env.production"
  exit 1
fi

# Check vertex-ai-key.json
if [[ ! -f "vertex-ai-key.json" ]]; then
  echo -e "${YELLOW}Warning: vertex-ai-key.json not found${NC}"
  echo "Vertex AI will not work without this file"
  read -p "Continue anyway? [y/N]: " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
  fi
fi

# Load environment
set -a
source .env.production
set +a

# Select compose file
if [[ "${MODE}" == "full" ]]; then
  COMPOSE_FILE="docker-compose.full.yaml"
  echo "Using full mode with Hatchet orchestration"
else
  COMPOSE_FILE="docker-compose.yaml"
  echo "Using minimal mode (simple orchestration)"
fi

# Build profiles
PROFILES=""
if [[ "${ENABLE_DASHBOARD}" == "true" ]]; then
  PROFILES="--profile dashboard"
  echo "Dashboard enabled"
fi

# Pull images
echo ""
echo -e "${BLUE}Pulling Docker images...${NC}"
docker compose -f "${COMPOSE_FILE}" pull

# Stop existing containers
echo ""
echo -e "${BLUE}Stopping existing containers...${NC}"
docker compose -f "${COMPOSE_FILE}" ${PROFILES} down

# Start services
echo ""
echo -e "${BLUE}Starting R2R services...${NC}"
docker compose -f "${COMPOSE_FILE}" ${PROFILES} up -d

# Wait for services
echo ""
echo -e "${BLUE}Waiting for services to be ready...${NC}"
sleep 10

# Health check
echo ""
echo -e "${BLUE}Checking R2R health...${NC}"
if curl -sf http://localhost:7272/v3/health | jq . &>/dev/null; then
  echo -e "${GREEN}✓ R2R is healthy${NC}"
  curl -s http://localhost:7272/v3/health | jq .
else
  echo -e "${RED}Warning: R2R health check failed${NC}"
  echo "Check logs: docker compose -f ${COMPOSE_FILE} logs r2r"
fi

# Summary
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "R2R API:       ${YELLOW}http://localhost:7272${NC}"
if [[ "${ENABLE_DASHBOARD}" == "true" ]]; then
  echo -e "Dashboard:     ${YELLOW}http://localhost:3000${NC}"
fi
if [[ "${MODE}" == "full" ]]; then
  echo -e "Hatchet UI:    ${YELLOW}http://localhost:7274${NC}"
fi
echo ""
echo -e "${GREEN}Useful commands:${NC}"
echo -e "  View logs:    ${BLUE}docker compose -f ${COMPOSE_FILE} logs -f${NC}"
echo -e "  Stop:         ${BLUE}docker compose -f ${COMPOSE_FILE} down${NC}"
echo -e "  Restart:      ${BLUE}docker compose -f ${COMPOSE_FILE} restart r2r${NC}"
echo ""
