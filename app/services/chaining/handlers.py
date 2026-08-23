"""Named chaining handlers referenced by `metadata/wiring/process_links.json`.

Each handler is a thin adapter: it unpacks a `ChainingContext` and calls the
domain service that owns the behaviour. Matching conditions (process code,
target state, completion) live in the wiring file, not here, and failure
isolation plus instance refetching are handled by the dispatcher.

Service imports are deliberately local to each function to preserve the lazy
import behaviour the engine relied on and to avoid import cycles.
"""

from __future__ import annotations

from app.core.chaining import ChainingContext, chaining_handler

# ─── introductory course registration ───────────────────────────────


@chaining_handler("introductory_registration.chain")
async def introductory_registration_chain(ctx: ChainingContext) -> None:
    from app.services.introductory_registration_chaining import (
        chain_introductory_registration_after_transition,
    )

    await chain_introductory_registration_after_transition(
        ctx.db,
        ctx.engine,
        ctx.instance,
        ctx.to_state,
        ctx.actor_id,
    )


@chaining_handler("student_service.followup_after_intro_registration")
async def followup_after_intro_registration(ctx: ChainingContext) -> None:
    from app.services.student_service import StudentService

    await StudentService(ctx.db).maybe_start_followup_after_intro_registration(ctx.instance)


# ─── term / lesson lifecycle ────────────────────────────────────────


@chaining_handler("introductory_term_end.advance_on_start")
async def introductory_term_end_advance_on_start(ctx: ChainingContext) -> None:
    from app.services.introductory_term_end_chaining import advance_introductory_term_end

    await advance_introductory_term_end(ctx.db, ctx.engine, ctx.instance, ctx.actor_id)


@chaining_handler("lesson_start.chain")
async def lesson_start_chain(ctx: ChainingContext) -> None:
    from app.services.lesson_start_chaining import chain_lesson_start_after_transition

    await chain_lesson_start_after_transition(
        ctx.db,
        ctx.engine,
        ctx.instance,
        ctx.to_state,
        ctx.actor_id,
    )


# ─── therapy ────────────────────────────────────────────────────────


@chaining_handler("therapy_changes.propagate_on_start")
async def therapy_changes_propagate_on_start(ctx: ChainingContext) -> None:
    from app.services.therapy_changes_chaining import propagate_on_therapy_changes_started

    await propagate_on_therapy_changes_started(ctx.db, ctx.instance)


@chaining_handler("therapy_changes.propagate_completed")
async def therapy_changes_propagate_completed(ctx: ChainingContext) -> None:
    from app.services.therapy_changes_chaining import propagate_therapy_changes_completed

    await propagate_therapy_changes_completed(ctx.db, ctx.instance, ctx.to_state)


@chaining_handler("therapy_completion.persist_snapshot")
async def therapy_completion_persist_snapshot(ctx: ChainingContext) -> None:
    await ctx.engine._persist_therapy_completion_snapshot(ctx.instance)


@chaining_handler("student_service.session_payment_after_start_therapy")
async def session_payment_after_start_therapy(ctx: ChainingContext) -> None:
    from app.services.student_service import StudentService

    await StudentService(ctx.db).maybe_start_session_payment_after_start_therapy(ctx.instance)


@chaining_handler("student_service.repoint_primary_after_session_payment")
async def repoint_primary_after_session_payment(ctx: ChainingContext) -> None:
    from app.services.student_service import StudentService

    await StudentService(ctx.db).repoint_primary_after_session_payment_completed(ctx.instance)


@chaining_handler("student_service.repoint_primary_after_therapy_completion")
async def repoint_primary_after_therapy_completion(ctx: ChainingContext) -> None:
    from app.services.student_service import StudentService

    await StudentService(ctx.db).repoint_primary_after_therapy_completion_terminal(ctx.instance)


# ─── leave / return ─────────────────────────────────────────────────


@chaining_handler("full_education_leave.propagate_on_start")
async def full_education_leave_propagate_on_start(ctx: ChainingContext) -> None:
    from app.services.full_education_leave_service import propagate_on_start

    await propagate_on_start(ctx.db, ctx.instance)


@chaining_handler("full_education_leave.maybe_skip_therapist_assignment")
async def full_education_leave_maybe_skip_therapist_assignment(ctx: ChainingContext) -> None:
    from app.services.full_education_leave_service import maybe_skip_therapist_assignment

    await maybe_skip_therapist_assignment(ctx.db, ctx.engine, ctx.instance, ctx.actor_id)


@chaining_handler("return_to_full_education.propagate_on_start")
async def return_to_full_education_propagate_on_start(ctx: ChainingContext) -> None:
    from app.services.return_to_full_education_service import propagate_on_start

    await propagate_on_start(ctx.db, ctx.instance)


@chaining_handler("return_to_full_education.branch_after_therapy_payment")
async def return_to_full_education_branch_after_therapy_payment(ctx: ChainingContext) -> None:
    from app.services.return_to_full_education_service import branch_after_therapy_payment

    await branch_after_therapy_payment(ctx.db, ctx.engine, ctx.instance, ctx.actor_id)


@chaining_handler("return_to_full_education.finalize_registration_unlock")
async def return_to_full_education_finalize_registration_unlock(ctx: ChainingContext) -> None:
    from app.services.return_to_full_education_service import finalize_registration_unlock

    await finalize_registration_unlock(ctx.db, ctx.engine, ctx.instance, ctx.actor_id)


# ─── non-registration hub ───────────────────────────────────────────


@chaining_handler("student_non_registration.chain")
async def student_non_registration_chain(ctx: ChainingContext) -> None:
    from app.services.student_non_registration_chaining import (
        chain_student_non_registration_after_transition,
    )

    await chain_student_non_registration_after_transition(
        ctx.db,
        ctx.engine,
        ctx.instance,
        ctx.to_state,
        ctx.actor_id,
    )


@chaining_handler("student_non_registration.advance_on_leave_start")
async def student_non_registration_advance_on_leave_start(ctx: ChainingContext) -> None:
    from app.services.student_non_registration_chaining import (
        maybe_advance_non_registration_on_leave_start,
    )

    await maybe_advance_non_registration_on_leave_start(
        ctx.db,
        ctx.engine,
        ctx.student_id,
        ctx.process_code,
        ctx.actor_id,
    )


@chaining_handler("student_non_registration.advance_on_term_registration")
async def student_non_registration_advance_on_term_registration(ctx: ChainingContext) -> None:
    from app.services.student_non_registration_chaining import (
        maybe_advance_non_registration_on_term_registration,
    )

    await maybe_advance_non_registration_on_term_registration(
        ctx.db,
        ctx.engine,
        ctx.instance,
        ctx.actor_id,
    )


# ─── internship ─────────────────────────────────────────────────────


@chaining_handler("intern_bulk_patient_referral.chain")
async def intern_bulk_patient_referral_chain(ctx: ChainingContext) -> None:
    from app.services.intern_bulk_patient_referral_chaining import (
        chain_intern_bulk_referral_after_transition,
    )

    await chain_intern_bulk_referral_after_transition(
        ctx.db,
        ctx.engine,
        ctx.instance,
        ctx.to_state,
        ctx.actor_id,
        ctx.payload,
    )


# ─── TA / instructor track ──────────────────────────────────────────


@chaining_handler("ta_track_change.chain")
async def ta_track_change_chain(ctx: ChainingContext) -> None:
    from app.services.ta_track_change_chaining import chain_ta_track_change_after_transition

    await chain_ta_track_change_after_transition(
        ctx.db,
        ctx.engine,
        ctx.instance,
        ctx.to_state,
        ctx.actor_id,
    )


@chaining_handler("ta_to_assistant_faculty.propagate_on_start")
async def ta_to_assistant_faculty_propagate_on_start(ctx: ChainingContext) -> None:
    from app.services.ta_to_assistant_faculty_service import propagate_on_start

    await propagate_on_start(ctx.db, ctx.instance, actor_id=ctx.actor_id)


@chaining_handler("ta_to_assistant_faculty.chain")
async def ta_to_assistant_faculty_chain(ctx: ChainingContext) -> None:
    from app.services.ta_to_assistant_faculty_service import chain_after_transition

    await chain_after_transition(ctx.db, ctx.instance, ctx.to_state)


@chaining_handler("upgrade_to_ta.chain")
async def upgrade_to_ta_chain(ctx: ChainingContext) -> None:
    from app.services.ta_upgrade_service import chain_after_transition

    await chain_after_transition(ctx.db, ctx.instance, ctx.to_state)
