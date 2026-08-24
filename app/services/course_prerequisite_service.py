"""پیش‌نیاز و هم‌نیاز دروس — پاس/مردود LMS، نه صرفاً ثبت‌نام."""

from __future__ import annotations

from typing import Any, Optional

from app.services.course_committee_roster_service import (
    KNOWN_SYSTEM_PREREQUISITE_CODES,
    get_catalog_course,
    list_system_prerequisites,
)
from app.services.term_end_snapshot_service import _is_failed, _numeric_grade

COREQUISITE_NOTE_FA = "هم‌نیاز: مردودی ترم قبل — قابل اخذ همزمان"
UNMET_PREREQ_PREFIX_FA = "پیش‌نیاز پاس‌نشده: "

_PASS_LABELS = frozenset({"قبول", "pass", "passed", "p", "ok"})
_PASS_LETTERS = frozenset(
    {"A", "A+", "A-", "B", "B+", "B-", "C", "C+", "C-", "D", "D+", "D-"}
)


def _normalize_code(code: str) -> str:
    from app.services.term_course_offering_service import normalize_legacy_course_code

    return normalize_legacy_course_code((code or "").strip())


def unenforced_system_prerequisite_codes() -> set[str]:
    """کدهای پیش‌نیاز سیستمی که هنوز گیت ثبت‌نام نباید قفلشان کند."""
    skip: set[str] = set()
    for item in list_system_prerequisites():
        code = _normalize_code(str(item.get("code") or ""))
        if code and not item.get("enforced"):
            skip.add(code)
    if skip:
        return skip
    return {_normalize_code(c) for c in KNOWN_SYSTEM_PREREQUISITE_CODES if c}


def _entry_code(item: Any) -> str:
    if isinstance(item, str):
        return _normalize_code(item)
    if not isinstance(item, dict):
        return ""
    return _normalize_code(
        str(
            item.get("code")
            or item.get("course_code")
            or item.get("value")
            or ""
        )
    )


def _is_passed(entry: dict) -> bool:
    if _is_failed(entry):
        return False
    if entry.get("passed") is True or entry.get("pass") is True:
        return True
    if entry.get("completed") is True:
        return True
    pf = str(entry.get("pass_fail_status") or entry.get("pass_fail") or "").strip()
    if pf.lower() in _PASS_LABELS or pf in _PASS_LABELS:
        return True
    letter = str(entry.get("letter_grade") or "").strip().upper()
    if letter in _PASS_LETTERS:
        return True
    num = _numeric_grade(entry)
    if num is not None and letter and letter not in {"F", "I", "مردود"}:
        if num >= 10:
            return True
    return False


def _ingest(
    records: Any,
    passed: set[str],
    failed: set[str],
    *,
    strings_mean: Optional[str],
) -> None:
    if not isinstance(records, list):
        return
    for item in records:
        if isinstance(item, str):
            code = _normalize_code(item)
            if not code:
                continue
            if strings_mean == "passed":
                passed.add(code)
                failed.discard(code)
            elif strings_mean == "failed":
                failed.add(code)
                passed.discard(code)
            continue
        if not isinstance(item, dict):
            continue
        code = _entry_code(item)
        if not code:
            continue
        if _is_failed(item):
            failed.add(code)
            passed.discard(code)
            continue
        if _is_passed(item):
            passed.add(code)
            failed.discard(code)


def classify_student_course_progress(
    ctx: Optional[dict[str, Any]] = None,
    student: Any = None,
) -> tuple[set[str], set[str]]:
    """کدهای قبول‌شده و مردود از کارنامه / LMS."""
    passed: set[str] = set()
    failed: set[str] = set()
    data = ctx if isinstance(ctx, dict) else {}
    extra: dict[str, Any] = {}
    if student is not None:
        raw = getattr(student, "extra_data", None) or {}
        if isinstance(raw, dict):
            extra = raw
    lms_extra = extra.get("lms") if isinstance(extra.get("lms"), dict) else {}
    lms_ctx = data.get("lms") if isinstance(data.get("lms"), dict) else {}

    _ingest(lms_extra.get("enrolled_courses"), passed, failed, strings_mean=None)
    _ingest(lms_ctx.get("enrolled_courses"), passed, failed, strings_mean=None)
    _ingest(extra.get("failed_courses"), passed, failed, strings_mean="failed")
    _ingest(data.get("failed_courses"), passed, failed, strings_mean="failed")
    _ingest(lms_extra.get("failed_courses"), passed, failed, strings_mean="failed")
    _ingest(lms_ctx.get("failed_courses"), passed, failed, strings_mean="failed")
    _ingest(data.get("completed_courses"), passed, failed, strings_mean="passed")
    _ingest(extra.get("completed_courses"), passed, failed, strings_mean="passed")
    return passed, failed


def _label_for(code: str, labels: dict[str, str]) -> str:
    if code in labels:
        return labels[code]
    cat = get_catalog_course(code) or {}
    return str(cat.get("label_fa") or code)


def _option_from_catalog(code: str) -> dict[str, Any]:
    cat = get_catalog_course(code) or {}
    return {
        "value": code,
        "label_fa": str(cat.get("label_fa") or code),
        "units": cat.get("units"),
        "track": cat.get("track"),
        "prerequisite_codes": [],
        "selectable": True,
        "is_corequisite": True,
        "corequisite_note_fa": COREQUISITE_NOTE_FA,
    }


def partition_options_by_prerequisites(
    options: list[dict[str, Any]],
    passed_codes: set[str],
    failed_codes: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """جدا کردن دروس مجاز / قفل‌شده؛ مردودی پیش‌نیاز را هم‌نیاز می‌کند."""
    passed = {_normalize_code(c) for c in passed_codes if c}
    failed = {_normalize_code(c) for c in failed_codes if c}
    skip_system = unenforced_system_prerequisite_codes()
    labels: dict[str, str] = {}
    allowed: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    needed_coreq: set[str] = set()
    allowed_codes: set[str] = set()

    for opt in options:
        if not isinstance(opt, dict):
            continue
        code = _normalize_code(str(opt.get("value") or ""))
        if not code:
            continue
        labels[code] = str(opt.get("label_fa") or code)
        raw_prereqs = opt.get("prerequisite_codes") or []
        if not isinstance(raw_prereqs, list) or not raw_prereqs:
            cat = get_catalog_course(code) or {}
            raw_prereqs = cat.get("prerequisite_codes") or []
        prereqs = []
        for p in raw_prereqs:
            norm = _normalize_code(str(p))
            if not norm or norm in skip_system:
                continue
            prereqs.append(norm)
        unmet = [p for p in prereqs if p not in passed and p not in failed]
        coreq = [p for p in prereqs if p in failed and p not in passed]
        if unmet:
            names = [_label_for(p, labels) for p in unmet]
            blocked.append(
                {
                    **opt,
                    "selectable": False,
                    "lock_reason_fa": f"{UNMET_PREREQ_PREFIX_FA}{', '.join(names)}",
                }
            )
            continue
        extra = dict(opt)
        extra["selectable"] = True
        extra["value"] = code
        if coreq:
            extra["corequisite_codes"] = coreq
            extra["corequisite_note_fa"] = COREQUISITE_NOTE_FA
            needed_coreq.update(coreq)
        allowed.append(extra)
        allowed_codes.add(code)

    for code in needed_coreq:
        if code in allowed_codes:
            for opt in allowed:
                if _normalize_code(str(opt.get("value") or "")) == code:
                    opt["is_corequisite"] = True
                    opt.setdefault("corequisite_note_fa", COREQUISITE_NOTE_FA)
            continue
        injected = _option_from_catalog(code)
        allowed.append(injected)
        allowed_codes.add(code)

    return allowed, blocked
