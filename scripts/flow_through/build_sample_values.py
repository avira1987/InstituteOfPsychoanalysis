#!/usr/bin/env python3
"""Build sample form values for flow-through tests from field specs."""

from __future__ import annotations

from typing import Any


def _visible(field: dict[str, Any], values: dict[str, Any]) -> bool:
    vis = field.get("visible_if")
    if not isinstance(vis, dict):
        return True
    field_name = vis.get("field")
    if not field_name:
        return True
    expected = vis.get("equals")
    if expected is not None:
        return values.get(field_name) == expected
    if vis.get("not_empty"):
        v = values.get(field_name)
        return v is not None and v != "" and v != []
    return True


def _sample_scalar(field_type: str, name: str, field: dict[str, Any]) -> Any:
    t = (field_type or "text").lower()
    if t in ("checkbox",):
        return True
    if t in ("number",):
        return 1000000 if "rial" in name or "tuition" in name or "fee" in name else 1
    if t in ("select", "radio"):
        opts = field.get("options") or []
        if opts and isinstance(opts[0], dict):
            return opts[0].get("value") or opts[0].get("label")
        if opts:
            return opts[0]
        return "option_a"
    if t in ("multi_select", "checkbox_list"):
        opts = field.get("options") or []
        if opts and isinstance(opts[0], dict):
            return [opts[0].get("value") or opts[0].get("label")]
        return ["option_a"]
    if t in ("radio_list",):
        return "ack"
    if t in ("shamsi_date", "date", "date_picker"):
        return {"year": 1404, "month": 7, "day": 15}
    if t in ("datetime",):
        return "2026-09-15T10:00:00+00:00"
    if t in ("time", "time_picker"):
        return "10:00"
    if t in ("file", "file_upload"):
        return {"file_name": "flow_test.pdf", "url": "/uploads/flow_test.pdf", "size": 1024}
    if t in ("step_otp",):
        return "123456"
    if t in ("therapist_select", "user_select"):
        return "therapist1"
    if t in ("email",):
        return "flow@test.anistito.local"
    if t in ("tel",):
        return "09121234567"
    if t in ("textarea",):
        return "متن تست flow-through"
    return "تست"


def _sample_table(field: dict[str, Any]) -> list[dict[str, Any]]:
    columns = field.get("columns") or []
    row: dict[str, Any] = {}
    default_course = {
        "course_name": "theory_psychoanalysis_1",
        "track": "analytic_psychotherapy",
        "proposed_day": "شنبه",
        "proposed_time": "10:00",
        "instructor": "مدرس تست",
        "teaching_assistant": "کمک‌مدرس تست",
        "classroom_location": "کلاس ۱",
        "instructor_coordinated": True,
    }
    for col in columns:
        if not isinstance(col, dict):
            continue
        cname = col.get("name") or "col"
        ct = (col.get("type") or "text").lower()
        src = col.get("options_source") or {}
        if cname in default_course:
            row[cname] = default_course[cname]
            continue
        if src.get("type") == "course_catalog" or cname == "course_name":
            row[cname] = "theory_psychoanalysis_1"
        elif src.get("type") == "course_committee_tracks" or cname == "track":
            row[cname] = "analytic_psychotherapy"
        elif ct == "checkbox":
            row[cname] = True
        elif ct == "select" and col.get("options"):
            o0 = col["options"][0]
            row[cname] = o0.get("value") if isinstance(o0, dict) else o0
        elif ct in ("number",):
            row[cname] = 1
        elif ct in ("time", "time_picker"):
            row[cname] = "10:00"
        else:
            row[cname] = f"تست {cname}"
    if not row:
        row = dict(default_course)
    return [row]


def _sample_date_range_list(field: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"start": {"year": 1404, "month": 7, "day": 1}, "end": {"year": 1404, "month": 7, "day": 5}},
    ]


def build_sample_values(field_specs: list[dict[str, Any]]) -> dict[str, Any]:
    """Return plausible values for all visible required fields (and optional fields)."""
    values: dict[str, Any] = {}
    # First pass: scalars that other fields may depend on
    for spec in field_specs:
        name = spec.get("name")
        if not name:
            continue
        t = (spec.get("type") or "text").lower()
        if t not in ("table", "date_range_list", "dynamic_list"):
            if _visible(spec, values):
                values[name] = _sample_scalar(t, name, spec)

    for spec in field_specs:
        name = spec.get("name")
        if not name or name in values:
            continue
        if not _visible(spec, values):
            continue
        t = (spec.get("type") or "text").lower()
        if t == "table":
            values[name] = _sample_table(spec)
        elif t == "date_range_list":
            values[name] = _sample_date_range_list(spec)
        elif t == "dynamic_list":
            values[name] = [{"item": "تست"}]
        else:
            values[name] = _sample_scalar(t, name, spec)

    return values
