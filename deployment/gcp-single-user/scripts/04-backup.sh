#!/bin/bash
# ========================================
# Backup R2R Data
# ========================================
set -euo pipefail

# Configuration
BACKUP_DIR="${BACKUP_DIR:-$HOME/r2r/backups}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"
GCS_BACKUP_BUCKET="${GCS_BACKUP_BUCKET:-}"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}R2R Backup${NC}"
echo -e "${BLUE}========================================${NC}"

# Create backup directory
mkdir -p "${BACKUP_DIR}"

# Backup PostgreSQL
echo "Backing up PostgreSQL database..."
docker exec r2r-postgres pg_dump -U postgres r2r | gzip > "${BACKUP_DIR}/postgres_${TIMESTAMP}.sql.gz"

# Backup volumes
echo "Backing up R2R data..."
docker run --rm \
  -v r2r-data:/data \
  -v "${BACKUP_DIR}:/backup" \
  ubuntu tar czf "/backup/r2r_data_${TIMESTAMP}.tar.gz" -C /data .

# Upload to GCS if configured
if [[ -n "${GCS_BACKUP_BUCKET}" ]]; then
  echo "Uploading to GCS..."
  gsutil -m cp "${BACKUP_DIR}/*_${TIMESTAMP}.*" "gs://${GCS_BACKUP_BUCKET}/backups/"
fi

# Clean old backups
echo "Cleaning old backups (>${RETENTION_DAYS} days)..."
find "${BACKUP_DIR}" -name "*.gz" -mtime +${RETENTION_DAYS} -delete

echo -e "${GREEN}✓ Backup complete${NC}"
echo "Backup location: ${BACKUP_DIR}"
