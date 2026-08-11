#!/usr/bin/env python3
"""
همگام‌سازی کلیدهای یکپارچه‌سازی (Alocom / SMS / …) از .env لوکال به هاست.

- فایل کامل .env لوکال آپلود نمی‌شود (DEBUG، DB لوکال، PAYMENT_TEST_BYPASS، …).
- فقط کلیدهای لیست‌شده upsert می‌شوند تا docker-compose.prod.yml (env_file) و
  مسیرهای docker run --env-file همان مقادیر را ببینند.

استفادهٔ مستقل:
  set ANISTITO_SSH_PASSWORD=...
  python scripts/integration_env_sync.py
"""
from __future__ import annotations

import argparse
import io
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# کلیدهایی که باید از لوکال به .env سرور بروند (بدون DATABASE_*/DEBUG/SECRET لوکال)
INTEGRATION_ENV_KEYS: tuple[str, ...] = (
    # Alocom
    "ALOCOM_ENABLED",
    "ALOCOM_API_BASE",
    "ALOCOM_USERNAME",
    "ALOCOM_PASSWORD",
    "ALOCOM_DEFAULT_AGENT_SERVICE_ID",
    "ALOCOM_PATH_LOGIN",
    "ALOCOM_PATH_CREATE_EVENT",
    "ALOCOM_PATH_REGISTER_IN_EVENT",
    "ALOCOM_PATH_CREATE_USER",
    "ALOCOM_FALLBACK_TO_UI_HINTS",
    "INTERVIEW_ONLINE_LINK_VISIBLE_MINUTES_BEFORE",
    # SMS (ملی‌پیامک)
    "SMS_PROVIDER",
    "SMS_USERNAME",
    "SMS_PASSWORD",
    "SMS_API_KEY",
    "SMS_LINE_NUMBER",
    "SMS_OTP_PATTERN_BODY_ID",
    "SMS_PATTERN_BODY_ID",
    "SMS_SIMULATION_UI",
    "SMS_SIMULATION_MIRROR_REAL_SEND",
    "SMS_SIMULATION_POPUP_SHOW_ALL",
)


def parse_dotenv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if not key:
            continue
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        out[key] = val
    return out


def extract_integration_env(src: Path | None = None) -> dict[str, str]:
    data = parse_dotenv(src or (ROOT / ".env"))
    return {k: data[k] for k in INTEGRATION_ENV_KEYS if k in data and data[k] != ""}


def merge_dotenv_content(existing: str, updates: dict[str, str]) -> str:
    """Upsert KEY=value lines; preserve unrelated keys and comments."""
    if not updates:
        return existing
    lines = existing.splitlines()
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                out.append(f"{key}={updates[key]}")
                seen.add(key)
                continue
        out.append(line)
    missing = [k for k in INTEGRATION_ENV_KEYS if k in updates and k not in seen]
    if missing:
        if out and out[-1].strip():
            out.append("")
        out.append("# --- synced integration (Alocom / SMS) ---")
        for k in missing:
            out.append(f"{k}={updates[k]}")
    return "\n".join(out) + ("\n" if out else "")


def write_fragment(path: Path, updates: dict[str, str] | None = None) -> Path:
    vals = updates if updates is not None else extract_integration_env()
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(f"{k}={vals[k]}\n" for k in INTEGRATION_ENV_KEYS if k in vals)
    path.write_text(body, encoding="utf-8", newline="\n")
    return path


def upsert_remote_dotenv(
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    remote_dir: str,
    updates: dict[str, str] | None = None,
) -> list[str]:
    """Merge integration keys into remote_dir/.env via SFTP. Returns keys written."""
    import paramiko  # noqa: PLC0415

    vals = updates if updates is not None else extract_integration_env()
    if not vals:
        return []

    remote_env = f"{remote_dir.rstrip('/')}/.env"
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(host, port=port, username=user, password=password, timeout=60)
    try:
        sftp = c.open_sftp()
        try:
            try:
                with sftp.open(remote_env, "r") as rf:
                    existing = rf.read().decode("utf-8", errors="replace")
            except OSError:
                existing = ""
            merged = merge_dotenv_content(existing, vals)
            with sftp.open(remote_env, "w") as wf:
                wf.write(merged.encode("utf-8"))
            # fragment for docker run --env-file (optional consumers)
            frag = f"/tmp/anistito-integration.env"
            with sftp.open(frag, "w") as wf:
                body = "".join(f"{k}={vals[k]}\n" for k in INTEGRATION_ENV_KEYS if k in vals)
                wf.write(body.encode("utf-8"))
        finally:
            sftp.close()
    finally:
        c.close()
    return sorted(vals.keys())


def main() -> int:
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="Sync Alocom/SMS env keys to host .env")
    ap.add_argument("--fragment-only", metavar="PATH", help="فقط نوشتن فایل fragment لوکال")
    ap.add_argument("--print-keys", action="store_true", help="فقط نام کلیدهای موجود در لوکال")
    ap.add_argument(
        "--recreate-api",
        action="store_true",
        help="بعد از sync، API را با compose.prod recreate کن تا env_file بارگذاری شود",
    )
    args = ap.parse_args()

    vals = extract_integration_env()
    if args.print_keys:
        print(",".join(sorted(vals.keys())) or "(none)")
        return 0
    if args.fragment_only:
        write_fragment(Path(args.fragment_only), vals)
        print(f"Wrote {len(vals)} keys -> {args.fragment_only}")
        return 0

    pw = os.environ.get("ANISTITO_SSH_PASSWORD") or os.environ.get("DEPLOY_SSH_PASSWORD")
    if not pw:
        local = parse_dotenv(ROOT / ".env")
        pw = local.get("DEPLOY_SSH_PASSWORD") or local.get("ANISTITO_SSH_PASSWORD")
    if not pw:
        print("Set ANISTITO_SSH_PASSWORD (or DEPLOY_SSH_PASSWORD).", file=sys.stderr)
        return 1

    host = os.environ.get("ANISTITO_HOST", "80.191.11.129")
    port = int(os.environ.get("ANISTITO_SSH_PORT", "9123"))
    user = os.environ.get("ANISTITO_SSH_USER", "root")
    remote_dir = os.environ.get("ANISTITO_REMOTE_DIR", "/opt/anistito")

    if not vals:
        print("No integration keys found in local .env", file=sys.stderr)
        return 2

    keys = upsert_remote_dotenv(
        host=host, port=port, user=user, password=pw, remote_dir=remote_dir, updates=vals
    )
    print(f"Synced {len(keys)} keys to {host}:{remote_dir}/.env")
    print("  " + ", ".join(keys))

    if args.recreate_api:
        import paramiko  # noqa: PLC0415

        cmd = f"""
set -e
cd {remote_dir}
grep -E '^(ALOCOM_|SMS_|INTERVIEW_ONLINE_)' .env > /tmp/anistito-integration.env || true
docker compose -f docker-compose.prod.yml up -d --force-recreate api
sleep 10
docker exec anistito-api printenv ALOCOM_ENABLED || true
curl -s -o /dev/null -w 'health:%{{http_code}}\\n' http://127.0.0.1:3000/health || true
"""
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(host, port=port, username=user, password=pw, timeout=60)
        _, stdout, stderr = c.exec_command(cmd, timeout=240)
        print((stdout.read() + stderr.read()).decode("utf-8", "replace"))
        c.close()
    else:
        print("Restart API so compose picks env_file, e.g.:")
        print(f"  python scripts/integration_env_sync.py --recreate-api")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
