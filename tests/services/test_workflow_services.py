"""Tests for the workflow action services (Services A-I).

Each previously log-only stub now performs real, persisted state mutations.
These tests assert the real side effects (not just that an audit event was
logged), via the public ActionHandler dispatch path.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import Student, User, ProcessInstance
from app.services.action_handler import ActionHandler


async def _make_instance(db_session: AsyncSession, student: Student, process_code="p", ctx=None):
    instance = ProcessInstance(
        id=uuid.uuid4(),
        process_code=process_code,
        student_id=student.id,
        current_state_code="s",
        context_data=ctx or {},
    )
    db_session.add(instance)
    await db_session.flush()
    return instance


async def _run(db_session, instance, actions, context=None):
    handler = ActionHandler(db_session)
    results = await handler.handle_actions(actions, instance, context or {})
    await db_session.commit()
    return results


@pytest.mark.asyncio
class TestServiceAPortalNotifications:
    async def test_display_error_message_creates_portal_message(self, db_session, sample_student):
        instance = await _make_instance(db_session, sample_student)
        results = await _run(db_session, instance, [{"type": "display_error_message", "message_fa": "خطا"}])
        assert results[0]["success"] is True
        await db_session.refresh(sample_student)
        msgs = (sample_student.extra_data or {}).get("portal_messages") or []
        assert msgs and msgs[-1]["kind"] == "error" and msgs[-1]["text_fa"] == "خطا"

    async def test_schedule_installment_reminders_creates_records(self, db_session, sample_student):
        from datetime import date, datetime

        instance = await _make_instance(
            db_session,
            sample_student,
            ctx={
                "payment_method": "installment",
                "installment_count": 4,
                "pending_installments_remaining": 3,
            },
        )
        await _run(db_session, instance, [{"type": "schedule_installment_reminders", "installments": 4}])
        await db_session.refresh(sample_student)
        rems = [r for r in (sample_student.extra_data or {}).get("scheduled_reminders", []) if r["type"] == "installment"]
        assert len(rems) == 4
        assert all(r.get("installment_due_at") for r in rems)
        # SOP: یک هفته قبل از سررسید
        for r in rems:
            due_raw = r["installment_due_at"]
            remind_raw = r["due_at"]
            if len(due_raw) <= 10:
                due_d = date.fromisoformat(due_raw[:10])
            else:
                due_d = datetime.fromisoformat(due_raw.replace("Z", "+00:00")).date()
            remind_d = datetime.fromisoformat(remind_raw.replace("Z", "+00:00")).date()
            assert abs((due_d - remind_d).days - 7) <= 1

    async def test_schedule_installment_reminders_skips_cash(self, db_session, sample_student):
        from datetime import date

        instance = await _make_instance(
            db_session,
            sample_student,
            ctx={
                "payment_method": "cash",
                "pending_installments_remaining": 0,
                "installment_plan": [
                    {
                        "index": 1,
                        "amount_rial": 70000,
                        "due_at": date.today().isoformat(),
                        "status": "pending",
                    }
                ],
            },
        )
        extra = dict(sample_student.extra_data or {})
        extra["scheduled_reminders"] = [
            {
                "id": "old-cash",
                "type": "installment",
                "instance_id": str(instance.id),
                "due_at": date.today().isoformat(),
                "sent": False,
            }
        ]
        sample_student.extra_data = extra
        await db_session.flush()
        results = await _run(db_session, instance, [{"type": "schedule_installment_reminders"}])
        await db_session.refresh(sample_student)
        assert results[0]["success"] is True
        assert "skipped_not_installment" in (results[0].get("detail") or "")
        rems = (sample_student.extra_data or {}).get("scheduled_reminders") or []
        unsent = [r for r in rems if r.get("type") == "installment" and not r.get("sent")]
        assert unsent == []

    async def test_send_to_dashboard_appends_feed(self, db_session, sample_student):
        instance = await _make_instance(db_session, sample_student)
        await _run(db_session, instance, [{"type": "send_to_dashboard"}])
        await db_session.refresh(instance)
        assert instance.context_data.get("dashboard_feed")


@pytest.mark.asyncio
class TestServiceBLms:
    async def test_register_courses_enrolls(self, db_session, sample_student):
        instance = await _make_instance(db_session, sample_student)
        await _run(db_session, instance, [{"type": "register_courses_in_portal", "courses": ["c1", "c2"]}])
        await db_session.refresh(sample_student)
        assert set((sample_student.extra_data or {})["lms"]["enrolled_courses"]) == {"c1", "c2"}

    async def test_unlock_therapist_selection_sets_flag(self, db_session, sample_student):
        instance = await _make_instance(db_session, sample_student)
        await _run(db_session, instance, [{"type": "unlock_student_therapist_selection"}])
        await db_session.refresh(sample_student)
        assert sample_student.extra_data["lms"]["access_flags"]["therapist_selection_unlocked"] is True


@pytest.mark.asyncio
class TestServiceCDocuments:
    async def test_generate_then_sign_then_upload_certificate(self, db_session, sample_student):
        instance = await _make_instance(db_session, sample_student)
        await _run(db_session, instance, [
            {"type": "generate_certificate"},
            {"type": "apply_electronic_signature_and_seal"},
            {"type": "upload_certificate_to_portal"},
        ])
        await db_session.refresh(sample_student)
        docs = (sample_student.extra_data or {})["documents"]
        cert = [d for d in docs if d["type"] == "certificate"][-1]
        assert cert["signed"] is True and cert["portal_visible"] is True
        assert cert["body_fa"]

    async def test_generate_term_transcript_has_body(self, db_session, sample_student):
        instance = await _make_instance(db_session, sample_student)
        await _run(db_session, instance, [{"type": "generate_term_transcript"}])
        await db_session.refresh(sample_student)
        doc = (sample_student.extra_data or {})["documents"][-1]
        assert doc["type"] == "term_transcript" and "کارنامه" in doc["body_fa"]


@pytest.mark.asyncio
class TestServiceDEvaluation:
    async def test_create_evaluation_task(self, db_session, sample_student):
        instance = await _make_instance(db_session, sample_student)
        await _run(db_session, instance, [{"type": "create_evaluation_task"}])
        await db_session.refresh(sample_student)
        tasks = (sample_student.extra_data or {})["tasks"]
        assert tasks and tasks[-1]["kind"] == "evaluation" and tasks[-1]["status"] == "open"

    async def test_add_ta_score(self, db_session, sample_student):
        instance = await _make_instance(db_session, sample_student)
        await _run(db_session, instance, [{"type": "add_ta_score", "ta_score": 18}])
        await db_session.refresh(sample_student)
        evals = (sample_student.extra_data or {})["evaluations"]
        assert any(e.get("type") == "ta_score" and e.get("score") == 18 for e in evals)


@pytest.mark.asyncio
class TestServiceECapacity:
    async def test_increase_intern_capacity(self, db_session, sample_student):
        instance = await _make_instance(db_session, sample_student)
        await _run(db_session, instance, [{"type": "increase_intern_capacity", "amount": 3}])
        await db_session.refresh(sample_student)
        assert sample_student.extra_data["capacity"]["intern_capacity"] == 3

    async def test_move_to_past_lists(self, db_session, sample_student):
        instance = await _make_instance(db_session, sample_student)
        await _run(db_session, instance, [{"type": "move_to_past_lists"}])
        await db_session.refresh(sample_student)
        assert sample_student.extra_data["therapist_assignment"] == "past_list"
        assert sample_student.extra_data["supervisor_assignment"] == "past_list"


@pytest.mark.asyncio
class TestServiceITermination:
    async def test_record_termination_date_and_accounting(self, db_session, sample_student):
        instance = await _make_instance(db_session, sample_student)
        await _run(db_session, instance, [
            {"type": "record_termination_date", "termination_date": "2026-01-15"},
            {"type": "record_accounting", "amount": 1500000, "kind": "refund"},
        ])
        await db_session.refresh(sample_student)
        extra = sample_student.extra_data
        assert extra["termination"]["date"] == "2026-01-15"
        assert extra["accounting_entries"][-1]["amount"] == 1500000.0


@pytest.mark.asyncio
class TestServiceFCalendar:
    async def test_apply_24h_rule_sets_calculated_start_date(self, db_session, sample_student):
        instance = await _make_instance(db_session, sample_student)
        await _run(db_session, instance, [{"type": "apply_24h_rule_for_start_date"}])
        await db_session.refresh(instance)
        assert instance.context_data.get("calculated_start_date")
        assert instance.context_data.get("start_date_rule") == "24h"

    async def test_record_interruption_dates(self, db_session, sample_student):
        instance = await _make_instance(db_session, sample_student)
        await _run(db_session, instance, [
            {"type": "record_interruption_dates", "interruption_start_date": "2026-02-01", "interruption_end_date": "2026-03-01"},
        ])
        await db_session.refresh(sample_student)
        ints = sample_student.extra_data["interruptions"]
        assert ints[-1]["start"] == "2026-02-01" and ints[-1]["end"] == "2026-03-01"


@pytest.mark.asyncio
class TestServiceGGate:
    async def test_block_then_unblock_next_term(self, db_session, sample_student):
        instance = await _make_instance(db_session, sample_student)
        await _run(db_session, instance, [{"type": "block_next_term_registration"}])
        await db_session.refresh(sample_student)
        assert sample_student.extra_data["gates"]["next_term_registration_blocked"] is True
        await _run(db_session, instance, [{"type": "unblock_next_term_registration"}])
        await db_session.refresh(sample_student)
        assert sample_student.extra_data["gates"]["next_term_registration_blocked"] is False


@pytest.mark.asyncio
class TestServiceHRole:
    async def test_move_ta_to_instructor_changes_user_role(self, db_session, sample_student):
        instance = await _make_instance(db_session, sample_student)
        await _run(db_session, instance, [{"type": "move_ta_to_instructor"}])
        user = await db_session.get(User, sample_student.user_id)
        await db_session.refresh(user)
        assert user.role == "instructor"
        await db_session.refresh(sample_student)
        assert sample_student.extra_data["rank"] == "instructor"

    async def test_revoke_student_access_deactivates_user(self, db_session, sample_student):
        instance = await _make_instance(db_session, sample_student)
        await _run(db_session, instance, [{"type": "revoke_student_access"}])
        user = await db_session.get(User, sample_student.user_id)
        await db_session.refresh(user)
        assert user.is_active is False
        await db_session.refresh(sample_student)
        assert sample_student.extra_data["access_revoked"] is True
