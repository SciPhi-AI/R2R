#!/bin/bash
# ========================================
# Deploy R2R to Google Kubernetes Engine
# ========================================
# This script deploys R2R using Kustomize
# ========================================

set -euo pipefail

# ========================================
# Configuration
# ========================================
OVERLAY="${1:-production}"  # Default to production overlay
NAMESPACE="r2r-system"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deploying R2R to GKE${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Overlay:    ${YELLOW}${OVERLAY}${NC}"
echo -e "Namespace:  ${YELLOW}${NAMESPACE}${NC}"
echo ""

# ========================================
# Verify prerequisites
# ========================================
echo -e "${BLUE}[1/6] Verifying prerequisites...${NC}"

# Check if kubectl is configured
if ! kubectl cluster-info &>/dev/null; then
  echo -e "${RED}Error: kubectl is not configured${NC}"
  echo -e "${YELLOW}Run: gcloud container clusters get-credentials r2r-production --region=us-central1${NC}"
  exit 1
fi

# Check if kustomize is available
if ! command -v kustomize &>/dev/null; then
  echo -e "${YELLOW}kustomize not found, using kubectl kustomize instead${NC}"
  KUSTOMIZE_CMD="kubectl kustomize"
else
  KUSTOMIZE_CMD="kustomize build"
fi

echo -e "${GREEN}✓ Prerequisites verified${NC}"

# ========================================
# Build Kustomize manifests
# ========================================
echo -e "${BLUE}[2/6] Building Kustomize manifests...${NC}"

MANIFEST_DIR="../overlays/${OVERLAY}"

if [[ ! -d "${MANIFEST_DIR}" ]]; then
  echo -e "${RED}Error: Overlay directory ${MANIFEST_DIR} not found${NC}"
  exit 1
fi

# Build and save manifests
${KUSTOMIZE_CMD} "${MANIFEST_DIR}" > /tmp/r2r-gke-manifests.yaml

echo -e "${GREEN}✓ Manifests built and saved to /tmp/r2r-gke-manifests.yaml${NC}"

# ========================================
# Preview deployment
# ========================================
echo -e "${BLUE}[3/6] Preview of deployment:${NC}"
echo ""
${KUSTOMIZE_CMD} "${MANIFEST_DIR}" | kubectl apply --dry-run=client -f - | head -n 50
echo ""
echo -e "${YELLOW}... (showing first 50 lines, full manifest in /tmp/r2r-gke-manifests.yaml)${NC}"
echo ""

# Ask for confirmation
read -p "$(echo -e ${YELLOW}Do you want to proceed with deployment? [y/N]: ${NC})" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo -e "${RED}Deployment cancelled${NC}"
  exit 1
fi

# ========================================
# Apply deployment
# ========================================
echo -e "${BLUE}[4/6] Applying deployment to GKE...${NC}"

kubectl apply -k "${MANIFEST_DIR}"

echo -e "${GREEN}✓ Deployment applied${NC}"

# ========================================
# Wait for deployments to be ready
# ========================================
echo -e "${BLUE}[5/6] Waiting for deployments to be ready...${NC}"
echo -e "${YELLOW}This may take 5-10 minutes for all services to start${NC}"
echo ""

# Wait for namespace
kubectl wait --for=jsonpath='{.status.phase}'=Active namespace/${NAMESPACE} --timeout=60s

# Get all deployments
DEPLOYMENTS=$(kubectl get deployments -n ${NAMESPACE} -o name)

echo -e "${YELLOW}Waiting for deployments:${NC}"
for DEPLOYMENT in ${DEPLOYMENTS}; do
  DEPLOY_NAME=$(basename ${DEPLOYMENT})
  echo -e "  - ${DEPLOY_NAME}"
done
echo ""

# Wait for each deployment
for DEPLOYMENT in ${DEPLOYMENTS}; do
  DEPLOY_NAME=$(basename ${DEPLOYMENT})
  echo -e "${YELLOW}Waiting for ${DEPLOY_NAME}...${NC}"

  kubectl rollout status ${DEPLOYMENT} -n ${NAMESPACE} --timeout=600s || {
    echo -e "${RED}Warning: ${DEPLOY_NAME} did not become ready in time${NC}"
    echo -e "${YELLOW}Check logs: kubectl logs -n ${NAMESPACE} ${DEPLOYMENT} --tail=50${NC}"
  }
done

echo -e "${GREEN}✓ All deployments checked${NC}"

# ========================================
# Verify deployment
# ========================================
echo -e "${BLUE}[6/6] Verifying deployment...${NC}"
echo ""

echo -e "${GREEN}Pods:${NC}"
kubectl get pods -n ${NAMESPACE}
echo ""

echo -e "${GREEN}Services:${NC}"
kubectl get svc -n ${NAMESPACE}
echo ""

echo -e "${GREEN}Ingress:${NC}"
kubectl get ingress -n ${NAMESPACE}
echo ""

echo -e "${GREEN}HPA (Autoscaling):${NC}"
kubectl get hpa -n ${NAMESPACE}
echo ""

# ========================================
# Check R2R API health
# ========================================
echo -e "${BLUE}Checking R2R API health...${NC}"

# Port-forward to check health
kubectl port-forward -n ${NAMESPACE} svc/r2r-api 7272:7272 &>/dev/null &
PF_PID=$!
sleep 3

if curl -s http://localhost:7272/v3/health | jq . &>/dev/null; then
  echo -e "${GREEN}✓ R2R API is healthy${NC}"
  curl -s http://localhost:7272/v3/health | jq .
else
  echo -e "${RED}Warning: Could not reach R2R API health endpoint${NC}"
fi

# Cleanup port-forward
kill ${PF_PID} 2>/dev/null || true

# ========================================
# Summary and Next Steps
# ========================================
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Get Load Balancer IP
LB_IP=$(kubectl get ingress r2r-ingress -n ${NAMESPACE} -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "pending")

echo -e "${GREEN}Access Information:${NC}"
echo ""

if [[ "${LB_IP}" != "pending" ]]; then
  echo -e "Load Balancer IP: ${YELLOW}${LB_IP}${NC}"
  echo -e "R2R API:          ${YELLOW}http://${LB_IP}${NC}"
  echo -e "R2R Dashboard:    ${YELLOW}http://${LB_IP}${NC}"
  echo ""
  echo -e "${YELLOW}⚠️  Note: HTTPS will be available after DNS propagation and SSL cert provisioning${NC}"
else
  echo -e "${YELLOW}Load Balancer IP is still pending...${NC}"
  echo -e "Check status: ${BLUE}kubectl get ingress -n ${NAMESPACE} -w${NC}"
fi

echo ""
echo -e "${GREEN}Useful Commands:${NC}"
echo -e "  View logs:        ${BLUE}kubectl logs -n ${NAMESPACE} deployment/r2r-api -f${NC}"
echo -e "  Check pods:       ${BLUE}kubectl get pods -n ${NAMESPACE}${NC}"
echo -e "  Port-forward API: ${BLUE}kubectl port-forward -n ${NAMESPACE} svc/r2r-api 7272:7272${NC}"
echo -e "  Scale deployment: ${BLUE}kubectl scale -n ${NAMESPACE} deployment/r2r-api --replicas=5${NC}"
echo ""

echo -e "${GREEN}Next Steps:${NC}"
echo -e "1. Verify DNS is pointed to Load Balancer IP: ${YELLOW}${LB_IP}${NC}"
echo -e "2. Wait for SSL certificate provisioning (~15 minutes after DNS)"
echo -e "3. Test document ingestion with automatic extraction"
echo -e "4. Monitor with: ${BLUE}./scripts/04-monitor.sh${NC}"
echo ""
