#!/bin/bash
# ========================================
# Monitor R2R Deployment on GKE
# ========================================
# This script provides monitoring and health check commands
# ========================================

set -euo pipefail

NAMESPACE="r2r-system"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ========================================
# Functions
# ========================================

show_status() {
  echo -e "${GREEN}========================================${NC}"
  echo -e "${GREEN}R2R GKE Deployment Status${NC}"
  echo -e "${GREEN}========================================${NC}"
  echo ""

  echo -e "${BLUE}Pods:${NC}"
  kubectl get pods -n ${NAMESPACE} -o wide
  echo ""

  echo -e "${BLUE}Services:${NC}"
  kubectl get svc -n ${NAMESPACE}
  echo ""

  echo -e "${BLUE}Ingress:${NC}"
  kubectl get ingress -n ${NAMESPACE}
  echo ""

  echo -e "${BLUE}HPA (Autoscaling):${NC}"
  kubectl get hpa -n ${NAMESPACE}
  echo ""
}

show_health() {
  echo -e "${GREEN}========================================${NC}"
  echo -e "${GREEN}R2R Health Checks${NC}"
  echo -e "${GREEN}========================================${NC}"
  echo ""

  # R2R API Health
  echo -e "${BLUE}R2R API Health:${NC}"
  kubectl exec -n ${NAMESPACE} deployment/r2r-api -- curl -s http://localhost:7272/v3/health | jq . || echo "Failed"
  echo ""

  # Hatchet API Health
  echo -e "${BLUE}Hatchet API Health:${NC}"
  kubectl exec -n ${NAMESPACE} deployment/hatchet-api -- curl -s http://localhost:8080/api/ready || echo "Failed"
  echo ""

  # Unstructured Health
  echo -e "${BLUE}Unstructured Service Health:${NC}"
  kubectl exec -n ${NAMESPACE} deployment/unstructured -- curl -s http://localhost:7275/health || echo "Failed"
  echo ""

  # Graph Clustering Health
  echo -e "${BLUE}Graph Clustering Service Health:${NC}"
  kubectl exec -n ${NAMESPACE} deployment/graph-clustering -- curl -s http://localhost:7276/health || echo "Failed"
  echo ""
}

show_logs() {
  local SERVICE="${1:-r2r-api}"
  echo -e "${GREEN}========================================${NC}"
  echo -e "${GREEN}Logs for ${SERVICE}${NC}"
  echo -e "${GREEN}========================================${NC}"
  kubectl logs -n ${NAMESPACE} deployment/${SERVICE} --tail=100 -f
}

show_events() {
  echo -e "${GREEN}========================================${NC}"
  echo -e "${GREEN}Recent Events${NC}"
  echo -e "${GREEN}========================================${NC}"
  kubectl get events -n ${NAMESPACE} --sort-by='.lastTimestamp' | tail -n 20
}

show_resources() {
  echo -e "${GREEN}========================================${NC}"
  echo -e "${GREEN}Resource Usage${NC}"
  echo -e "${GREEN}========================================${NC}"
  echo ""

  echo -e "${BLUE}Top Pods by CPU:${NC}"
  kubectl top pods -n ${NAMESPACE} --sort-by=cpu
  echo ""

  echo -e "${BLUE}Top Pods by Memory:${NC}"
  kubectl top pods -n ${NAMESPACE} --sort-by=memory
  echo ""
}

port_forward() {
  local SERVICE="${1:-r2r-api}"
  local PORT="${2:-7272}"

  echo -e "${GREEN}Port forwarding ${SERVICE} on port ${PORT}${NC}"
  echo -e "${YELLOW}Access at: http://localhost:${PORT}${NC}"
  echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
  kubectl port-forward -n ${NAMESPACE} svc/${SERVICE} ${PORT}:${PORT}
}

# ========================================
# Main Menu
# ========================================

show_menu() {
  echo -e "${GREEN}========================================${NC}"
  echo -e "${GREEN}R2R GKE Monitoring Tool${NC}"
  echo -e "${GREEN}========================================${NC}"
  echo ""
  echo -e "1) Show deployment status"
  echo -e "2) Show health checks"
  echo -e "3) Show logs (R2R API)"
  echo -e "4) Show logs (Hatchet)"
  echo -e "5) Show logs (Unstructured)"
  echo -e "6) Show recent events"
  echo -e "7) Show resource usage (CPU/Memory)"
  echo -e "8) Port-forward R2R API (7272)"
  echo -e "9) Port-forward Dashboard (3000)"
  echo -e "10) Port-forward Hatchet Dashboard (8080)"
  echo -e "q) Quit"
  echo ""
}

# ========================================
# Interactive Mode
# ========================================

if [[ $# -eq 0 ]]; then
  while true; do
    show_menu
    read -p "$(echo -e ${BLUE}Select option: ${NC})" choice
    case $choice in
      1) show_status ;;
      2) show_health ;;
      3) show_logs "r2r-api" ;;
      4) show_logs "hatchet-api" ;;
      5) show_logs "unstructured" ;;
      6) show_events ;;
      7) show_resources ;;
      8) port_forward "r2r-api" "7272" ;;
      9) port_forward "r2r-dashboard" "3000" ;;
      10) port_forward "hatchet-frontend" "8080" ;;
      q|Q) echo "Exiting..."; exit 0 ;;
      *) echo -e "${YELLOW}Invalid option${NC}" ;;
    esac
    echo ""
    read -p "Press Enter to continue..."
  done
else
  # Command line mode
  case "$1" in
    status) show_status ;;
    health) show_health ;;
    logs) show_logs "${2:-r2r-api}" ;;
    events) show_events ;;
    resources) show_resources ;;
    port-forward) port_forward "${2:-r2r-api}" "${3:-7272}" ;;
    *)
      echo "Usage: $0 [status|health|logs|events|resources|port-forward]"
      echo "  Or run without arguments for interactive mode"
      exit 1
      ;;
  esac
fi
