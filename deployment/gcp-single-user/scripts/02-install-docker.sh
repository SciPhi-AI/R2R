#!/bin/bash
# ========================================
# Install Docker and Docker Compose on GCP VM
# ========================================
# Can be run locally on VM or remotely via gcloud
# ========================================

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ========================================
# Configuration
# ========================================
INSTANCE_NAME="${INSTANCE_NAME:-r2r-single-user}"
ZONE="${INSTANCE_ZONE:-us-central1-a}"
REMOTE_INSTALL="${REMOTE_INSTALL:-false}"

# ========================================
# Parse Arguments
# ========================================
while [[ $# -gt 0 ]]; do
  case $1 in
    --instance)
      INSTANCE_NAME="$2"
      REMOTE_INSTALL="true"
      shift 2
      ;;
    --zone)
      ZONE="$2"
      shift 2
      ;;
    --local)
      REMOTE_INSTALL="false"
      shift
      ;;
    --help)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --instance NAME   Install on remote instance (requires gcloud)"
      echo "  --zone ZONE       Zone of the instance (default: us-central1-a)"
      echo "  --local           Run installation locally on current VM"
      echo "  --help            Show this help"
      echo ""
      echo "Examples:"
      echo "  # Remote installation"
      echo "  $0 --instance r2r-single-user --zone us-central1-a"
      echo ""
      echo "  # Local installation (when already SSH'd into VM)"
      echo "  $0 --local"
      exit 0
      ;;
    *)
      echo -e "${YELLOW}Unknown option: $1${NC}"
      exit 1
      ;;
  esac
done

# ========================================
# Installation Script
# ========================================
INSTALL_SCRIPT='#!/bin/bash
set -euo pipefail

echo "========================================

"
echo "Installing Docker and Docker Compose"
echo "========================================"
echo ""

# Update system
echo "[1/6] Updating system packages..."
sudo apt-get update -qq

# Install prerequisites
echo "[2/6] Installing prerequisites..."
sudo apt-get install -y -qq \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    software-properties-common

# Add Docker GPG key
echo "[3/6] Adding Docker repository..."
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Update package index
sudo apt-get update -qq

# Install Docker
echo "[4/6] Installing Docker..."
sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add current user to docker group
echo "[5/6] Configuring Docker permissions..."
sudo usermod -aG docker $USER

# Enable Docker service
echo "[6/6] Enabling Docker service..."
sudo systemctl enable docker
sudo systemctl start docker

# Verify installation
echo ""
echo "✓ Docker installed successfully"
docker --version
docker compose version

# Create directories
echo ""
echo "Creating R2R directories..."
mkdir -p ~/r2r/{data,logs,backups}

echo ""
echo "========================================"
echo "Installation Complete!"
echo "========================================"
echo ""
echo "IMPORTANT: Log out and log back in for Docker permissions to take effect"
echo ""
echo "Next step: Run deployment script"
echo "  ./03-deploy.sh --mode minimal"
echo ""
'

# ========================================
# Execute Installation
# ========================================
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Docker Installation${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

if [[ "${REMOTE_INSTALL}" == "true" ]]; then
  echo -e "Installing on remote instance: ${YELLOW}${INSTANCE_NAME}${NC}"
  echo -e "Zone: ${YELLOW}${ZONE}${NC}"
  echo ""

  # Check if instance exists
  if ! gcloud compute instances describe "${INSTANCE_NAME}" --zone="${ZONE}" &>/dev/null; then
    echo -e "${YELLOW}Error: Instance ${INSTANCE_NAME} not found in zone ${ZONE}${NC}"
    exit 1
  fi

  # Run installation via SSH
  gcloud compute ssh "${INSTANCE_NAME}" --zone="${ZONE}" --command="${INSTALL_SCRIPT}"

else
  echo -e "Installing Docker locally..."
  echo ""

  # Run installation locally
  bash -c "${INSTALL_SCRIPT}"
fi

echo ""
echo -e "${GREEN}✓ Installation complete${NC}"
echo ""
