"""PDF pack for admissions officer → marketing manager handoff (semester prep step 6)."""

from __future__ import annotations

from typing import Any

import jdatetime

from app.services.reports_formatters import rows_to_pdf_bytes
from app.services.semester_prep_service import FALL_PREP, WINTER_PREP
from app.utils.shamsi_calendar_utils import parse_iso_date


def _fmt_date(value: Any) -> str:
    if value in (None, ""):
        return "—"
    d = parse_iso_date(value)
    if d is None:
        return str(value)
    try:
        jd = jdatetime.date.fromgregorian(date=d)
        return jd.strftime("%Y/%m/%d")
    except (TypeError, ValueError):
        return str(value)


def _fmt_rial(value: Any) -> str:
    if value in (None, ""):
        return "—"
    try:
        n = int(float(value))
        return f"{n:,} ریال"
    except (TypeError, ValueError):
        return str(value)


def _fmt_range(start: Any, end: Any) -> str:
    if not start and not end:
        return "—"
    return f"{_fmt_date(start)} تا {_fmt_date(end)}"


def _fmt_break_periods(periods: Any) -> str:
    if not isinstance(periods, list) or not periods:
        return "—"
    parts: list[str] = []
    for item in periods:
        if not isinstance(item, dict):
            continue
        s = _fmt_date(item.get("start"))
        e = _fmt_date(item.get("end"))
        if s != "—" or e != "—":
            parts.append(f"{s} تا {e}")
    return "؛ ".join(parts) if parts else "—"


def _nonempty_table(value: Any) -> list[dict[str, Any]]:
  if not isinstance(value, list):
    return []
  return [row for row in value if isinstance(row, dict) and any(v not in (None, "", False) for v in row.values())]


def _draft_row_to_finalized(row: dict[str, Any]) -> dict[str, Any]:
  return {
    "course_name": row.get("course_name") or "",
    "track": row.get("track") or "",
    "day": row.get("day") or row.get("proposed_day") or "",
    "time": row.get("time") or row.get("proposed_time") or "",
    "instructor": row.get("instructor") or "",
    "teaching_assistant": row.get("teaching_assistant") or "",
    "classroom_location": row.get("classroom_location") or "",
    "instructor_coordinated": row.get("instructor_coordinated"),
  }


def resolve_marketing_handoff_context(process_code: str, ctx: dict[str, Any]) -> dict[str, Any]:
  """نرمال‌سازی context برای گزارش/PDF کمپین — fallback از پیش‌نویس مرحلهٔ ۴ اگر نهایی‌سازی خالی باشد."""
  code = (process_code or "").strip()
  raw = dict(ctx) if isinstance(ctx, dict) else {}
  out = dict(raw)

  if code == FALL_PREP:
    fall_final = _nonempty_table(raw.get("courses_finalized_fall"))
    if not fall_final:
      fall_final = _nonempty_table(raw.get("courses_finalized"))
    if not fall_final:
      fall_final = _nonempty_table(raw.get("courses_fall"))
    if not fall_final:
      fall_final = _nonempty_table(raw.get("courses"))
    if fall_final and not _nonempty_table(raw.get("courses_finalized_fall")):
      out["courses_finalized_fall"] = [
        _draft_row_to_finalized(row) if row.get("proposed_day") or row.get("proposed_time") else row
        for row in fall_final
      ]

    winter_final = _nonempty_table(raw.get("courses_finalized_winter"))
    if not winter_final:
      winter_final = _nonempty_table(raw.get("courses_winter"))
    if winter_final and not _nonempty_table(raw.get("courses_finalized_winter")):
      out["courses_finalized_winter"] = [
        _draft_row_to_finalized(row) if row.get("proposed_day") or row.get("proposed_time") else row
        for row in winter_final
      ]

  elif code == WINTER_PREP:
    winter_final = _nonempty_table(raw.get("courses_finalized"))
    if not winter_final:
      winter_final = _nonempty_table(raw.get("courses_winter"))
    if not winter_final:
      winter_final = _nonempty_table(raw.get("courses"))
    if winter_final and not _nonempty_table(raw.get("courses_finalized")):
      out["courses_finalized"] = [
        _draft_row_to_finalized(row) if row.get("proposed_day") or row.get("proposed_time") else row
        for row in winter_final
      ]

  return out


def _course_rows(courses: Any) -> list[list[str]]:
    if not isinstance(courses, list) or not courses:
        return []
    out: list[list[str]] = []
    for row in courses:
        if not isinstance(row, dict):
            continue
        coordinated = row.get("instructor_coordinated")
        coord_txt = "بله" if coordinated is True else ("خیر" if coordinated is False else "—")
        out.append(
            [
                str(row.get("course_name") or "—"),
                str(row.get("track") or "—"),
                str(row.get("proposed_day") or row.get("day") or "—"),
                str(row.get("proposed_time") or row.get("time") or "—"),
                str(row.get("instructor") or "—"),
                str(row.get("teaching_assistant") or "—"),
                str(row.get("classroom_location") or "—"),
                coord_txt,
            ]
        )
    return out


def _append_calendar_section(rows: list[list[Any]], ctx: dict[str, Any]) -> None:
    rows.append(["فعالیت ۱ — تقویم آموزشی"])
    rows.append(["عنوان", "مقدار"])
    rows.append(["ترم پاییز", _fmt_range(ctx.get("fall_start_date"), ctx.get("fall_end_date"))])
    rows.append(["ترم زمستان", _fmt_range(ctx.get("winter_start_date"), ctx.get("winter_end_date"))])
    rows.append(
        [
            "پنجره ثبت‌نام و پرداخت",
            _fmt_range(
                ctx.get("registration_payment_window_start"),
                ctx.get("registration_payment_window_end"),
            ),
        ]
    )
    rows.append(["مهلت مصاحبه انترن‌ها", _fmt_date(ctx.get("intern_interview_deadline"))])
    rows.append(
        ["مهلت مصاحبه کمک‌مدرس", _fmt_date(ctx.get("teaching_assistant_interview_deadline"))]
    )
    rows.append(["تعطیلات نوروز", _fmt_range(ctx.get("nowruz_holiday_start"), ctx.get("nowruz_holiday_end"))])
    rows.append(["تعطیلات ترم پاییز", _fmt_break_periods(ctx.get("fall_break_periods"))])
    rows.append(["تعطیلات ترم زمستان", _fmt_break_periods(ctx.get("winter_break_periods"))])
    rows.append([])


def _append_tuition_section(rows: list[list[Any]], ctx: dict[str, Any]) -> None:
    rows.append(["فعالیت ۲ — شهریه و هزینه مصاحبه"])
    rows.append(["عنوان", "مقدار"])
    rows.append(["هزینه هر واحد دوره آشنایی", _fmt_rial(ctx.get("per_unit_cost_introductory"))])
    rows.append(["هزینه هر واحد دوره جامع", _fmt_rial(ctx.get("per_unit_cost_comprehensive"))])
    rows.append(["هزینه مصاحبه دوره آشنایی", _fmt_rial(ctx.get("interview_fee_introductory"))])
    rows.append(["هزینه مصاحبه دوره جامع", _fmt_rial(ctx.get("interview_fee_comprehensive"))])
    rows.append([])


def _append_courses_table(
    rows: list[list[Any]],
    *,
    title: str,
    courses: Any,
    finalized: bool,
) -> None:
    rows.append([title])
    course_rows = _course_rows(courses)
    if not course_rows:
        rows.append(["(داده‌ای ثبت نشده)"])
        rows.append([])
        return
    header = ["نام درس", "ترک", "روز", "ساعت", "مدرس", "کمک‌مدرس", "مکان"]
    if finalized:
        header.append("هماهنگی با مدرس")
    rows.append(header)
    for row in course_rows:
        rows.append(row if finalized else row[:7])
    rows.append([])


def build_marketing_campaign_pdf_rows(process_code: str, ctx: dict[str, Any]) -> list[list[Any]]:
    """Build tabular rows for marketing handoff PDF."""
    code = (process_code or "").strip()
    context = resolve_marketing_handoff_context(code, ctx if isinstance(ctx, dict) else {})
    rows: list[list[Any]] = []

    if code == FALL_PREP:
        _append_calendar_section(rows, context)
        _append_tuition_section(rows, context)
        finalized_fall = (
            context.get("courses_finalized_fall")
            or context.get("courses_finalized")
            or context.get("courses_fall")
            or context.get("courses")
        )
        finalized_winter = (
            context.get("courses_finalized_winter")
            or context.get("courses_winter")
        )
        _append_courses_table(
            rows,
            title="فعالیت ۵ — برنامه نهایی دروس ترم پاییز",
            courses=finalized_fall,
            finalized=True,
        )
        _append_courses_table(
            rows,
            title="فعالیت ۵ — برنامه نهایی دروس ترم زمستان",
            courses=finalized_winter,
            finalized=True,
        )
    elif code == WINTER_PREP:
        _append_courses_table(
            rows,
            title="فعالیت ۲ — لیست دروس ترم زمستان",
            courses=context.get("courses") or context.get("courses_winter"),
            finalized=False,
        )
        finalized = (
            context.get("courses_finalized")
            or context.get("courses_winter")
            or context.get("courses")
        )
        _append_courses_table(
            rows,
            title="فعالیت ۳ — برنامه نهایی دروس زمستان",
            courses=finalized,
            finalized=True,
        )
    else:
        rows.append(["(فرایند پشتیبانی نمی‌شود)"])

    return rows


def marketing_campaign_pdf_title(process_code: str) -> str:
    if process_code == WINTER_PREP:
        return "بسته اطلاعات کمپین بازاریابی زمستان"
    return "بسته اطلاعات کمپین بازاریابی پذیرش"


def build_marketing_campaign_pdf_bytes(
    process_code: str,
    ctx: dict[str, Any],
    *,
    recipient_display_name: str = "",
) -> bytes:
    rows = build_marketing_campaign_pdf_rows(process_code, ctx)
    return rows_to_pdf_bytes(
        rows,
        document_title=marketing_campaign_pdf_title(process_code),
        recipient_display_name=recipient_display_name,
    )
