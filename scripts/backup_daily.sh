#!/bin/sh
# Daily backup: PostgreSQL (pg_dump -Fc) + uploads volume + manifest (sha256).
# Intended for host cron at 04:00 — not inside the API container.
#
# Usage:
#   ./scripts/backup_daily.sh
#   BACKUP_ROOT=/var/backups/anistito RETAIN_DAYS=14 ./scripts/backup_daily.sh
#
# Env:
#   BACKUP_ROOT       default /var/backups/anistito
#   RETAIN_DAYS       default 14
#   POSTGRES_USER     default anistito
#   POSTGRES_DB       default anistito
#   DB_CONTAINER      default anistito-db
#   UPLOADS_VOLUME    default: first docker volume matching *_uploads_data
set -eu

BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/anistito}"
RETAIN_DAYS="${RETAIN_DAYS:-14}"
DB_CONTAINER="${DB_CONTAINER:-anistito-db}"
POSTGRES_USER="${POSTGRES_USER:-anistito}"
POSTGRES_DB="${POSTGRES_DB:-anistito}"

DAY=$(date +%Y-%m-%d)
TAKEN_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
DAY_DIR="${BACKUP_ROOT}/${DAY}"
TMP_DIR="${DAY_DIR}.tmp.$$"

mkdir -p "$BACKUP_ROOT"
rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR"

cleanup_tmp() {
  rm -rf "$TMP_DIR"
}
trap cleanup_tmp EXIT

sha256_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    echo "neither sha256sum nor shasum found" >&2
    exit 1
  fi
}

resolve_uploads_volume() {
  if [ -n "${UPLOADS_VOLUME:-}" ]; then
    echo "$UPLOADS_VOLUME"
    return 0
  fi
  # Prefer compose project volume name if present
  if docker volume inspect anistito_uploads_data >/dev/null 2>&1; then
    echo "anistito_uploads_data"
    return 0
  fi
  FOUND=$(docker volume ls -q | grep -E '_uploads_data$' | head -n 1 || true)
  if [ -n "$FOUND" ]; then
    echo "$FOUND"
    return 0
  fi
  echo ""
}

echo "[backup_daily] start day=${DAY} root=${BACKUP_ROOT}"

# --- DB dump ---
DB_FILE="${TMP_DIR}/db.dump"
docker exec "$DB_CONTAINER" pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB" > "$DB_FILE"
DB_SIZE=$(wc -c < "$DB_FILE" | tr -d ' ')
DB_SHA=$(sha256_file "$DB_FILE")

PG_VERSION=""
PG_VERSION=$(docker exec "$DB_CONTAINER" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SHOW server_version;" 2>/dev/null | tr -d '[:space:]' || true)

# --- Uploads ---
UPLOADS_FILE="${TMP_DIR}/uploads.tar.gz"
VOL=$(resolve_uploads_volume)
UPLOADS_SIZE=0
UPLOADS_SHA=""
UPLOADS_NOTE=""
if [ -z "$VOL" ]; then
  echo "[backup_daily] WARN: no uploads volume found; writing empty archive" >&2
  EMPTY_DIR="${TMP_DIR}/empty_uploads"
  mkdir -p "$EMPTY_DIR"
  tar czf "$UPLOADS_FILE" -C "$EMPTY_DIR" .
  rmdir "$EMPTY_DIR"
  UPLOADS_NOTE="no_uploads_volume"
else
  echo "[backup_daily] uploads volume=${VOL}"
  docker run --rm \
    -v "${VOL}:/data:ro" \
    -v "${TMP_DIR}:/out" \
    alpine:3.20 \
    tar czf /out/uploads.tar.gz -C /data .
  UPLOADS_NOTE="volume:${VOL}"
fi
UPLOADS_SIZE=$(wc -c < "$UPLOADS_FILE" | tr -d ' ')
UPLOADS_SHA=$(sha256_file "$UPLOADS_FILE")

# --- Manifest ---
MANIFEST="${TMP_DIR}/manifest.json"
cat > "$MANIFEST" <<EOF
{
  "date": "${DAY}",
  "taken_at": "${TAKEN_AT}",
  "status": "ok",
  "postgres_version": "${PG_VERSION}",
  "db_container": "${DB_CONTAINER}",
  "postgres_db": "${POSTGRES_DB}",
  "uploads_note": "${UPLOADS_NOTE}",
  "files": {
    "db.dump": {
      "size_bytes": ${DB_SIZE},
      "sha256": "${DB_SHA}"
    },
    "uploads.tar.gz": {
      "size_bytes": ${UPLOADS_SIZE},
      "sha256": "${UPLOADS_SHA}"
    }
  }
}
EOF

# Atomic publish
rm -rf "$DAY_DIR"
mv "$TMP_DIR" "$DAY_DIR"
trap - EXIT

echo "[backup_daily] written ${DAY_DIR}"

# --- Retention ---
if [ "$RETAIN_DAYS" -gt 0 ] 2>/dev/null; then
  # Portable prune: delete YYYY-MM-DD dirs older than RETAIN_DAYS
  CUTOFF=$(date -u -d "-${RETAIN_DAYS} days" +%Y-%m-%d 2>/dev/null || date -u -v-"${RETAIN_DAYS}"d +%Y-%m-%d 2>/dev/null || true)
  if [ -n "$CUTOFF" ]; then
    for d in "${BACKUP_ROOT}"/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]; do
      [ -d "$d" ] || continue
      name=$(basename "$d")
      if [ "$name" \< "$CUTOFF" ]; then
        echo "[backup_daily] prune ${name} (older than ${CUTOFF})"
        rm -rf "$d"
      fi
    done
  else
    echo "[backup_daily] WARN: could not compute cutoff date; skip prune" >&2
  fi
fi

echo "[backup_daily] done"
