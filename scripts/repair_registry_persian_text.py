# -*- coding: utf-8 -*-
"""Restore stripped Persian in INDEX.json from SOP / process metadata."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from lib.persian_text_integrity import is_stripped_persian, try_prefix_repair  # noqa: E402

from _fix_index_name_fa import resolve_name  # noqa: E402
from app.meta.sop_registry import _FALLBACK_SOP_ORDER  # noqa: E402

IDX = ROOT / "metadata" / "process_registry" / "INDEX.json"
META = ROOT / "metadata" / "processes"
REG = ROOT / "metadata" / "process_registry" / "processes"

INDEX_DESCRIPTION = "فهرست ماشین‌خوان فرایندها و وضعیت آن‌ها"


def _load_meta(code: str) -> dict:
    path = META / f"{code}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _process_description(code: str) -> str:
    data = _load_meta(code)
    proc = data.get("process") or {}
    return str(proc.get("description") or "").strip()


def _rewrite_notes(code: str, sop_order: int | None) -> str:
    desc = _process_description(code)
    prefix = f"مرحله {sop_order} (SOP)." if sop_order is not None else "SOP."
    parts = [prefix]
    if desc:
        parts.append(desc if desc.endswith((".", "。", "؟", "!")) else desc + ".")
    sop_txt = REG / code / "SOP_document.txt"
    sop_png = REG / code / "SOP_flowchart.png"
    if sop_txt.exists():
        pointer = f"processes/{code}/SOP_document.txt"
        if sop_png.exists():
            pointer += " + SOP_flowchart.png"
            pointer += f" sync: scripts/sync_sop_doc_from_registry_files.py --code {code}"
        parts.append("SOP: " + pointer)
    return " ".join(parts)


def _insert_sop_order(proc: dict, order: int) -> dict:
    if "sop_order" in proc:
        proc["sop_order"] = order
        return proc
    out: dict = {}
    inserted = False
    for key, value in proc.items():
        if key == "notes" and not inserted:
            out["sop_order"] = order
            inserted = True
        out[key] = value
    if not inserted:
        out["sop_order"] = order
    return out


def repair_index() -> dict:
    idx = json.loads(IDX.read_text(encoding="utf-8"))
    stats = {
        "description": False,
        "sop_order": [],
        "name_fa": [],
        "notes_prefix": [],
        "notes_rewrite": [],
        "notes_kept": [],
    }
    if idx.get("description") != INDEX_DESCRIPTION:
        idx["description"] = INDEX_DESCRIPTION
        stats["description"] = True

    repaired_procs = []
    for proc in idx.get("processes") or []:
        code = proc["code"]
        fallback = _FALLBACK_SOP_ORDER.get(code)
        if not isinstance(proc.get("sop_order"), int) and fallback is not None:
            proc = _insert_sop_order(proc, fallback)
            stats["sop_order"].append(code)
        sop_order = proc.get("sop_order") if isinstance(proc.get("sop_order"), int) else fallback

        resolved = resolve_name(code)
        meta_name = str((_load_meta(code).get("process") or {}).get("name_fa") or "").strip()
        chosen = resolved or meta_name or proc.get("name_fa")
        if chosen and chosen != proc.get("name_fa"):
            stats["name_fa"].append({"code": code, "old": proc.get("name_fa"), "new": chosen})
            proc["name_fa"] = chosen

        notes = proc.get("notes") or ""
        prefixed = try_prefix_repair(notes)
        if not is_stripped_persian(prefixed):
            if prefixed != notes:
                stats["notes_prefix"].append(code)
            else:
                stats["notes_kept"].append(code)
            proc["notes"] = prefixed
        else:
            proc["notes"] = _rewrite_notes(code, sop_order)
            stats["notes_rewrite"].append(code)
        repaired_procs.append(proc)

    idx["processes"] = repaired_procs
    IDX.write_text(json.dumps(idx, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return stats


def main() -> None:
    stats = repair_index()
    print("description updated:", stats["description"])
    print("sop_order filled:", stats["sop_order"])
    print("name_fa updated:", len(stats["name_fa"]))
    print("notes prefix-repaired:", stats["notes_prefix"])
    print("notes rewritten:", len(stats["notes_rewrite"]), stats["notes_rewrite"])
    print("notes kept:", len(stats["notes_kept"]))


if __name__ == "__main__":
    main()
