"""Normalize Slice 1 patient_referral context rows."""

from __future__ import annotations

from typing import Any, Optional


def normalize_referral_patients(raw: Any) -> list[dict[str, Optional[str]]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Optional[str]]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        label = str(row.get("patient_label") or row.get("patient_name") or "").strip()
        if not label:
            continue
        tid = row.get("assigned_therapist_user_id") or row.get("therapist_user_id")
        tid_s = str(tid).strip() if tid not in (None, "") else None
        out.append(
            {
                "patient_label": label,
                "assigned_therapist_user_id": tid_s,
            }
        )
    return out
