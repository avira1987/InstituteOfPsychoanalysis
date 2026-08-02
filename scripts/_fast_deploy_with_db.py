#!/usr/bin/env python3
"""Fast deploy: zip code (deploy_internet_host) + pg_dump restore for user data."""
from __future__ import annotations

import io
import os
import subprocess
import sys
import time
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

HOST = "80.191.11.129"
PORT = 9123
USER = "root"
PASSWORD = os.environ.get("ANISTITO_SSH_PASSWORD", "Tpi@1405")
REMOTE_DIR = "/opt/anistito"
REMOTE_DUMP = "/tmp/anistito_local.dump"


def log(msg: str) -> None:
    print(msg, flush=True)


def pg_dump_local() -> Path:
    dump_path = ROOT / "anistito_local.dump"
    log("=== pg_dump local anistito-db ===")
    subprocess.run(
        [
            "docker", "exec", "anistito-db", "pg_dump",
            "-U", "anistito", "-Fc", "anistito", "-f", "/tmp/anistito_local.dump",
        ],
        check=True,
    )
    subprocess.run(
        ["docker", "cp", "anistito-db:/tmp/anistito_local.dump", str(dump_path)],
        check=True,
    )
    log(f"  dump {dump_path.stat().st_size // 1024} KB")
    return dump_path


def upload_dump(dump_path: Path) -> None:
    log("=== upload database dump ===")
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=60)
    sftp = c.open_sftp()
    sftp.put(str(dump_path), REMOTE_DUMP)
    sftp.close()
    c.close()
    log("  dump uploaded")


def restore_and_verify() -> int:
    log("=== restore DB + restart API ===")
    script = r"""
set -e
cd /opt/anistito
docker stop anistito-api 2>/dev/null || true
docker cp /tmp/anistito_local.dump anistito-db:/tmp/restore.dump
set +e
docker exec anistito-db pg_restore -U anistito -d anistito --clean --if-exists --no-owner --no-acl /tmp/restore.dump 2>&1
RV=$?
set -e
if [ "$RV" -gt 1 ]; then echo "pg_restore failed: $RV"; exit "$RV"; fi
if ! grep -q '^POSTGRES_PASSWORD=' .env 2>/dev/null; then
  PG_PW=$(docker exec anistito-db printenv POSTGRES_PASSWORD 2>/dev/null || echo anistito)
  echo "POSTGRES_PASSWORD=${PG_PW}" >> .env
fi
docker compose -f docker-compose.prod.yml up -d api
for i in 1 2 3 4 5 6 7 8 9 10 12 15; do
  h=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:3000/health 2>/dev/null || echo 000)
  echo "health_try_${i}=${h}"
  if [ "$h" = "200" ]; then break; fi
  sleep 3
done
docker exec anistito-db psql -U anistito -d anistito -t -c "SELECT count(*) FROM users;"
curl -s http://127.0.0.1:3000/health
systemctl reload apache2 2>/dev/null || true
echo DONE
"""
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=60)
    _, stdout, stderr = c.exec_command(script, timeout=300)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    c.close()
    log(out + err)
    return code


def main() -> int:
    os.environ["ANISTITO_SSH_PASSWORD"] = PASSWORD
    os.environ["ANISTITO_SKIP_APACHE_SECURITY"] = "1"
    dump = pg_dump_local()
    log("=== deploy code (zip, fast) ===")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "deploy_internet_host.py")])
    if r.returncode != 0:
        log(f"deploy_internet_host failed: {r.returncode}")
        return r.returncode
    upload_dump(dump)
    code = restore_and_verify()
    log("=== external check ===")
    time.sleep(2)
    try:
        import urllib.request
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        for u in (
            "https://lms.psychoanalysis.ir/anistito/health",
            "https://lms.psychoanalysis.ir/anistito/login",
        ):
            try:
                resp = urllib.request.urlopen(u, timeout=25, context=ctx)
                log(f"  {u} -> {resp.status}")
            except Exception as e:
                log(f"  {u} -> ERROR {e}")
    except Exception as e:
        log(f"  check skipped: {e}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
