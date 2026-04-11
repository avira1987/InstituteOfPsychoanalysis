#!/usr/bin/env python3
"""
دیپلوی پروژه از لوکال به هاست اینترنتی:
  - npm run build (admin-ui)
  - بستهٔ zip بدون node_modules و .git
  - آپلود SFTP به /tmp/deploy-anistito.zip
  - بیلد Docker با پروکسی SOCKS روی سرور (فقط برای apt/pip در مرحلهٔ build)
  - پس از موفقیت: قطع xray/v2ray تا سرویس با شبکهٔ عادی کار کند (قابل غیرفعال‌سازی)
  - docker compose -f docker-compose.prod.yml up -d --build api
  - تکمیل .env برای CORS و امنیت
  - اجرای اسکریپت هدرهای Apache (اختیاری)

متغیرهای محیطی:
  ANISTITO_SSH_PASSWORD (الزامی)
  ANISTITO_HOST (پیش‌فرض 80.191.11.129)
  ANISTITO_SSH_PORT (پیش‌فرض 9123)
  ANISTITO_SSH_USER (پیش‌فرض root)
  ANISTITO_REMOTE_DIR (پیش‌فرض /opt/anistito)
  ANISTITO_SKIP_NPM (1 = رد کردن npm build)
  ANISTITO_SKIP_APACHE_SECURITY (1 = رد کردن اسکریپت Apache)
  ANISTITO_STOP_PROXY_AFTER_DEPLOY (پیش‌فرض 1) — بعد از بیلد systemctl stop برای xray و v2ray؛ 0 = پروکسی را روشن نگه دار
  ANISTITO_DOCKER_BUILD_USE_PROXY (پیش‌فرض 0) — 1 = APT و PIP هر دو SOCKS (قدیمی؛ pip ممکن است SSL بدهد)
    پیش‌فرض: فقط APT از طریق SOCKS (برای deb.debian.org)، pip بدون پروکسی (PyPI مستقیم)
"""
from __future__ import annotations

import io
import os
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

EXCLUDE_DIR_NAMES = {".git", "node_modules", "__pycache__", ".pytest_cache", ".venv", "dist"}
EXCLUDE_SUFFIXES = (".pyc", ".pyo")


def _is_under_admin_ui_dist(path: Path) -> bool:
    """خروجی build فرانت — نباید به‌خاطر نام dist از zip حذف شود."""
    parts = path.parts
    for i, p in enumerate(parts):
        if p == "admin-ui" and i + 1 < len(parts) and parts[i + 1] == "dist":
            return True
    return False


def should_skip(path: Path, rel: str) -> bool:
    if _is_under_admin_ui_dist(path):
        return False
    parts = path.parts
    if any(p in EXCLUDE_DIR_NAMES for p in parts):
        return True
    if path.name in EXCLUDE_DIR_NAMES:
        return True
    if rel.endswith(EXCLUDE_SUFFIXES):
        return True
    return False


def add_tree(zf: zipfile.ZipFile, base: Path, arc_prefix: str = "") -> None:
    for root, dirs, files in os.walk(base):
        dirs[:] = [
            d
            for d in dirs
            if d not in EXCLUDE_DIR_NAMES or (Path(root).name == "admin-ui" and d == "dist")
        ]
        for name in files:
            if name.endswith(EXCLUDE_SUFFIXES):
                continue
            fp = Path(root) / name
            rel = fp.relative_to(base)
            if should_skip(fp, str(rel)):
                continue
            arc = (Path(arc_prefix) / rel).as_posix()
            zf.write(fp, arcname=arc)


def run_npm_build() -> None:
    if os.environ.get("ANISTITO_SKIP_NPM") == "1":
        print("Skip npm build (ANISTITO_SKIP_NPM=1)")
        return
    admin = REPO / "admin-ui"
    print("=== npm run build (admin-ui) ===")
    r = subprocess.run(
        ["npm", "run", "build"],
        cwd=admin,
        shell=sys.platform == "win32",
    )
    if r.returncode != 0:
        raise SystemExit("npm run build failed")


def make_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in (
            "app",
            "metadata",
            "alembic",
            "scripts",
            "docker",
            "admin-ui/dist",
            "admin-ui/src",
            "admin-ui/public",
        ):
            p = REPO / name
            if p.is_dir():
                add_tree(zf, p, name)
            elif p.exists():
                zf.write(p, arcname=name)

        for f in (
            "requirements.txt",
            "requirements-docker.txt",
            "Dockerfile",
            "alembic.ini",
            ".dockerignore",
            "docker-compose.prod.yml",
        ):
            fp = REPO / f
            if fp.is_file():
                zf.write(fp, arcname=f)

        for f in ("index.html", "package.json", "vite.config.js"):
            fp = REPO / "admin-ui" / f
            if fp.is_file():
                zf.write(fp, arcname=f"admin-ui/{f}")

    return buf.getvalue()


def main() -> int:
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    pw = os.environ.get("ANISTITO_SSH_PASSWORD")
    if not pw:
        print("خطا: ANISTITO_SSH_PASSWORD را تنظیم کنید.", file=sys.stderr)
        return 1

    host = os.environ.get("ANISTITO_HOST", "80.191.11.129")
    port = int(os.environ.get("ANISTITO_SSH_PORT", "9123"))
    user = os.environ.get("ANISTITO_SSH_USER", "root")
    remote_dir = os.environ.get("ANISTITO_REMOTE_DIR", "/opt/anistito")
    remote_zip = "/tmp/deploy-anistito.zip"

    run_npm_build()
    data = make_zip()
    print(f"=== zip package: {len(data) // 1024} KB ===")

    import paramiko  # noqa: PLC0415

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(host, port=port, username=user, password=pw, timeout=60)
    sftp = c.open_sftp()
    sftp.putfo(io.BytesIO(data), remote_zip)
    sftp.close()
    print(f"=== uploaded -> {host}:{remote_zip} ===")

    remote_script = r"""
set -e
cd REMOTE_DIR_PLACEHOLDER
unzip -o /tmp/deploy-anistito.zip -d .
find scripts -type f -name '*.sh' -exec sed -i 's/\\r$//' {} +
chmod +x scripts/apply_apache_security_headers.sh 2>/dev/null || true

# .env: CORS و DEBUG برای محصول
touch .env
sed -i 's/^DEBUG=.*/DEBUG=false/' .env 2>/dev/null || true
if ! grep -q '^DEBUG=' .env; then echo 'DEBUG=false' >> .env; fi
if ! grep -q '^CORS_ALLOW_ORIGINS=' .env; then
  echo 'CORS_ALLOW_ORIGINS=https://lms.psychoanalysis.ir,https://ims.psychoanalysis.ir,http://lms.psychoanalysis.ir,http://ims.psychoanalysis.ir' >> .env
fi

PROXY_AND_XRAY_BLOCK_PLACEHOLDER

export COMPOSE_DOCKER_CLI_BUILD=1
export DOCKER_BUILDKIT=1

if docker compose -f docker-compose.prod.yml up -d --build api; then
  BUILD_OK=1
else
  BUILD_OK=0
fi

if [ "$BUILD_OK" != "1" ]; then
  echo "docker build failed — fallback: docker cp به مسیرهای داخل ایمیج (/app/app، admin-ui/dist، …)"
  docker cp ./app/. anistito-api:/app/app/
  docker cp ./admin-ui/dist/. anistito-api:/app/admin-ui/dist/
  docker cp ./metadata/. anistito-api:/app/metadata/
  docker cp ./alembic/. anistito-api:/app/alembic/
  docker exec anistito-api alembic upgrade head || true
  docker restart anistito-api
fi

sleep 8
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  h=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:3000/health 2>/dev/null || echo 000)
  echo "health_try_${i}=${h}"
  if [ "$h" = "200" ]; then break; fi
  sleep 4
done

# پروکسی فقط برای مرحلهٔ build (نصب apt/pip داخل ایمیج) بود؛ کانتینر API از bridge عادی Docker استفاده می‌کند.
unset APT_PROXY PIP_PROXY
# STOP_PROXY_FLAG_REPLACE = 1 → قطع xray/v2ray | 0 → دست نزن
if [ "STOP_PROXY_FLAG_REPLACE" != "0" ]; then
  for svc in xray v2ray; do
    if systemctl is-active --quiet "${svc}" 2>/dev/null; then
      systemctl stop "${svc}" && echo "Stopped ${svc}.service (runtime بدون SOCKS؛ اینترنت عادی)"
    fi
  done
else
  echo "ANISTITO_STOP_PROXY_AFTER_DEPLOY=0 — xray/v2ray متوقف نشد"
fi
"""
    use_full_proxy = os.environ.get("ANISTITO_DOCKER_BUILD_USE_PROXY", "0") == "1"
    if use_full_proxy:
        proxy_block = """
export APT_PROXY=socks5h://127.0.0.1:10808
export PIP_PROXY=socks5h://127.0.0.1:10808
systemctl start xray 2>/dev/null || true
systemctl start v2ray 2>/dev/null || true
echo "=== Docker build: APT+PIP از طریق SOCKS (ANISTITO_DOCKER_BUILD_USE_PROXY=1) ==="
"""
    else:
        # apt داخل ایمیج به deb.debian.org معمولاً فقط با SOCKS؛ pip با SOCKS روی PyPI اغلب SSL می‌شکند
        proxy_block = """
export APT_PROXY=socks5h://127.0.0.1:10808
unset PIP_PROXY
export PIP_PROXY=
systemctl start xray 2>/dev/null || true
systemctl start v2ray 2>/dev/null || true
echo "=== Docker build: APT=SOCKS، pip بدون پروکسی (پیش‌فرض سالم برای PyPI) ==="
"""
    remote_script = remote_script.replace(
        "PROXY_AND_XRAY_BLOCK_PLACEHOLDER", proxy_block.strip()
    )
    remote_script = remote_script.replace("REMOTE_DIR_PLACEHOLDER", remote_dir)
    stop_flag = "0" if os.environ.get("ANISTITO_STOP_PROXY_AFTER_DEPLOY") == "0" else "1"
    remote_script = remote_script.replace("STOP_PROXY_FLAG_REPLACE", stop_flag)

    if os.environ.get("ANISTITO_SKIP_APACHE_SECURITY") != "1":
        remote_script += "\nbash scripts/apply_apache_security_headers.sh || true\n"
    else:
        remote_script += "\necho 'Skip Apache security (ANISTITO_SKIP_APACHE_SECURITY=1)'\n"

    _, stdout, stderr = c.exec_command(remote_script, timeout=600)
    out = (stdout.read() + stderr.read()).decode("utf-8", errors="replace")
    print(out)
    c.close()

    print("=== تست از این ماشین (در صورت دسترسی به اینترنت) ===")
    null_out = "nul" if sys.platform == "win32" else "/dev/null"
    for url in (
        "http://lms.psychoanalysis.ir/anistito/health",
        "https://lms.psychoanalysis.ir/anistito/health",
        "https://ims.psychoanalysis.ir/anistito/health",
    ):
        try:
            r = subprocess.run(
                ["curl", "-sS", "-o", null_out, "-w", "%{http_code}", "-k", "-L", "--max-time", "25", url],
                capture_output=True,
                text=True,
                timeout=35,
                shell=False,
            )
            print(f"  {url} -> HTTP {r.stdout.strip()} {r.stderr.strip()}")
        except FileNotFoundError:
            print("  (curl نصب نیست — تست را در مرورگر انجام دهید)")
            break
        except Exception as e:
            print(f"  {url} -> error: {e}")

    print("=== پایان ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
