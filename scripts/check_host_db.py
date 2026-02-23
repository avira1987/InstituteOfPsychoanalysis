#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Connect to host and check internet DB content."""
import subprocess
import sys
from pathlib import Path

PLINK = str(Path(__file__).resolve().parents[1] / "plink.exe")
HOSTKEY = "SHA256:F459aXR14g147aSBxWlTypGEKisuxzYnrYl4kcDyPdA"
HOST = "root@80.191.11.129"
PORT = "2022"
PW = "parsbpms.com"


def run(cmd: str) -> tuple[str, int]:
    full = f'{PLINK} -batch -hostkey {HOSTKEY} -P {PORT} -pw {PW} {HOST} "{cmd}"'
    r = subprocess.run(full, shell=True, capture_output=True, text=True, timeout=60)
    return (r.stdout + r.stderr).strip(), r.returncode


def main():
    print("=== 1. SSH Connection Test ===\n")
    out, code = run("echo CONNECTION_OK")
    if code != 0:
        print(f"Connection error: {out}")
        sys.exit(1)
    print("Connection OK\n")

    print("=== 2. Internet DB Status ===\n")
    cmds = [
        "docker exec anistito-db psql -U anistito -d anistito -t -c 'SELECT COUNT(*) FROM rule_definitions'",
        "docker exec anistito-db psql -U anistito -d anistito -t -c 'SELECT COUNT(*) FROM process_definitions'",
        "docker exec anistito-db psql -U anistito -d anistito -t -c 'SELECT COUNT(*) FROM state_definitions'",
        "docker exec anistito-db psql -U anistito -d anistito -t -c 'SELECT COUNT(*) FROM transition_definitions'",
        "docker exec anistito-db psql -U anistito -d anistito -t -c 'SELECT COUNT(*) FROM users'",
        "docker exec anistito-db psql -U anistito -d anistito -t -c 'SELECT COUNT(*) FROM students'",
        "docker exec anistito-db psql -U anistito -d anistito -t -c 'SELECT COUNT(*) FROM process_instances'",
    ]
    tables = ["rule_definitions", "process_definitions", "state_definitions", "transition_definitions", "users", "students", "process_instances"]
    rows = []
    for tbl, cmd in zip(tables, cmds):
        out2, code2 = run(cmd)
        cnt = out2.strip().split("\n")[0].strip() if out2 else "0"
        rows.append((tbl, cnt))
    print(f"{'Table':<25} {'Count':>10}")
    print("-" * 38)
    for tbl, cnt in rows:
        print(f"{tbl:<25} {cnt:>10}")

    print("\n=== 3. What should be transferred? ===\n")
    counts = {r[0]: int(r[1]) if r[1].isdigit() else 0 for r in rows}
    local = {
        "rule_definitions": 82,
        "process_definitions": 32,
        "state_definitions": 258,
        "transition_definitions": 294,
    }
    for tbl, local_n in local.items():
        remote_n = counts.get(tbl, 0)
        diff = local_n - remote_n
        if diff > 0:
            print(f"  {tbl}: local {local_n}, server {remote_n} -> {diff} items to transfer")
        elif diff < 0:
            print(f"  {tbl}: local {local_n}, server {remote_n} -> server has more")
        else:
            print(f"  {tbl}: same ({local_n})")
    print("\nTo transfer: python scripts/export_from_pg.py then upload and server-import-data.sh")


if __name__ == "__main__":
    main()
