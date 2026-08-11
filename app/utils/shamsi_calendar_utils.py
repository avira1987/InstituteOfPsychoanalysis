"""Shamsi calendar helpers for semester-prep scheduling."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

import jdatetime

TEHRAN = ZoneInfo("Asia/Tehran")

_SHAMSI_DATE_RE = re.compile(r"^(\d{4})/(\d{1,2})/(\d{1,2})$")
_ISO_DATE_PREFIX_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")

_SMS_DATE_FIELD_EXACT = frozenset({
    "interview_date",
    "date",
    "meeting_date",
    "deadline",
    "session_date",
    "session_date_fa",
    "due_date",
    "start_date",
    "end_date",
    "makeup_date",
    "proposed_date",
    "registration_payment_deadline",
    "documents_upload_deadline",
    "documents_correction_deadline",
    "lms_login_deadline",
    "first_session_date",
    "first_session_date_effective",
    "agreed_session_date",
    "cancelled_session_date",
    "record_date",
    "term_start_date",
    "term_end_date",
    "display_calculated_start_date",
    "next_installment_due_at",
    "installment_due_at",
    "تاریخ ثبت شده",
})
_SMS_DATETIME_FIELD_EXACT = frozenset({
    "committee_meeting_at",
    "return_deadline_at",
    "return_reminder_at",
    "meeting_at_fa",
})
_SMS_DATE_FIELD_SUFFIXES = ("_date", "_deadline")
_SMS_SKIP_NORMALIZE_KEYS = frozenset({"day", "username", "password", "amount", "amount_rial"})


def tehran_today() -> date:
    return datetime.now(TEHRAN).date()


def shamsi_parts(d: date | None = None) -> tuple[int, int, int]:
    g = d or tehran_today()
    j = jdatetime.date.fromgregorian(date=g)
    return j.year, j.month, j.day


def is_farvardin_15_20(d: date | None = None) -> bool:
    """True when today (Tehran) is Farvardin 15–20."""
    _, month, day = shamsi_parts(d)
    return month == 1 and 15 <= day <= 20


def farvardin_20_end_tehran(shamsi_year: int | None = None) -> datetime:
    """End of Farvardin 20 (23:59:59 Tehran) as UTC-aware datetime."""
    sy = shamsi_year or shamsi_parts()[0]
    g = jdatetime.date(sy, 1, 20).togregorian()
    local_end = datetime.combine(g, time(23, 59, 59), tzinfo=TEHRAN)
    return local_end.astimezone(timezone.utc)


def days_before_date(target: date, days: int, today: date | None = None) -> bool:
    ref = today or tehran_today()
    return ref >= (target - __import__("datetime").timedelta(days=days))


def tehran_calendar_date(value: Any) -> Optional[date]:
    """Calendar day in Asia/Tehran — never use UTC ``.date()`` / ``[:10]`` for SMS or due-day checks."""
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(TEHRAN).date()
    if isinstance(value, date):
        return value
    raw = str(value).strip()
    if not raw or raw == "—":
        return None
    if _is_shamsi_date_text(raw):
        try:
            y, m, d = (int(x) for x in raw.split("/"))
            return jdatetime.date(y, m, d).togregorian()
        except (TypeError, ValueError):
            return None
    dt = _parse_datetime_value(raw)
    if dt is not None:
        return dt.astimezone(TEHRAN).date()
    try:
        # Date-only ISO: treat as civil calendar day (not a UTC midnight instant).
        if _ISO_DATE_PREFIX_RE.match(raw[:10]) and "T" not in raw and " " not in raw:
            return date.fromisoformat(raw[:10])
    except (TypeError, ValueError):
        return None
    return None


def parse_iso_date(value) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    # Datetime / ISO-with-time → Tehran calendar day (avoids off-by-one near midnight).
    td = tehran_calendar_date(value)
    if td is not None:
        return td
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def tehran_day_start_utc(d: date) -> datetime:
    """Start of calendar day in Tehran, as UTC-aware datetime."""
    local_start = datetime.combine(d, time.min, tzinfo=TEHRAN)
    return local_start.astimezone(timezone.utc)


def tehran_day_end_utc(d: date) -> datetime:
    """End of calendar day in Tehran (23:59:59), as UTC-aware datetime."""
    local_end = datetime.combine(d, time(23, 59, 59), tzinfo=TEHRAN)
    return local_end.astimezone(timezone.utc)


def tehran_datetime_parts(dt: datetime) -> tuple[str, str]:
    """Shamsi date (YYYY/MM/DD) and HH:MM in Asia/Tehran for SMS/notifications."""
    raw_in = dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(TEHRAN)
    jdate = jdatetime.date.fromgregorian(date=local.date())
    date_s, time_s = jdate.strftime("%Y/%m/%d"), local.strftime("%H:%M")
    # #region agent log
    try:
        import json as _json
        from pathlib import Path as _Path
        from time import time as _time
        _line = {
            "sessionId": "8e31fd",
            "hypothesisId": "C",
            "location": "shamsi_calendar_utils.py:tehran_datetime_parts",
            "message": "tehran_datetime_parts convert",
            "data": {
                "input": str(raw_in),
                "input_tz": str(getattr(raw_in, "tzinfo", None)),
                "assumed_utc_naive": getattr(raw_in, "tzinfo", None) is None,
                "local_tehran": local.isoformat(),
                "out_date": date_s,
                "out_time": time_s,
            },
            "timestamp": int(_time() * 1000),
            "runId": "post-fix",
        }
        with open(_Path(__file__).resolve().parents[2] / "debug-8e31fd.log", "a", encoding="utf-8") as _f:
            _f.write(_json.dumps(_line, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion
    return date_s, time_s


def _is_shamsi_date_text(value: str) -> bool:
    m = _SHAMSI_DATE_RE.match(value.strip())
    if not m:
        return False
    try:
        year = int(m.group(1))
    except ValueError:
        return False
    return 1200 <= year <= 1600


def _gregorian_to_shamsi_date_str(gday: date) -> str:
    return jdatetime.date.fromgregorian(date=gday).strftime("%Y/%m/%d")


def _parse_datetime_value(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=TEHRAN)
    raw = str(value).strip()
    if not raw or raw == "—":
        return None
    if _is_shamsi_date_text(raw):
        return None
    try:
        if "T" in raw or " " in raw:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        if _ISO_DATE_PREFIX_RE.match(raw[:10]):
            d = date.fromisoformat(raw[:10])
            return datetime.combine(d, time.min, tzinfo=TEHRAN)
    except (TypeError, ValueError):
        return None
    return None


def format_shamsi_date(value: Any) -> str:
    """Normalize a date/datetime/ISO string to Shamsi YYYY/MM/DD for SMS."""
    if value is None:
        return ""
    if isinstance(value, str):
        s = value.strip()
        if not s or s == "—":
            return s
        if _is_shamsi_date_text(s):
            return s
    dt = _parse_datetime_value(value)
    if dt is not None:
        local = dt.astimezone(TEHRAN)
        return _gregorian_to_shamsi_date_str(local.date())
    if isinstance(value, date):
        return _gregorian_to_shamsi_date_str(value)
    return str(value).strip()


def format_shamsi_datetime_for_sms(value: Any) -> str:
    """Shamsi date + Tehran clock for SMS (YYYY/MM/DD HH:MM)."""
    if value is None:
        return ""
    s = str(value).strip()
    if not s or s == "—":
        return s
    if _is_shamsi_date_text(s):
        return s
    dt = _parse_datetime_value(value)
    if dt is None:
        return format_shamsi_date(value)
    local = dt.astimezone(TEHRAN)
    jdate = jdatetime.date.fromgregorian(date=local.date())
    return f"{jdate.strftime('%Y/%m/%d')} {local.strftime('%H:%M')}"


def _format_absence_dates_shamsi(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return raw
    parts = re.split(r"[,،;\n]+", raw)
    out: list[str] = []
    for part in parts:
        token = part.strip()
        if not token:
            continue
        out.append(format_shamsi_date(token))
    return "، ".join(out)


def _should_normalize_sms_date_key(key: str) -> bool:
    if not key or key in _SMS_SKIP_NORMALIZE_KEYS:
        return False
    if key in _SMS_DATE_FIELD_EXACT or key in _SMS_DATETIME_FIELD_EXACT:
        return True
    if key.endswith("_time"):
        return False
    return any(key.endswith(suffix) for suffix in _SMS_DATE_FIELD_SUFFIXES)


def normalize_sms_context_dates(context: dict[str, Any] | None) -> dict[str, Any]:
    """Ensure date-like SMS template variables use Shamsi calendar in Tehran timezone."""
    if not context:
        return {}
    out = dict(context)
    # #region agent log
    _dbg_before: dict[str, Any] = {}
    # #endregion
    for key, value in list(out.items()):
        if value is None or str(value).strip() in ("", "—"):
            continue
        if key == "absence_dates":
            # #region agent log
            _dbg_before[key] = str(value)[:120]
            # #endregion
            out[key] = _format_absence_dates_shamsi(value)
            continue
        if key in _SMS_DATETIME_FIELD_EXACT:
            # #region agent log
            _dbg_before[key] = str(value)[:120]
            # #endregion
            out[key] = format_shamsi_datetime_for_sms(value)
            continue
        if _should_normalize_sms_date_key(key):
            # #region agent log
            _dbg_before[key] = str(value)[:120]
            # #endregion
            out[key] = format_shamsi_date(value)
    if out.get("meeting_date") and not out.get("date"):
        out["date"] = out["meeting_date"]
    if out.get("interview_date") and not out.get("date"):
        out["date"] = out["interview_date"]
    # #region agent log
    try:
        import json as _json
        from pathlib import Path as _Path
        from time import time as _time
        _dbg_after = {k: str(out.get(k))[:120] for k in _dbg_before}
        _suspect_slice = {
            k: str(context.get(k))[:40]
            for k in (context or {})
            if any(x in k for x in ("date", "deadline", "due", "at", "تاریخ"))
            and k not in _dbg_before
        }
        _line = {
            "sessionId": "8e31fd",
            "hypothesisId": "A,D",
            "location": "shamsi_calendar_utils.py:normalize_sms_context_dates",
            "message": "sms date normalize in/out",
            "data": {
                "before": _dbg_before,
                "after": _dbg_after,
                "unnormalized_date_like": _suspect_slice,
                "tehran_today": str(tehran_today()),
                "utc_today": str(datetime.now(timezone.utc).date()),
            },
            "timestamp": int(_time() * 1000),
            "runId": "post-fix",
        }
        with open(_Path(__file__).resolve().parents[2] / "debug-8e31fd.log", "a", encoding="utf-8") as _f:
            _f.write(_json.dumps(_line, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion
    return out


def iso_value_has_explicit_time(value) -> bool:
    """True when an ISO string carries a non-midnight clock time (admin scheduler)."""
    raw = str(value or "").strip()
    if not raw or "T" not in raw and " " not in raw:
        return False
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(TEHRAN)
    return local.hour != 0 or local.minute != 0 or local.second != 0
