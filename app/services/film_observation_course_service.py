"""سرویس فرایند ۶۴ — خاتمه درس مشاهده فیلم / عملی کاربردی (گزارش پایانی PDF)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import ProcessInstance

PROCESS_CODE = "film_observation_course_completion"


def _as_mapping(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        return dict(data)
    return {}


def course_code_from_context(ctx: dict[str, Any]) -> str:
    for key in ("course_code", "lesson_course_label", "course_id", "course_name"):
        val = ctx.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


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


def enrich_roster_with_final_reports(
    roster: list[dict[str, Any]],
    reports_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """ادغام final_report_pdf و نمرات مشارکت/حضور در ردیف‌های roster."""
    if not reports_map:
        return roster
    for row in roster:
        if (row.get("role") or "student") == "teaching_assistant":
            continue
        sid = str(row.get("student_id") or "")
        info = reports_map.get(sid)
        if not info:
            continue
        if info.get("final_report_pdf"):
            row["final_report_pdf"] = info["final_report_pdf"]
            row["report_file"] = info["final_report_pdf"]
        if info.get("final_report_uploaded_at"):
            row["final_report_uploaded_at"] = info["final_report_uploaded_at"]
        if info.get("participation_score") is not None and row.get("participation_score") in (None, ""):
            row["participation_score"] = info["participation_score"]
        if info.get("attendance_score") is not None and row.get("attendance_score") in (None, ""):
            row["attendance_score"] = info["attendance_score"]
        if info.get("report_grade") is not None and row.get("report_grade") in (None, ""):
            row["report_grade"] = info["report_grade"]
    return roster
