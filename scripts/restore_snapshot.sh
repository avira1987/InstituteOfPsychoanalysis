#!/bin/sh
# Restore a dated host snapshot into a NON-PRODUCTION database (default: anistito_test).
# Never point TARGET_DB at the live production database unless you intend a full disaster recovery.
#
# Usage:
#   ./scripts/restore_snapshot.sh 2026-08-10
#   TARGET_DB=anistito_staging ./scripts/restore_snapshot.sh 2026-08-10
#
# Env:
#   BACKUP_ROOT     default /var/backups/anistito
#   DB_CONTAINER    default anistito-db
#   POSTGRES_USER   default anistito
#   TARGET_DB       default anistito_test
#   RESTORE_UPLOADS 1 = also extract uploads.tar.gz into a temp dir (does NOT replace live volume)
set -eu

DAY="${1:-}"
if [ -z "$DAY" ]; then
  echo "Usage: $0 YYYY-MM-DD" >&2
  exit 2
fi
case "$DAY" in
  [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]) ;;
  *)
    echo "Invalid date: $DAY (expected YYYY-MM-DD)" >&2
    exit 2
    ;;
esac

BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/anistito}"
DB_CONTAINER="${DB_CONTAINER:-anistito-db}"
POSTGRES_USER="${POSTGRES_USER:-anistito}"
TARGET_DB="${TARGET_DB:-anistito_test}"
RESTORE_UPLOADS="${RESTORE_UPLOADS:-0}"
PROD_DB="${POSTGRES_DB:-anistito}"

DAY_DIR="${BACKUP_ROOT}/${DAY}"
DUMP="${DAY_DIR}/db.dump"
UPLOADS="${DAY_DIR}/uploads.tar.gz"

if [ ! -f "$DUMP" ]; then
  echo "Missing dump: $DUMP" >&2
  exit 1
fi

if [ "$TARGET_DB" = "$PROD_DB" ]; then
  echo "Refusing to restore onto production DB name '${PROD_DB}'." >&2
  echo "Set TARGET_DB to a test/staging database (e.g. anistito_test)." >&2
  exit 1
fi

echo "[restore_snapshot] date=${DAY} target_db=${TARGET_DB} container=${DB_CONTAINER}"

# Ensure target DB exists
EXISTS=$(docker exec "$DB_CONTAINER" psql -U "$POSTGRES_USER" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='${TARGET_DB}'" | tr -d '[:space:]')
if [ "$EXISTS" != "1" ]; then
  echo "[restore_snapshot] creating database ${TARGET_DB}"
  docker exec "$DB_CONTAINER" psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE \"${TARGET_DB}\";"
fi

echo "[restore_snapshot] pg_restore -> ${TARGET_DB}"
docker cp "$DUMP" "${DB_CONTAINER}:/tmp/restore-snapshot.dump"
set +e
docker exec "$DB_CONTAINER" pg_restore -U "$POSTGRES_USER" -d "$TARGET_DB" --clean --if-exists --no-owner --no-acl /tmp/restore-snapshot.dump
RV=$?
set -e
docker exec "$DB_CONTAINER" rm -f /tmp/restore-snapshot.dump
# pg_restore exit 1 = warnings; >1 = failure
if [ "$RV" -gt 1 ]; then
  echo "pg_restore failed: $RV" >&2
  exit "$RV"
fi

if [ "$RESTORE_UPLOADS" = "1" ] && [ -f "$UPLOADS" ]; then
  OUT="${BACKUP_ROOT}/_restore_uploads_${DAY}"
  rm -rf "$OUT"
  mkdir -p "$OUT"
  tar xzf "$UPLOADS" -C "$OUT"
  echo "[restore_snapshot] uploads extracted to ${OUT} (live volume untouched)"
fi

echo "[restore_snapshot] done. Next: point a test API at DATABASE_URL=.../${TARGET_DB} and run health checks."
echo "See docs/BACKUP_RESTORE_RUNBOOK_FA.md"
