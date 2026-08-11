"""Unit tests for backup_catalog (filesystem-only, no DB)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.services.backup_catalog import (
    BackupCatalogError,
    get_snapshot,
    list_snapshots,
    resolve_download_path,
    verify_snapshot,
)


def _write_snap(root: Path, day: str, *, db: bytes = b"DB", uploads: bytes = b"UP", with_manifest: bool = True):
    d = root / day
    d.mkdir(parents=True)
    (d / "db.dump").write_bytes(db)
    (d / "uploads.tar.gz").write_bytes(uploads)
    if with_manifest:
        manifest = {
            "date": day,
            "taken_at": f"{day}T01:00:00Z",
            "status": "ok",
            "postgres_version": "16.0",
            "files": {
                "db.dump": {"size_bytes": len(db), "sha256": hashlib.sha256(db).hexdigest()},
                "uploads.tar.gz": {
                    "size_bytes": len(uploads),
                    "sha256": hashlib.sha256(uploads).hexdigest(),
                },
            },
        }
        (d / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_list_and_get_snapshot(tmp_path: Path):
    _write_snap(tmp_path, "2026-08-10")
    _write_snap(tmp_path, "2026-08-11")
    items = list_snapshots(tmp_path)
    assert [i["date"] for i in items] == ["2026-08-11", "2026-08-10"]
    detail = get_snapshot(tmp_path, "2026-08-10")
    assert detail["status"] == "ok"
    assert detail["files"]["db.dump"]["present"] is True


def test_verify_ok_and_mismatch(tmp_path: Path):
    _write_snap(tmp_path, "2026-08-10")
    ok = verify_snapshot(tmp_path, "2026-08-10")
    assert ok["verified"] is True

    bad = tmp_path / "2026-08-10" / "db.dump"
    bad.write_bytes(b"TAMPERED")
    bad_res = verify_snapshot(tmp_path, "2026-08-10")
    assert bad_res["verified"] is False


def test_download_path_and_traversal(tmp_path: Path):
    _write_snap(tmp_path, "2026-08-10")
    p = resolve_download_path(tmp_path, "2026-08-10", "db")
    assert p.name == "db.dump"
    with pytest.raises(BackupCatalogError) as ei:
        resolve_download_path(tmp_path, "../etc", "db")
    assert ei.value.status_code == 400
    with pytest.raises(BackupCatalogError) as ei2:
        get_snapshot(tmp_path, "1999-01-01")
    assert ei2.value.status_code == 404
