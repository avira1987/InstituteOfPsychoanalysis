#!/usr/bin/env python3
"""Upload anistito_export.json and run import on server."""
import subprocess
import sys
from pathlib import Path

PLINK = str(Path(__file__).resolve().parents[1] / "plink.exe")
PSCP = str(Path(__file__).resolve().parents[1] / "pscp.exe")
HOSTKEY = "SHA256:F459aXR14g147aSBxWlTypGEKisuxzYnrYl4kcDyPdA"
HOST = "root@80.191.11.129"
PORT = "2022"
PW = "parsbpms.com"
EXPORT = Path(__file__).resolve().parents[1] / "anistito_export.json"


def run_plink(cmd: str) -> tuple[str, int]:
    full = f'{PLINK} -batch -hostkey {HOSTKEY} -P {PORT} -pw {PW} {HOST} "{cmd}"'
    r = subprocess.run(full, shell=True, capture_output=True, text=True, timeout=120)
    return (r.stdout + r.stderr).strip(), r.returncode


def run_pscp(local: str, remote: str) -> tuple[str, int]:
    full = f'{PSCP} -batch -hostkey {HOSTKEY} -P {PORT} -pw {PW} "{local}" {HOST}:{remote}'
    r = subprocess.run(full, shell=True, capture_output=True, text=True, timeout=60)
    return (r.stdout + r.stderr).strip(), r.returncode


def main():
    if not EXPORT.exists():
        print("Run first: python scripts/export_from_pg.py")
        sys.exit(1)

    print("=== 1. Upload anistito_export.json ===")
    out, code = run_pscp(str(EXPORT), "/tmp/anistito_export.json")
    if code != 0:
        print(f"Upload failed: {out}")
        sys.exit(1)
    print("OK")

    print("\n=== 2. Import on server ===")
    cmd = "cd /opt/anistito && (test -f scripts/truncate_and_import.py || (test -f /tmp/anistito_export.json && docker run --rm --network anistito-net -v /opt/anistito:/app -v /tmp:/tmp -w /app -e DATABASE_URL=postgresql+asyncpg://anistito:anistito@anistito-db:5432/anistito python:3.12-slim sh -c 'pip install sqlalchemy asyncpg -q && python scripts/truncate_and_import.py /tmp/anistito_export.json'))"
    # Simpler: run server-import-data.sh if it exists
    cmd = "cd /opt/anistito && bash -c 'if [ -f /tmp/anistito_export.json ]; then docker run --rm --network anistito-net -v /opt/anistito:/app -v /tmp:/tmp -w /app -e DATABASE_URL=postgresql+asyncpg://anistito:anistito@anistito-db:5432/anistito python:3.12-slim sh -c \"pip install sqlalchemy asyncpg -q && python scripts/truncate_and_import.py /tmp/anistito_export.json\"; docker restart anistito-api 2>/dev/null || true; echo Done; else echo No export file; fi'"
    out, code = run_plink(cmd)
    print(out)
    if code != 0:
        print("Import may have issues, check output above")
    else:
        print("\nImport complete. API restarted.")


if __name__ == "__main__":
    main()
