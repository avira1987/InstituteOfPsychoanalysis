#!/bin/sh
# Install/refresh host cron for daily snapshots (04:00 UTC).
# Safe to re-run. Does not take a backup itself — use backup_daily.sh for that.
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
BACKUP_SH="${SCRIPT_DIR}/backup_daily.sh"
CRON_FILE="/etc/cron.d/anistito-backup"
BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/anistito}"
LOG_FILE="${BACKUP_LOG:-/var/log/anistito-backup.log}"

if [ ! -f "$BACKUP_SH" ]; then
  echo "missing ${BACKUP_SH}" >&2
  exit 1
fi

# Deploy from Windows can leave CRLF which breaks the shebang
if command -v sed >/dev/null 2>&1; then
  sed -i 's/\r$//' "$BACKUP_SH" "$0" 2>/dev/null || true
fi
chmod 755 "$BACKUP_SH"

mkdir -p "$BACKUP_ROOT"
chmod 755 "$BACKUP_ROOT"
touch "$LOG_FILE"
chmod 644 "$LOG_FILE"

cat > "$CRON_FILE" <<EOF
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
# 04:00 UTC = 07:30 Iran — PostgreSQL + uploads → ${BACKUP_ROOT}/YYYY-MM-DD
0 4 * * * root ${BACKUP_SH} >> ${LOG_FILE} 2>&1
EOF
chmod 644 "$CRON_FILE"

echo "[install_backup_cron] wrote ${CRON_FILE}"
echo "[install_backup_cron] script ${BACKUP_SH}"
echo "[install_backup_cron] snapshots ${BACKUP_ROOT}/YYYY-MM-DD"
echo "[install_backup_cron] log ${LOG_FILE}"
