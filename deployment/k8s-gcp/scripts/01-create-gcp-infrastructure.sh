#!/bin/bash
# ========================================
# R2R GKE Infrastructure Setup Script
# ========================================
# This script creates all required GCP infrastructure:
# - GKE cluster
# - Cloud SQL instance with pgvector
# - Cloud Storage buckets
# - Service accounts and IAM bindings
# ========================================

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# ========================================
# Configuration Variables
# ========================================
PROJECT_ID="${GCP_PROJECT_ID:-r2r-full-deployment}"
REGION="${GCP_REGION:-us-central1}"
ZONE="${GCP_ZONE:-us-central1-a}"
CLUSTER_NAME="${CLUSTER_NAME:-r2r-production}"
SQL_INSTANCE="${SQL_INSTANCE:-r2r-postgres}"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT:-r2r-workload}"

# ========================================
# Colors for output
# ========================================
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'  # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}R2R GKE Infrastructure Setup${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Project ID:     ${YELLOW}${PROJECT_ID}${NC}"
echo -e "Region:         ${YELLOW}${REGION}${NC}"
echo -e "Cluster:        ${YELLOW}${CLUSTER_NAME}${NC}"
echo -e "Cloud SQL:      ${YELLOW}${SQL_INSTANCE}${NC}"
echo ""

# ========================================
# 1. Set GCP Project
# ========================================
echo -e "${GREEN}[1/7] Setting GCP project...${NC}"
gcloud config set project "${PROJECT_ID}"

# ========================================
# 2. Enable Required APIs
# ========================================
echo -e "${GREEN}[2/7] Enabling required APIs...${NC}"
gcloud services enable \
  container.googleapis.com \
  sqladmin.googleapis.com \
  storage.googleapis.com \
  compute.googleapis.com \
  iam.googleapis.com \
  aiplatform.googleapis.com \
  servicenetworking.googleapis.com

# ========================================
# 3. Create GKE Cluster
# ========================================
echo -e "${GREEN}[3/7] Creating GKE cluster (this takes ~5-10 minutes)...${NC}"

if gcloud container clusters describe "${CLUSTER_NAME}" --region="${REGION}" &>/dev/null; then
  echo -e "${YELLOW}Cluster ${CLUSTER_NAME} already exists, skipping creation${NC}"
else
  gcloud container clusters create "${CLUSTER_NAME}" \
    --region="${REGION}" \
    --num-nodes=3 \
    --enable-autoscaling \
    --min-nodes=3 \
    --max-nodes=10 \
    --machine-type=n2-standard-4 \
    --disk-size=100 \
    --disk-type=pd-ssd \
    --enable-autorepair \
    --enable-autoupgrade \
    --enable-workload-identity \
    --workload-pool="${PROJECT_ID}.svc.id.goog" \
    --addons=HorizontalPodAutoscaling,HttpLoadBalancing,GcePersistentDiskCsiDriver \
    --logging=SYSTEM,WORKLOAD \
    --monitoring=SYSTEM

  echo -e "${GREEN}✓ GKE cluster created${NC}"
fi

# Get cluster credentials
gcloud container clusters get-credentials "${CLUSTER_NAME}" --region="${REGION}"

# ========================================
# 4. Create Cloud SQL Instance
# ========================================
echo -e "${GREEN}[4/7] Creating Cloud SQL instance (this takes ~10-15 minutes)...${NC}"

if gcloud sql instances describe "${SQL_INSTANCE}" &>/dev/null; then
  echo -e "${YELLOW}Cloud SQL instance ${SQL_INSTANCE} already exists, skipping creation${NC}"
else
  gcloud sql instances create "${SQL_INSTANCE}" \
    --database-version=POSTGRES_16 \
    --tier=db-n1-standard-2 \
    --region="${REGION}" \
    --network=default \
    --no-assign-ip \
    --availability-type=REGIONAL \
    --backup-start-time=03:00 \
    --maintenance-window-day=SUN \
    --maintenance-window-hour=3 \
    --database-flags=cloudsql.enable_pgvector=on

  echo -e "${GREEN}✓ Cloud SQL instance created${NC}"

  # Create databases
  echo -e "${GREEN}Creating databases...${NC}"
  gcloud sql databases create r2r --instance="${SQL_INSTANCE}"
  gcloud sql databases create hatchet --instance="${SQL_INSTANCE}"

  # Set root password
  echo -e "${YELLOW}Setting postgres user password...${NC}"
  echo "Please enter a password for the postgres user:"
  read -s POSTGRES_PASSWORD
  gcloud sql users set-password postgres \
    --instance="${SQL_INSTANCE}" \
    --password="${POSTGRES_PASSWORD}"

  echo -e "${GREEN}✓ Databases created and postgres password set${NC}"
fi

# Get Cloud SQL private IP
SQL_IP=$(gcloud sql instances describe "${SQL_INSTANCE}" --format='get(ipAddresses[0].ipAddress)')
echo -e "${GREEN}Cloud SQL Private IP: ${YELLOW}${SQL_IP}${NC}"
echo -e "${YELLOW}⚠️  Update this IP in deployment/k8s-gcp/overlays/production/kustomization.yaml${NC}"

# ========================================
# 5. Create Cloud Storage Buckets
# ========================================
echo -e "${GREEN}[5/7] Creating Cloud Storage buckets...${NC}"

for BUCKET in "r2r-documents-${PROJECT_ID}" "r2r-embeddings-${PROJECT_ID}" "r2r-graphs-${PROJECT_ID}"; do
  if gsutil ls -b "gs://${BUCKET}" &>/dev/null; then
    echo -e "${YELLOW}Bucket ${BUCKET} already exists, skipping${NC}"
  else
    gsutil mb -p "${PROJECT_ID}" -c STANDARD -l US "gs://${BUCKET}/"
    echo -e "${GREEN}✓ Created bucket: ${BUCKET}${NC}"
  fi
done

# ========================================
# 6. Create Service Account for Workload Identity
# ========================================
echo -e "${GREEN}[6/7] Creating service account for Workload Identity...${NC}"

SA_EMAIL="${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com"

if gcloud iam service-accounts describe "${SA_EMAIL}" &>/dev/null; then
  echo -e "${YELLOW}Service account ${SA_EMAIL} already exists, skipping creation${NC}"
else
  gcloud iam service-accounts create "${SERVICE_ACCOUNT}" \
    --display-name="R2R Workload Identity Service Account"
  echo -e "${GREEN}✓ Service account created${NC}"
fi

# Assign IAM roles
echo -e "${GREEN}Assigning IAM roles to service account...${NC}"
for ROLE in "roles/aiplatform.user" "roles/storage.objectAdmin" "roles/cloudsql.client"; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${ROLE}" \
    --condition=None
  echo -e "${GREEN}✓ Assigned ${ROLE}${NC}"
done

# Bind Workload Identity
echo -e "${GREEN}Binding Workload Identity...${NC}"
gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
  --role="roles/iam.workloadIdentityUser" \
  --member="serviceAccount:${PROJECT_ID}.svc.id.goog[r2r-system/r2r-ksa]"
echo -e "${GREEN}✓ Workload Identity binding complete${NC}"

# ========================================
# 7. Reserve Static IP for Load Balancer
# ========================================
echo -e "${GREEN}[7/7] Reserving static IP address for Load Balancer...${NC}"

if gcloud compute addresses describe r2r-production-ip --global &>/dev/null; then
  echo -e "${YELLOW}Static IP already exists${NC}"
else
  gcloud compute addresses create r2r-production-ip --global
  echo -e "${GREEN}✓ Static IP reserved${NC}"
fi

LB_IP=$(gcloud compute addresses describe r2r-production-ip --global --format="get(address)")
echo -e "${GREEN}Load Balancer IP: ${YELLOW}${LB_IP}${NC}"
echo -e "${YELLOW}⚠️  Point your DNS A record (r2r.yourdomain.com) to this IP${NC}"

# ========================================
# Summary
# ========================================
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Infrastructure Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${GREEN}Next Steps:${NC}"
echo -e "1. Update Cloud SQL IP in: ${YELLOW}deployment/k8s-gcp/overlays/production/kustomization.yaml${NC}"
echo -e "   Replace 'POSTGRES_HOST=10.x.x.x' with: ${YELLOW}${SQL_IP}${NC}"
echo ""
echo -e "2. Point DNS A record to Load Balancer IP: ${YELLOW}${LB_IP}${NC}"
echo ""
echo -e "3. Create Kubernetes secrets:"
echo -e "   ${YELLOW}./scripts/02-create-secrets.sh${NC}"
echo ""
echo -e "4. Deploy R2R to GKE:"
echo -e "   ${YELLOW}./scripts/03-deploy-to-gke.sh${NC}"
echo ""
