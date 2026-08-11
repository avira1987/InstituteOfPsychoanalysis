"""کاتالوگ فقط‌خواندنی بکاپ‌های روزانه روی دیسک (BACKUP_DIR).

هر اسنپ‌شات یک پوشهٔ YYYY-MM-DD با db.dump، uploads.tar.gz و manifest.json است.
هیچ‌گاه pg_restore یا overwrite روی دیتابیس زنده انجام نمی‌دهد.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
FILE_KINDS = {
    "db": "db.dump",
    "uploads": "uploads.tar.gz",
}
KindName = Literal["db", "uploads"]


class BackupCatalogError(Exception):
    """خطای قابل‌نمایش به کلاینت برای کاتالوگ بکاپ."""

    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class BackupFileInfo:
    name: str
    size_bytes: int | None
    sha256: str | None
    present: bool


def resolve_backup_root(backup_dir: str | Path) -> Path:
    return Path(backup_dir).expanduser().resolve()


def parse_snapshot_date(date: str) -> str:
    d = (date or "").strip()
    if not DATE_RE.match(d):
        raise BackupCatalogError("تاریخ باید به صورت YYYY-MM-DD باشد", status_code=400)
    return d


def snapshot_dir(root: Path, date: str) -> Path:
    d = parse_snapshot_date(date)
    path = (root / d).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise BackupCatalogError("مسیر بکاپ نامعتبر است", status_code=400) from exc
    return path


def _sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _read_manifest(day_dir: Path) -> dict[str, Any] | None:
    mf = day_dir / "manifest.json"
    if not mf.is_file():
        return None
    try:
        data = json.loads(mf.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _file_entry(day_dir: Path, name: str, manifest: dict[str, Any] | None) -> BackupFileInfo:
    path = day_dir / name
    present = path.is_file()
    size: int | None = None
    sha: str | None = None
    files = (manifest or {}).get("files") if isinstance((manifest or {}).get("files"), dict) else {}
    meta = files.get(name) if isinstance(files, dict) else None
    if isinstance(meta, dict):
        raw_size = meta.get("size_bytes")
        if isinstance(raw_size, int):
            size = raw_size
        elif isinstance(raw_size, str) and raw_size.isdigit():
            size = int(raw_size)
        raw_sha = meta.get("sha256")
        if isinstance(raw_sha, str) and raw_sha.strip():
            sha = raw_sha.strip().lower()
    if present and size is None:
        try:
            size = path.stat().st_size
        except OSError:
            size = None
    return BackupFileInfo(name=name, size_bytes=size, sha256=sha, present=present)


def summarize_day(day_dir: Path) -> dict[str, Any] | None:
    if not day_dir.is_dir():
        return None
    date = day_dir.name
    if not DATE_RE.match(date):
        return None
    manifest = _read_manifest(day_dir)
    db = _file_entry(day_dir, "db.dump", manifest)
    uploads = _file_entry(day_dir, "uploads.tar.gz", manifest)
    total = 0
    for f in (db, uploads):
        if f.present and isinstance(f.size_bytes, int):
            total += f.size_bytes
    status = "ok"
    if isinstance(manifest, dict) and isinstance(manifest.get("status"), str):
        status = str(manifest.get("status") or "ok")
    if not db.present:
        status = "incomplete"
    taken_at = None
    if isinstance(manifest, dict):
        raw = manifest.get("taken_at")
        if isinstance(raw, str):
            taken_at = raw
    return {
        "date": date,
        "taken_at": taken_at,
        "status": status,
        "has_manifest": manifest is not None,
        "total_size_bytes": total,
        "postgres_version": (manifest or {}).get("postgres_version") if manifest else None,
        "files": {
            "db.dump": {
                "present": db.present,
                "size_bytes": db.size_bytes,
                "sha256": db.sha256,
            },
            "uploads.tar.gz": {
                "present": uploads.present,
                "size_bytes": uploads.size_bytes,
                "sha256": uploads.sha256,
            },
        },
    }


def list_snapshots(backup_dir: str | Path) -> list[dict[str, Any]]:
    root = resolve_backup_root(backup_dir)
    if not root.is_dir():
        return []
    items: list[dict[str, Any]] = []
    for child in sorted(root.iterdir(), reverse=True):
        summary = summarize_day(child)
        if summary:
            items.append(summary)
    return items


def get_snapshot(backup_dir: str | Path, date: str) -> dict[str, Any]:
    root = resolve_backup_root(backup_dir)
    day = snapshot_dir(root, date)
    if not day.is_dir():
        raise BackupCatalogError(f"بکاپ تاریخ {date} یافت نشد", status_code=404)
    summary = summarize_day(day)
    if not summary:
        raise BackupCatalogError(f"بکاپ تاریخ {date} نامعتبر است", status_code=404)
    return summary


def verify_snapshot(backup_dir: str | Path, date: str) -> dict[str, Any]:
    root = resolve_backup_root(backup_dir)
    day = snapshot_dir(root, date)
    if not day.is_dir():
        raise BackupCatalogError(f"بکاپ تاریخ {date} یافت نشد", status_code=404)
    summary = summarize_day(day) or {"date": date, "status": "missing"}
    manifest = _read_manifest(day)
    checks: list[dict[str, Any]] = []
    ok = True
    for name in ("db.dump", "uploads.tar.gz"):
        path = day / name
        entry = _file_entry(day, name, manifest)
        item: dict[str, Any] = {
            "name": name,
            "present": entry.present,
            "expected_sha256": entry.sha256,
            "actual_sha256": None,
            "size_bytes": None,
            "match": False,
        }
        if not entry.present:
            ok = False
            checks.append(item)
            continue
        try:
            actual_size = path.stat().st_size
            actual_sha = _sha256_file(path)
        except OSError:
            ok = False
            checks.append(item)
            continue
        item["size_bytes"] = actual_size
        item["actual_sha256"] = actual_sha
        if entry.sha256:
            item["match"] = actual_sha.lower() == entry.sha256.lower()
            if not item["match"]:
                ok = False
        else:
            # بدون manifest فقط حضور فایل را تأیید می‌کنیم
            item["match"] = True
            item["note"] = "no_manifest_sha"
        if entry.size_bytes is not None and entry.size_bytes != actual_size:
            item["size_match"] = False
            ok = False
        else:
            item["size_match"] = True
        checks.append(item)
    return {
        **summary,
        "verified": ok,
        "checks": checks,
    }


def resolve_download_path(backup_dir: str | Path, date: str, kind: str) -> Path:
    if kind not in FILE_KINDS:
        raise BackupCatalogError("kind باید db یا uploads باشد", status_code=400)
    root = resolve_backup_root(backup_dir)
    day = snapshot_dir(root, date)
    path = (day / FILE_KINDS[kind]).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise BackupCatalogError("مسیر دانلود نامعتبر است", status_code=400) from exc
    if not path.is_file():
        raise BackupCatalogError(f"فایل {FILE_KINDS[kind]} برای {date} یافت نشد", status_code=404)
    return path
