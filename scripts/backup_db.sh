#!/bin/sh
# Daily PostgreSQL backup for docker-compose.prod.yml
# Usage: ./scripts/backup_db.sh [output_dir]
set -e
OUT_DIR="${1:-./backups}"
mkdir -p "$OUT_DIR"
STAMP=$(date +%Y%m%d-%H%M%S)
FILE="$OUT_DIR/anistito-$STAMP.dump"
docker exec anistito-db pg_dump -U "${POSTGRES_USER:-anistito}" -Fc "${POSTGRES_DB:-anistito}" > "$FILE"
echo "Backup written: $FILE"
