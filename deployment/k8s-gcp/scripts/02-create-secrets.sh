#!/bin/bash
# ========================================
# Create Kubernetes Secrets for R2R on GKE
# ========================================
# This script creates all required Kubernetes secrets from .env.production
# ========================================

set -euo pipefail

# ========================================
# Configuration
# ========================================
NAMESPACE="r2r-system"
ENV_FILE="../../../.env.production"
CONFIG_FILE="../../../config.production.toml"
VERTEX_KEY_FILE="../../../vertex-ai-key.production.json"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Creating Kubernetes Secrets${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# ========================================
# Check if files exist
# ========================================
if [[ ! -f "${ENV_FILE}" ]]; then
  echo -e "${RED}Error: ${ENV_FILE} not found${NC}"
  echo -e "${YELLOW}Please ensure .env.production exists in the root directory${NC}"
  exit 1
fi

if [[ ! -f "${CONFIG_FILE}" ]]; then
  echo -e "${RED}Error: ${CONFIG_FILE} not found${NC}"
  echo -e "${YELLOW}Please ensure config.production.toml exists in the root directory${NC}"
  exit 1
fi

if [[ ! -f "${VERTEX_KEY_FILE}" ]]; then
  echo -e "${RED}Error: ${VERTEX_KEY_FILE} not found${NC}"
  echo -e "${YELLOW}Please ensure vertex-ai-key.production.json exists in the root directory${NC}"
  exit 1
fi

# ========================================
# Create namespace if not exists
# ========================================
echo -e "${GREEN}[1/4] Ensuring namespace ${NAMESPACE} exists...${NC}"
kubectl create namespace ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -

# ========================================
# Create r2r-secrets from .env.production
# ========================================
echo -e "${GREEN}[2/4] Creating r2r-secrets from .env.production...${NC}"

# Check if secret exists
if kubectl get secret r2r-secrets -n ${NAMESPACE} &>/dev/null; then
  echo -e "${YELLOW}Secret r2r-secrets already exists. Deleting and recreating...${NC}"
  kubectl delete secret r2r-secrets -n ${NAMESPACE}
fi

# Create secret from env file
kubectl create secret generic r2r-secrets \
  --from-env-file="${ENV_FILE}" \
  --namespace="${NAMESPACE}"

echo -e "${GREEN}✓ r2r-secrets created${NC}"

# ========================================
# Create r2r-config-toml ConfigMap
# ========================================
echo -e "${GREEN}[3/4] Creating r2r-config-toml ConfigMap...${NC}"

if kubectl get configmap r2r-config-toml -n ${NAMESPACE} &>/dev/null; then
  echo -e "${YELLOW}ConfigMap r2r-config-toml already exists. Deleting and recreating...${NC}"
  kubectl delete configmap r2r-config-toml -n ${NAMESPACE}
fi

kubectl create configmap r2r-config-toml \
  --from-file=r2r.toml="${CONFIG_FILE}" \
  --namespace="${NAMESPACE}"

echo -e "${GREEN}✓ r2r-config-toml created${NC}"

# ========================================
# Create vertex-ai-key Secret
# ========================================
echo -e "${GREEN}[4/4] Creating vertex-ai-key Secret...${NC}"

if kubectl get secret vertex-ai-key -n ${NAMESPACE} &>/dev/null; then
  echo -e "${YELLOW}Secret vertex-ai-key already exists. Deleting and recreating...${NC}"
  kubectl delete secret vertex-ai-key -n ${NAMESPACE}
fi

kubectl create secret generic vertex-ai-key \
  --from-file=key.json="${VERTEX_KEY_FILE}" \
  --namespace="${NAMESPACE}"

echo -e "${GREEN}✓ vertex-ai-key created${NC}"

# ========================================
# Verify secrets
# ========================================
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Verifying Secrets${NC}"
echo -e "${GREEN}========================================${NC}"

echo -e "${GREEN}Secrets in namespace ${NAMESPACE}:${NC}"
kubectl get secrets -n ${NAMESPACE}

echo ""
echo -e "${GREEN}ConfigMaps in namespace ${NAMESPACE}:${NC}"
kubectl get configmaps -n ${NAMESPACE}

# ========================================
# Summary
# ========================================
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Secrets Created Successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${GREEN}Next Step:${NC}"
echo -e "Deploy R2R to GKE:"
echo -e "   ${YELLOW}./scripts/03-deploy-to-gke.sh${NC}"
echo ""
