"""واردسازی forms[] متادیتای فرایندها به جداول DB فرم یکپارچه (idempotent).

برای هر فرم در metadata/processes/*.json:
  • FormTemplate با کد namespaced: "{process_code}:{form_code}"
  • FormTemplateVersion منتشرشده (source=metadata) با schema تبدیل‌شده
  • FormAssignment(های) نوع process برای هر used_in_state (+ aliasهای حالت)

تبدیل schema:
  • code فیلد ⇒ name
  • visible_when (عبارت رشته‌ای) ⇒ show_if (شیء)
  • required_when / required_if (رشته‌ای) ⇒ required_if (شیء)
  • confidential/visible_to فرم ⇒ روی فیلدها منتشر می‌شود
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.meta.process_forms import STATE_FORM_ALIASES
from app.models.dynamic_forms import FormAssignment, FormTemplate, FormTemplateVersion

METADATA_PROCESSES_DIR = Path(__file__).resolve().parents[3] / "metadata" / "processes"

# نگاشت معکوس alias: state واقعی ⇒ stateهایی که همان فرم را نشان می‌دهند
_REVERSE_ALIASES: dict[str, list[str]] = {}
for _alias_state, _target_state in STATE_FORM_ALIASES.items():
    _REVERSE_ALIASES.setdefault(_target_state, []).append(_alias_state)


# ─── تبدیل عبارت رشته‌ای به گزارهٔ شیئی ──────────────────────────

_RE_EQ = re.compile(r"^\s*(\w+)\s*==\s*'([^']*)'\s*$")
_RE_NEQ = re.compile(r"^\s*(\w+)\s*!=\s*'([^']*)'\s*$")
_RE_IN = re.compile(r"^\s*(\w+)\s+in\s+\[(.*)\]\s*$")
_RE_NIN = re.compile(r"^\s*(\w+)\s+not\s+in\s+\[(.*)\]\s*$")
_RE_TRUTHY = re.compile(r"^\s*(\w+)\s*$")


def _parse_list(raw: str) -> list[str]:
    return [m.group(1) for m in re.finditer(r"'([^']*)'", raw)]


def expr_to_predicate(expr: Any) -> Optional[dict]:
    """عبارت رشته‌ای metadata را به گزارهٔ { field, op, value } تبدیل می‌کند.

    اگر از قبل شیء باشد، همان برمی‌گردد. اگر قابل تجزیه نباشد None (یعنی همیشه نمایش/الزام پایه).
    """
    if expr is None:
        return None
    if isinstance(expr, dict):
        return expr
    if not isinstance(expr, str):
        return None
    s = expr.strip()
    if not s:
        return None

    m = _RE_EQ.match(s)
    if m:
        return {"field": m.group(1), "op": "eq", "value": m.group(2)}
    m = _RE_NEQ.match(s)
    if m:
        return {"field": m.group(1), "op": "neq", "value": m.group(2)}
    m = _RE_IN.match(s)
    if m:
        return {"field": m.group(1), "op": "in", "value": _parse_list(m.group(2))}
    m = _RE_NIN.match(s)
    if m:
        return {"field": m.group(1), "op": "nin", "value": _parse_list(m.group(2))}
    m = _RE_TRUTHY.match(s)
    if m:
        return {"field": m.group(1), "op": "truthy"}
    # عبارت پیچیده (and/or و …) — نگه‌داری خام برای دیباگ، نمایش پیش‌فرض True
    return {"raw": s}


def _convert_field(field: dict, form_confidential: bool, form_visible_to: Any) -> dict:
    out = dict(field)
    if not out.get("name") and out.get("code"):
        out["name"] = out["code"]

    vw = out.pop("visible_when", None)
    if vw is not None and "show_if" not in out:
        pred = expr_to_predicate(vw)
        if pred and "raw" not in pred:
            out["show_if"] = pred
        elif pred:
            out["show_if_raw"] = pred.get("raw")

    rw = out.pop("required_when", None)
    if rw is None:
        rw = out.get("required_if")
    if isinstance(rw, str):
        pred = expr_to_predicate(rw)
        if pred and "raw" not in pred:
            out["required_if"] = pred
        elif pred:
            out["required_if_raw"] = pred.get("raw")
            out.pop("required_if", None)

    # انتشار محرمانگی/نقش فرم روی فیلد
    if form_confidential and "confidential" not in out:
        out["confidential"] = True
    if isinstance(form_visible_to, list) and form_visible_to and "visible_to" not in out:
        out["visible_to"] = list(form_visible_to)
    return out


def convert_form_schema(form: dict) -> dict:
    """forms[] متادیتا ⇒ schema_json یکپارچه { "fields": [...] }."""
    confidential = bool(form.get("confidential"))
    visible_to = form.get("visible_to")
    fields = form.get("fields") or []
    return {
        "fields": [
            _convert_field(f, confidential, visible_to) if isinstance(f, dict) else f
            for f in fields
        ]
    }


def _audience_for(form: dict) -> str:
    if form.get("confidential"):
        return "operator"
    vis = form.get("visible_to")
    if isinstance(vis, list) and vis and "student" not in vis:
        return "operator"
    return "both"


def _states_for_form(form: dict) -> list[str]:
    raw = form.get("used_in_state")
    states: list[str] = []
    if isinstance(raw, list):
        states = [str(s) for s in raw if s]
    elif raw:
        states = [str(raw)]
    # افزودن stateهای alias (مثلاً documents_review/incomplete برای documents_upload)
    expanded = list(states)
    for st in states:
        for alias in _REVERSE_ALIASES.get(st, []):
            if alias not in expanded:
                expanded.append(alias)
    return expanded


# ─── upsert ها ───────────────────────────────────────────────────


async def _upsert_template(db: AsyncSession, code: str, name_fa: str, audience: str) -> FormTemplate:
    t = (await db.execute(select(FormTemplate).where(FormTemplate.code == code))).scalars().first()
    if t:
        t.name_fa = name_fa or t.name_fa
        t.audience = audience
        return t
    t = FormTemplate(code=code, name_fa=name_fa or code, audience=audience)
    db.add(t)
    await db.flush()
    return t


async def _upsert_version(
    db: AsyncSession,
    template: FormTemplate,
    schema_json: dict,
    process_code: str,
    state_code: Optional[str],
) -> FormTemplateVersion:
    versions = (
        (
            await db.execute(
                select(FormTemplateVersion)
                .where(FormTemplateVersion.template_id == template.id)
                .order_by(FormTemplateVersion.version.desc())
            )
        )
        .scalars()
        .all()
    )
    latest = versions[0] if versions else None
    if latest and json.dumps(latest.schema_json, sort_keys=True, ensure_ascii=False) == json.dumps(
        schema_json, sort_keys=True, ensure_ascii=False
    ):
        # بدون تغییر — همان نسخه
        if not latest.published_at:
            latest.published_at = datetime.now(timezone.utc)
        latest.source = "metadata"
        latest.process_code = process_code
        latest.state_code = state_code
        return latest
    next_v = (latest.version + 1) if latest else 1
    v = FormTemplateVersion(
        template_id=template.id,
        version=next_v,
        schema_json=schema_json,
        published_at=datetime.now(timezone.utc),
        source="metadata",
        process_code=process_code,
        state_code=state_code,
    )
    db.add(v)
    await db.flush()
    return v


async def _upsert_assignment(
    db: AsyncSession,
    template: FormTemplate,
    version: FormTemplateVersion,
    process_code: str,
    state_code: str,
    context_key: str,
    sort_order: int,
    submit_label_fa: Optional[str],
    header_fa: Optional[str],
) -> None:
    a = (
        await db.execute(
            select(FormAssignment).where(
                FormAssignment.assignment_type == "process",
                FormAssignment.process_code == process_code,
                FormAssignment.state_code == state_code,
                FormAssignment.template_id == template.id,
            )
        )
    ).scalars().first()
    if a:
        a.template_version_id = version.id
        a.context_key = context_key
        a.sort_order = sort_order
        a.submit_label_fa = submit_label_fa
        a.header_fa = header_fa
        a.active = True
        return
    db.add(
        FormAssignment(
            template_id=template.id,
            template_version_id=version.id,
            assignment_type="process",
            process_code=process_code,
            state_code=state_code,
            context_key=context_key,
            sort_order=sort_order,
            submit_label_fa=submit_label_fa,
            header_fa=header_fa,
            active=True,
        )
    )


async def import_process_file(db: AsyncSession, path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"forms": 0, "assignments": 0}
    process_code = (data.get("process") or {}).get("code") or path.stem
    forms = data.get("forms") or []
    n_forms = 0
    n_assign = 0
    for idx, form in enumerate(forms):
        if not isinstance(form, dict):
            continue
        fields = form.get("fields")
        if not isinstance(fields, list):
            continue  # داشبورد/بدون فیلد را رد کن
        form_code = form.get("code") or f"form_{idx}"
        tmpl_code = f"{process_code}:{form_code}"
        schema_json = convert_form_schema(form)
        template = await _upsert_template(
            db, tmpl_code, form.get("name_fa") or form_code, _audience_for(form)
        )
        states = _states_for_form(form)
        version = await _upsert_version(
            db, template, schema_json, process_code, states[0] if states else None
        )
        for st in states:
            await _upsert_assignment(
                db,
                template,
                version,
                process_code,
                st,
                form.get("context_key") or form_code,
                idx,
                form.get("submit_label_fa"),
                form.get("header_fa") or form.get("name_fa"),
            )
            n_assign += 1
        n_forms += 1
    return {"forms": n_forms, "assignments": n_assign}


async def import_all_metadata_forms(db: AsyncSession) -> dict:
    """همهٔ فرایندها را وارد می‌کند. caller باید commit کند."""
    if not METADATA_PROCESSES_DIR.exists():
        return {"processes": 0, "forms": 0, "assignments": 0}
    n_proc = n_forms = n_assign = 0
    for pf in sorted(METADATA_PROCESSES_DIR.glob("*.json")):
        res = await import_process_file(db, pf)
        if res["forms"]:
            n_proc += 1
            n_forms += res["forms"]
            n_assign += res["assignments"]
    return {"processes": n_proc, "forms": n_forms, "assignments": n_assign}


# ─── اجرای CLI یک‌باره ───────────────────────────────────────────


async def _main() -> None:
    from app.database import async_session_factory

    async with async_session_factory() as db:
        result = await import_all_metadata_forms(db)
        await db.commit()
        print("imported:", result)


if __name__ == "__main__":
    import asyncio

    asyncio.run(_main())
