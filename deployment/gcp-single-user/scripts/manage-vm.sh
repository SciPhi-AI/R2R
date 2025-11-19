#!/bin/bash
# ========================================
# Manage R2R VM Instance
# ========================================
set -euo pipefail

# Load VM info if exists
if [[ -f ".vm-info" ]]; then
  source .vm-info
fi

INSTANCE_NAME="${INSTANCE_NAME:-r2r-single-user}"
ZONE="${ZONE:-us-central1-a}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Functions
show_status() {
  echo -e "${BLUE}VM Status:${NC}"
  gcloud compute instances describe "${INSTANCE_NAME}" --zone="${ZONE}" \
    --format="table(name,status,machineType,networkInterfaces[0].accessConfigs[0].natIP:label=EXTERNAL_IP)"
}

start_vm() {
  echo -e "${BLUE}Starting VM...${NC}"
  gcloud compute instances start "${INSTANCE_NAME}" --zone="${ZONE}"
  echo -e "${GREEN}✓ VM started${NC}"
}

stop_vm() {
  echo -e "${BLUE}Stopping VM...${NC}"
  gcloud compute instances stop "${INSTANCE_NAME}" --zone="${ZONE}"
  echo -e "${GREEN}✓ VM stopped (cost savings active)${NC}"
}

ssh_vm() {
  gcloud compute ssh "${INSTANCE_NAME}" --zone="${ZONE}"
}

restart_vm() {
  echo -e "${BLUE}Restarting VM...${NC}"
  gcloud compute instances reset "${INSTANCE_NAME}" --zone="${ZONE}"
  echo -e "${GREEN}✓ VM restarted${NC}"
}

show_logs() {
  ssh_vm << 'EOF'
cd ~/r2r
docker compose logs -f r2r
EOF
}

# Main menu
case "${1:-menu}" in
  start)
    start_vm
    ;;
  stop)
    stop_vm
    ;;
  restart)
    restart_vm
    ;;
  status)
    show_status
    ;;
  ssh)
    ssh_vm
    ;;
  logs)
    show_logs
    ;;
  *)
    echo -e "${GREEN}R2R VM Management${NC}"
    echo ""
    echo "Usage: $0 {start|stop|restart|status|ssh|logs}"
    echo ""
    echo "Commands:"
    echo "  start   - Start VM"
    echo "  stop    - Stop VM (saves costs)"
    echo "  restart - Restart VM"
    echo "  status  - Show VM status"
    echo "  ssh     - SSH to VM"
    echo "  logs    - View R2R logs"
    ;;
esac
