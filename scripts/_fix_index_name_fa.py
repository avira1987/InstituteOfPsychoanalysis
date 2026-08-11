# -*- coding: utf-8 -*-
"""One-shot: restore corrupted INDEX.json name_fa from registry sources."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IDX = ROOT / "metadata" / "process_registry" / "INDEX.json"
REG = ROOT / "metadata" / "process_registry" / "processes"

OVERRIDES = {
    "therapy_early_termination": "قطع زودرس درمان آموزشی توسط درمانگر آموزشی",
    "specialized_commission_review": "بررسی کمیسیون تخصصی (زیرفرایند الف)",
    "committees_review": "بررسی کمیته‌های نظارت و آموزش (زیرفرایند ب)",
    "process_merged_to_one": "منتقل‌شده به فرایند شماره ۱",
    "therapy_changes": "مدیریت تغییرات درمان آموزشی (آغاز مجدد، تغییر درمانگر، تغییر ساعت)",
}


def clean_title(text: str) -> str:
    t = (text or "").strip().lstrip("#").strip()
    if t.startswith("فرایند "):
        t = t[len("فرایند ") :].strip()
    if t.startswith("وضعیت:"):
        t = t.split(":", 1)[1].strip()
    if t.startswith("وضعیت "):
        t = t[len("وضعیت ") :].strip()
    t = re.split(r"\s*[—–-]\s*بخش\s*\d+", t, maxsplit=1)[0].strip()
    t = re.sub(r"\s*\(مرحلهٔ?\s*\d+\)\s*$", "", t).strip()
    t = re.sub(r"\s*\(Stub\)\s*$", "", t, flags=re.I).strip()
    t = re.sub(r"\s*—\s*مرحلهٔ?\s*\d+.*$", "", t).strip()
    return t


def is_usable(name: str) -> bool:
    if not name:
        return False
    if re.search(r"[A-Za-z]", name):
        return False
    if "پیاده‌سازی" in name:
        return False
    return True


def resolve_name(code: str) -> str | None:
    if code in OVERRIDES:
        return OVERRIDES[code]
    candidates: list[str] = []
    out = REG / code / "03_output.json"
    if out.exists():
        d = json.loads(out.read_text(encoding="utf-8"))
        proc = d.get("process") or {}
        raw = (proc.get("name_fa") or d.get("name_fa") or "").strip()
        if raw:
            candidates.append(clean_title(raw))
    # 01_input often has the public process title; SOP may be a section heading.
    for cand in ("01_input.md", "SOP_document.txt", "04_status.md"):
        fp = REG / code / cand
        if not fp.exists():
            continue
        first = fp.read_text(encoding="utf-8").splitlines()[0]
        candidates.append(clean_title(first))
    for c in candidates:
        if is_usable(c):
            return c
    return None


def main() -> None:
    idx = json.loads(IDX.read_text(encoding="utf-8"))
    changed = []
    still_bad = []
    for p in idx["processes"]:
        code = p["code"]
        new = resolve_name(code)
        if not new:
            still_bad.append(code)
            continue
        old = p.get("name_fa")
        if old != new:
            changed.append({"code": code, "old": old, "new": new})
            p["name_fa"] = new
    if still_bad:
        raise SystemExit(f"unresolved: {still_bad}")
    IDX.write_text(json.dumps(idx, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"updated {len(changed)} name_fa entries in INDEX.json")

    from app.meta.student_lifecycle_matrix import (
        _load_process_index_json,
        _process_name_fa_by_code,
        get_student_lifecycle_matrix,
    )

    _load_process_index_json.cache_clear()
    _process_name_fa_by_code.cache_clear()
    d = get_student_lifecycle_matrix()
    print("P0:", d["phases"][0]["process_labels_fa"])
    print("P3:", d["phases"][3]["process_labels_fa"][:6])
    print("P5:", d["phases"][5]["process_labels_fa"])


if __name__ == "__main__":
    main()
