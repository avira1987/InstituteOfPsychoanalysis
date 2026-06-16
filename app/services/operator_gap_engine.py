"""موتور کمبود فرایند (قواعد JSON) — on-demand از API؛ اجرای دوره‌ای (cron) اختیاری و در این ماژول نیست."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import ProcessInstance, Student

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GAP_RULES_PATH = _REPO_ROOT / "metadata" / "operator_gap_rules.json"


def _load_gap_rules() -> dict[str, Any]:
    if not _GAP_RULES_PATH.is_file():
        return {"version": "1", "rules": []}
    with _GAP_RULES_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _student_matches_filter(st: Student, filt: dict[str, Any]) -> bool:
    if not filt:
        return True
    for key, val in filt.items():
        if getattr(st, key, None) != val:
            return False
    return True


async def _has_non_cancelled_instance(
    db: AsyncSession,
    student_id: uuid.UUID,
    process_code: str,
) -> bool:
    r = await db.execute(
        select(func.count(ProcessInstance.id)).where(
            ProcessInstance.student_id == student_id,
            ProcessInstance.process_code == process_code,
            ProcessInstance.is_cancelled.is_(False),
        )
    )
    return int(r.scalar() or 0) > 0


async def compute_operator_gaps(
    db: AsyncSession,
    *,
    limit: int = 100,
    student_id: Optional[uuid.UUID] = None,
    max_students_scan: int = 2000,
) -> list[dict[str, Any]]:
    """
    اجرای قواعد enabled روی دانشجویان؛ حداکثر limit ردیف gap برمی‌گرداند.
    """
    data = _load_gap_rules()
    rules = [r for r in (data.get("rules") or []) if r.get("enabled") is True and r.get("expect") == "missing_instance"]
    if not rules:
        return []

    stmt = select(Student).order_by(Student.student_code.asc())
    if student_id is not None:
        stmt = stmt.where(Student.id == student_id)
    stmt = stmt.limit(max_students_scan)
    r = await db.execute(stmt)
    students = r.scalars().all()

    out: list[dict[str, Any]] = []
    for st in students:
        if len(out) >= limit:
            break
        for rule in rules:
            if len(out) >= limit:
                break
            filt = rule.get("student_filter") or {}
            if not _student_matches_filter(st, filt):
                continue
            pcode = rule.get("process_code")
            if not pcode:
                continue
            has_inst = await _has_non_cancelled_instance(db, st.id, str(pcode))
            if has_inst:
                continue
            out.append(
                {
                    "kind": "gap",
                    "rule_id": rule.get("id", ""),
                    "title_fa": rule.get("title_fa", ""),
                    "process_code": str(pcode),
                    "student_id": str(st.id),
                    "student_code": st.student_code,
                    "severity": "warning",
                }
            )
    return out
