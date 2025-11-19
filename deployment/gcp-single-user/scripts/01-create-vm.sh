#!/bin/bash
# ========================================
# Create GCP VM for R2R Single-User Deployment
# ========================================
# Creates cost-optimized VM instance
# Supports: e2-micro (free), e2-small, e2-medium, e2-standard-2
# ========================================

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# ========================================
# Configuration
# ========================================
PROJECT_ID="${GCP_PROJECT_ID:-}"
INSTANCE_NAME="${INSTANCE_NAME:-r2r-single-user}"
ZONE="${INSTANCE_ZONE:-us-central1-a}"
MACHINE_TYPE="${INSTANCE_TYPE:-e2-medium}"
DISK_SIZE="${DISK_SIZE:-50}"
USE_PREEMPTIBLE="${USE_PREEMPTIBLE:-false}"
BOOT_DISK_TYPE="${BOOT_DISK_TYPE:-pd-standard}"

# Service account for Vertex AI
SERVICE_ACCOUNT_NAME="r2r-vertex-ai"
SERVICE_ACCOUNT_EMAIL=""

# ========================================
# Parse Arguments
# ========================================
while [[ $# -gt 0 ]]; do
  case $1 in
    --project)
      PROJECT_ID="$2"
      shift 2
      ;;
    --name)
      INSTANCE_NAME="$2"
      shift 2
      ;;
    --zone)
      ZONE="$2"
      shift 2
      ;;
    --machine-type)
      MACHINE_TYPE="$2"
      shift 2
      ;;
    --disk-size)
      DISK_SIZE="$2"
      shift 2
      ;;
    --preemptible)
      USE_PREEMPTIBLE="true"
      shift
      ;;
    --help)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --project ID          GCP project ID (required)"
      echo "  --name NAME           Instance name (default: r2r-single-user)"
      echo "  --zone ZONE           Zone (default: us-central1-a)"
      echo "  --machine-type TYPE   Machine type (default: e2-medium)"
      echo "                        Options: e2-micro (free), e2-small, e2-medium, e2-standard-2"
      echo "  --disk-size SIZE      Disk size in GB (default: 50)"
      echo "  --preemptible         Use preemptible instance (70% cheaper)"
      echo "  --help                Show this help"
      echo ""
      echo "Examples:"
      echo "  # Free tier (1GB RAM - limited)"
      echo "  $0 --project my-project --machine-type e2-micro"
      echo ""
      echo "  # Recommended for single user (4GB RAM)"
      echo "  $0 --project my-project --machine-type e2-medium --preemptible"
      echo ""
      echo "  # More power for heavy workloads (8GB RAM)"
      echo "  $0 --project my-project --machine-type e2-standard-2"
      exit 0
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      echo "Use --help for usage information"
      exit 1
      ;;
  esac
done

# ========================================
# Validation
# ========================================
if [[ -z "${PROJECT_ID}" ]]; then
  echo -e "${RED}Error: GCP project ID is required${NC}"
  echo "Use: $0 --project YOUR_PROJECT_ID"
  echo "Or set: export GCP_PROJECT_ID=YOUR_PROJECT_ID"
  exit 1
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}R2R Single-User VM Creation${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Project:       ${YELLOW}${PROJECT_ID}${NC}"
echo -e "Instance:      ${YELLOW}${INSTANCE_NAME}${NC}"
echo -e "Zone:          ${YELLOW}${ZONE}${NC}"
echo -e "Machine Type:  ${YELLOW}${MACHINE_TYPE}${NC}"
echo -e "Disk Size:     ${YELLOW}${DISK_SIZE}GB${NC}"
echo -e "Preemptible:   ${YELLOW}${USE_PREEMPTIBLE}${NC}"
echo ""

# Confirm
read -p "$(echo -e ${YELLOW}Continue with VM creation? [y/N]: ${NC})" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo -e "${RED}Cancelled${NC}"
  exit 1
fi

# Set project
gcloud config set project "${PROJECT_ID}"

# ========================================
# Create Service Account for Vertex AI
# ========================================
echo -e "${BLUE}[1/4] Creating service account for Vertex AI...${NC}"

SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

if gcloud iam service-accounts describe "${SERVICE_ACCOUNT_EMAIL}" &>/dev/null; then
  echo -e "${YELLOW}Service account already exists: ${SERVICE_ACCOUNT_EMAIL}${NC}"
else
  gcloud iam service-accounts create "${SERVICE_ACCOUNT_NAME}" \
    --display-name="R2R Vertex AI Service Account" \
    --description="Service account for R2R to access Vertex AI"

  echo -e "${GREEN}✓ Service account created${NC}"
fi

# Grant necessary roles
echo "Granting IAM roles..."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/aiplatform.user" \
  --condition=None

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SERVICE_ACCOUNT_EMAIL}" \
  --role="roles/storage.objectAdmin" \
  --condition=None

echo -e "${GREEN}✓ IAM roles granted${NC}"

# ========================================
# Create Firewall Rules
# ========================================
echo -e "${BLUE}[2/4] Creating firewall rules...${NC}"

# Allow HTTP/HTTPS
if ! gcloud compute firewall-rules describe r2r-allow-http &>/dev/null; then
  gcloud compute firewall-rules create r2r-allow-http \
    --allow=tcp:80,tcp:443,tcp:7272,tcp:3000 \
    --source-ranges=0.0.0.0/0 \
    --description="Allow HTTP/HTTPS traffic for R2R"
  echo -e "${GREEN}✓ HTTP/HTTPS firewall rule created${NC}"
else
  echo -e "${YELLOW}Firewall rule already exists${NC}"
fi

# ========================================
# Create VM Instance
# ========================================
echo -e "${BLUE}[3/4] Creating VM instance...${NC}"

# Build create command
CREATE_CMD="gcloud compute instances create ${INSTANCE_NAME} \
  --zone=${ZONE} \
  --machine-type=${MACHINE_TYPE} \
  --boot-disk-size=${DISK_SIZE}GB \
  --boot-disk-type=${BOOT_DISK_TYPE} \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --service-account=${SERVICE_ACCOUNT_EMAIL} \
  --scopes=https://www.googleapis.com/auth/cloud-platform \
  --tags=http-server,https-server"

# Add preemptible flag if requested
if [[ "${USE_PREEMPTIBLE}" == "true" ]]; then
  CREATE_CMD="${CREATE_CMD} --preemptible"
  echo -e "${YELLOW}Using preemptible instance (70% cost savings, 24h max runtime)${NC}"
fi

# Execute create command
eval "${CREATE_CMD}"

echo -e "${GREEN}✓ VM instance created${NC}"

# Wait for instance to be ready
echo "Waiting for instance to be ready..."
sleep 10

# ========================================
# Get Instance IP
# ========================================
echo -e "${BLUE}[4/4] Getting instance information...${NC}"

EXTERNAL_IP=$(gcloud compute instances describe "${INSTANCE_NAME}" \
  --zone="${ZONE}" \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo -e "${GREEN}✓ Instance ready${NC}"

# ========================================
# Summary
# ========================================
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}VM Created Successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Instance Name:    ${YELLOW}${INSTANCE_NAME}${NC}"
echo -e "External IP:      ${YELLOW}${EXTERNAL_IP}${NC}"
echo -e "Zone:             ${YELLOW}${ZONE}${NC}"
echo -e "Machine Type:     ${YELLOW}${MACHINE_TYPE}${NC}"
echo ""
echo -e "${GREEN}Estimated Monthly Cost:${NC}"
case "${MACHINE_TYPE}" in
  e2-micro)
    echo -e "  VM: ${YELLOW}$0 (free tier)${NC}"
    echo -e "  Disk (${DISK_SIZE}GB): ${YELLOW}~$$(echo \"${DISK_SIZE} * 0.04\" | bc) (first 30GB free)${NC}"
    ;;
  e2-small)
    if [[ "${USE_PREEMPTIBLE}" == "true" ]]; then
      echo -e "  VM: ${YELLOW}~\$4/month (preemptible)${NC}"
    else
      echo -e "  VM: ${YELLOW}~\$13/month${NC}"
    fi
    ;;
  e2-medium)
    if [[ "${USE_PREEMPTIBLE}" == "true" ]]; then
      echo -e "  VM: ${YELLOW}~\$8/month (preemptible)${NC}"
    else
      echo -e "  VM: ${YELLOW}~\$26/month${NC}"
    fi
    ;;
  e2-standard-2)
    if [[ "${USE_PREEMPTIBLE}" == "true" ]]; then
      echo -e "  VM: ${YELLOW}~\$15/month (preemptible)${NC}"
    else
      echo -e "  VM: ${YELLOW}~\$48/month${NC}"
    fi
    ;;
esac
echo ""

# ========================================
# Next Steps
# ========================================
echo -e "${GREEN}Next Steps:${NC}"
echo ""
echo -e "1. SSH to instance:"
echo -e "   ${BLUE}gcloud compute ssh ${INSTANCE_NAME} --zone=${ZONE}${NC}"
echo ""
echo -e "2. Or run installation script:"
echo -e "   ${BLUE}./02-install-docker.sh --instance=${INSTANCE_NAME} --zone=${ZONE}${NC}"
echo ""
echo -e "3. Set up DNS (optional):"
echo -e "   Point your domain to: ${YELLOW}${EXTERNAL_IP}${NC}"
echo ""

# Save instance info to file
cat > .vm-info <<EOF
PROJECT_ID=${PROJECT_ID}
INSTANCE_NAME=${INSTANCE_NAME}
ZONE=${ZONE}
EXTERNAL_IP=${EXTERNAL_IP}
MACHINE_TYPE=${MACHINE_TYPE}
SERVICE_ACCOUNT_EMAIL=${SERVICE_ACCOUNT_EMAIL}
EOF

echo -e "${YELLOW}Instance info saved to .vm-info${NC}"
echo ""
