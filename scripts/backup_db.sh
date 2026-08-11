#!/bin/sh
# Thin wrapper kept for older docs/scripts — prefer backup_daily.sh.
# Usage: ./scripts/backup_db.sh [ignored_output_dir]
set -e
ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
exec "$ROOT/scripts/backup_daily.sh"
