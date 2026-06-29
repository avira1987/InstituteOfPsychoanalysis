"""زنجیرهٔ خودکار فرایند ۷۲ — انتشار لیست بیماران پس از ثبت شرایط ارجاع."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.core.engine import StateMachineEngine
from app.models.operational_models import ProcessInstance, User

logger = logging.getLogger(__name__)


async def _resolve_system_actor_id(db) -> uuid.UUID:
    r = await db.execute(select(User.id).where(User.role == "admin").limit(1))
    row = r.scalars().first()
    if row:
        return row
    r = await db.execute(select(User.id).limit(1))
    row = r.scalars().first()
    return row if row else uuid.uuid4()


def _normalize_patient_rows(rows: list) -> list[dict]:
    out: list[dict] = []
    for i, row in enumerate(rows or []):
        if not isinstance(row, dict):
            continue
        name = str(row.get("patient_name") or "").strip()
        if not name:
            continue
        rid = str(row.get("row_id") or f"row-{i + 1}")
        out.append({
            "row_id": rid,
            "patient_name": name,
            "patient_phone": str(row.get("patient_phone") or "").strip(),
            "contacted": bool(row.get("contacted")),
            "contact_notes": str(row.get("contact_notes") or "").strip(),
            "committee_contacted": bool(row.get("committee_contacted")),
            "referral_notes": str(row.get("referral_notes") or "").strip(),
            "replacement_therapist": str(row.get("replacement_therapist") or "").strip(),
            "followup_done": bool(row.get("followup_done")),
        })
    return out


def merge_referral_payload_into_context(instance: ProcessInstance, payload: dict | None) -> None:
    """پس از ثبت فرم نظارت، ردیف‌ها و مهر زمان را در context ذخیره کن."""
    p = payload if isinstance(payload, dict) else {}
    ctx = dict(StateMachineEngine._as_mapping(instance.context_data))
    rows = _normalize_patient_rows(p.get("patient_referral_rows") or ctx.get("patient_referral_rows"))
    if rows:
        ctx["patient_referral_rows"] = rows
    for key in ("meeting_datetime", "meeting_held", "referral_conditions"):
        if key in p:
            ctx[key] = p[key]
    if p.get("meeting_and_conditions_logged") or rows:
        ctx.setdefault(
            "referral_conditions_set_at",
            datetime.now(timezone.utc).isoformat(),
        )
    instance.context_data = ctx
    flag_modified(instance, "context_data")


async def chain_intern_bulk_referral_after_transition(
    db,
    engine: StateMachineEngine,
    instance: ProcessInstance,
    to_state: str,
    actor_id: uuid.UUID,
    payload: dict | None = None,
) -> None:
    if instance.process_code != "intern_bulk_patient_referral":
        return
    if instance.is_completed or instance.is_cancelled:
        return

    if to_state == "referral_conditions_set":
        merge_referral_payload_into_context(instance, payload)
        ctx = dict(StateMachineEngine._as_mapping(instance.context_data))
        if not ctx.get("student_patient_log_entered_at"):
            ctx["student_patient_log_entered_at"] = datetime.now(timezone.utc).isoformat()
        instance.context_data = ctx
        flag_modified(instance, "context_data")

        sys_id = await _resolve_system_actor_id(db)
        result = await engine.execute_transition(
            instance.id,
            "patient_list_published",
            sys_id,
            "system",
            None,
        )
        if not result.success:
            logger.warning(
                "intern_bulk_patient_referral patient_list_published failed instance=%s: %s",
                instance.id,
                result.error,
            )
        return

    if to_state == "student_patient_log" and payload:
        ctx = dict(StateMachineEngine._as_mapping(instance.context_data))
        rows = _normalize_patient_rows(payload.get("patient_referral_rows"))
        if rows:
            ctx["patient_referral_rows"] = rows
        ctx.setdefault(
            "student_patient_log_entered_at",
            datetime.now(timezone.utc).isoformat(),
        )
        instance.context_data = ctx
        flag_modified(instance, "context_data")

    if to_state == "general_therapy_committee_review":
        ctx = dict(StateMachineEngine._as_mapping(instance.context_data))
        ctx.setdefault(
            "general_therapy_committee_review_entered_at",
            datetime.now(timezone.utc).isoformat(),
        )
        instance.context_data = ctx
        flag_modified(instance, "context_data")

    if to_state == "coordination_followup":
        ctx = dict(StateMachineEngine._as_mapping(instance.context_data))
        if payload:
            rows = _normalize_patient_rows(payload.get("patient_referral_rows"))
            if rows:
                ctx["patient_referral_rows"] = rows
        ctx.setdefault(
            "coordination_followup_entered_at",
            datetime.now(timezone.utc).isoformat(),
        )
        instance.context_data = ctx
        flag_modified(instance, "context_data")
