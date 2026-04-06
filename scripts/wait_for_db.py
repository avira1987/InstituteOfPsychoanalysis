#!/usr/bin/env python3
"""Wait until PostgreSQL accepts TCP connections (Docker Compose host, usually db:5432)."""

import os
import socket
import sys
import time

HOST = os.environ.get("DB_WAIT_HOST", "db")
PORT = int(os.environ.get("DB_WAIT_PORT", "5432"))
RETRIES = int(os.environ.get("DB_WAIT_RETRIES", "45"))
DELAY = float(os.environ.get("DB_WAIT_DELAY", "2"))


def main() -> None:
    for i in range(RETRIES):
        try:
            s = socket.create_connection((HOST, PORT), timeout=2)
            s.close()
            print(f"wait_for_db: {HOST}:{PORT} OK (attempt {i + 1})", flush=True)
            return
        except OSError as e:
            print(f"wait_for_db: {HOST}:{PORT} not ready ({e}), retry {i + 1}/{RETRIES}", flush=True)
            time.sleep(DELAY)
    print(f"wait_for_db: giving up on {HOST}:{PORT}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
