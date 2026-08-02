"""سرویس فرایند ۶۵ — خاتمه درس مشاهده زنده درمان (گزارش پایانی PDF)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import ProcessInstance
from app.services.film_observation_course_service import (
    course_code_from_context,
    enrich_roster_with_final_reports,
)

PROCESS_CODE = "live_therapy_observation_course_completion"


def _as_mapping(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        return dict(data)
    return {}


def _context_matches_course(ctx: dict[str, Any], course_code: str) -> bool:
    code = str(course_code or "").strip()
    if not code:
        return False
    inst_code = course_code_from_context(ctx)
    if inst_code == code:
        return True
    name = str(ctx.get("course_name") or "").strip()
    return name == code


async def collect_student_final_reports(
    db: AsyncSession,
    course_code: str,
) -> dict[str, dict[str, Any]]:
    """گزارش‌های PDF آپلودشدهٔ دانشجویان برای یک درس — از نمونه‌های per-student."""
    code = str(course_code or "").strip()
    if not code:
        return {}

    result = await db.execute(
        select(ProcessInstance).where(
            ProcessInstance.process_code == PROCESS_CODE,
            ProcessInstance.is_cancelled.is_(False),
        )
    )
    reports: dict[str, dict[str, Any]] = {}
    for inst in result.scalars().all():
        ctx = _as_mapping(inst.context_data)
        if not _context_matches_course(ctx, code):
            continue
        pdf = ctx.get("final_report_pdf")
        if not pdf:
            continue
        sid = str(inst.student_id)
        reports[sid] = {
            "final_report_pdf": pdf,
            "final_report_uploaded_at": ctx.get("final_report_uploaded_at"),
            "participation_score": ctx.get("participation_score"),
            "attendance_score": ctx.get("attendance_score"),
            "report_grade": ctx.get("report_grade") if ctx.get("report_grade") is not None else ctx.get("grade"),
        }
    return reports


__all__ = [
    "PROCESS_CODE",
    "collect_student_final_reports",
    "enrich_roster_with_final_reports",
    "course_code_from_context",
]
