#!/usr/bin/env python3
"""
کپی فایل‌های اصلاح‌شده از این مخزن به کانتینر anistito-api روی سرور اینترنتی و ریستارت.
استفاده:  set ANISTITO_SSH_PASSWORD=...  و سپس  python scripts/deploy_hotfix_to_internet_host.py
"""
import hashlib
import os
import sys

import paramiko

HOST = os.environ.get("ANISTITO_HOST", "80.191.11.129")
PORT = int(os.environ.get("ANISTITO_SSH_PORT", "9123"))
USER = os.environ.get("ANISTITO_SSH_USER", "root")
PASSWORD = os.environ.get("ANISTITO_SSH_PASSWORD")
CONTAINER = os.environ.get("ANISTITO_API_CONTAINER", "anistito-api")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = [
    ("app/meta/loader.py", "/app/app/meta/loader.py"),
    ("app/meta/student_step_forms.py", "/app/app/meta/student_step_forms.py"),
    ("app/api/admin/routes.py", "/app/app/api/admin/routes.py"),
]


def main() -> int:
    if not PASSWORD:
        print("خطا: متغیر محیطی ANISTITO_SSH_PASSWORD را تنظیم کنید.", file=sys.stderr)
        return 1

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=45)
    sftp = c.open_sftp()

    for rel, dest in FILES:
        local_path = os.path.join(ROOT, rel)
        with open(local_path, "rb") as f:
            data = f.read()
        h = hashlib.sha256(data).hexdigest()[:16]
        remote_tmp = "/tmp/hotfix_" + rel.replace("/", "_")
        sftp.putfo(__import__("io").BytesIO(data), remote_tmp)
        _, o, e = c.exec_command(f"docker cp {remote_tmp} {CONTAINER}:{dest}", timeout=90)
        err = (o.read() + e.read()).decode("utf-8", errors="replace")
        if err.strip():
            print(err.strip())
        print(f"  OK {rel} sha256[:16]={h} -> {CONTAINER}:{dest}")

    sftp.close()

    _, o, e = c.exec_command(f"docker restart {CONTAINER}", timeout=120)
    print((o.read() + e.read()).decode("utf-8", errors="replace").strip())
    c.close()

    c2 = paramiko.SSHClient()
    c2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c2.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=45)
    _, o, e = c2.exec_command(
        f"docker exec {CONTAINER} grep -c 'StateMachineEngine._as_mapping' /app/app/meta/loader.py",
        timeout=30,
    )
    n = (o.read() + e.read()).decode().strip()
    print(f"تأیید داخل کانتینر: loader.py دارای _as_mapping = {n}")
    c2.close()
    print("سرور اینترنتی به‌روز شد.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
