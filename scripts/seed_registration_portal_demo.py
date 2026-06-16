#!/usr/bin/env python3
"""
دمو مسیر ثبت‌نام (آشنایی / جامع): اسلات مصاحبه، پر کردن مبلغ پرداخت در context،
و در صورت --matrix ساخت کاربران regdemo_* با یک نمونه فرایند در هر وضعیت نمایشی.

اجرا از ریشهٔ ریپو:
  python scripts/seed_registration_portal_demo.py
  python scripts/seed_registration_portal_demo.py --matrix

رمز همهٔ کاربران ساخته‌شده: demo123 (مگر با DEMO_REG_PASSWORD)
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, str(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm.attributes import flag_modified

try:
    from app.config import get_settings

    DATABASE_URL = get_settings().DATABASE_URL
except Exception:
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://anistito:anistito@localhost:5432/anistito",
    )

DEMO_PASSWORD = os.getenv("DEMO_REG_PASSWORD", "demo123")

INTRO_PC = "introductory_course_registration"
COMP_PC = "comprehensive_course_registration"

INTRO_TERMINAL = frozenset({"rejected", "registration_complete"})
COMP_TERMINAL = frozenset(
    {
        "supervision_rejected",
        "scientific_rejected",
        "result_rejected",
        "result_rejected_with_suggestion",
        "registration_complete",
    }
)

# (username, process_code, course_type on Student, state_code, extra_context)
DEMO_MATRIX: Sequence[Tuple[str, str, str, str, Dict[str, Any]]] = (
    # introductory — پوشش UI کارت مسیر، اسلات، پرداخت، منتظر مرکز، مدارک، شهریه
    ("regdemo_intro_app", INTRO_PC, "introductory", "application_submitted", {}),
    ("regdemo_intro_sched", INTRO_PC, "introductory", "interview_scheduled", {}),
    ("regdemo_intro_ipay", INTRO_PC, "introductory", "interview_payment", {}),
    ("regdemo_intro_ipay_ok", INTRO_PC, "introductory", "interview_payment_confirmed", {}),
    ("regdemo_intro_done_iv", INTRO_PC, "introductory", "interview_completed", {}),
    ("regdemo_intro_res_therapy", INTRO_PC, "introductory", "result_conditional_therapy", {}),
    ("regdemo_intro_res_single", INTRO_PC, "introductory", "result_single_course", {}),
    ("regdemo_intro_res_full", INTRO_PC, "introductory", "result_full_admission", {}),
    ("regdemo_intro_docs_up", INTRO_PC, "introductory", "documents_upload", {}),
    ("regdemo_intro_docs_rev", INTRO_PC, "introductory", "documents_review", {}),
    ("regdemo_intro_docs_bad", INTRO_PC, "introductory", "documents_incomplete", {"__documents_resubmit_fields": ["national_card_scan"]}),
    ("regdemo_intro_cred", INTRO_PC, "introductory", "credentials_created", {}),
    ("regdemo_intro_courses", INTRO_PC, "introductory", "course_selection", {"allowed_course_count": 5, "admission_type": "full"}),
    ("regdemo_intro_pay", INTRO_PC, "introductory", "payment", {}),
    ("regdemo_intro_done", INTRO_PC, "introductory", "registration_complete", {}),
    ("regdemo_intro_reject", INTRO_PC, "introductory", "rejected", {}),
    ("regdemo_intro_inst_ov", INTRO_PC, "introductory", "installment_overdue", {"overdue_installment_index": 2}),
    # comprehensive
    ("regdemo_comp_app", COMP_PC, "comprehensive", "application_submitted", {}),
    ("regdemo_comp_sup", COMP_PC, "comprehensive", "supervision_committee_review", {}),
    ("regdemo_comp_exec", COMP_PC, "comprehensive", "executive_review", {}),
    ("regdemo_comp_sci", COMP_PC, "comprehensive", "scientific_review", {}),
    ("regdemo_comp_doc", COMP_PC, "comprehensive", "document_upload", {}),
    ("regdemo_comp_sched", COMP_PC, "comprehensive", "interview_scheduled", {}),
    ("regdemo_comp_ipay", COMP_PC, "comprehensive", "interview_payment", {}),
    ("regdemo_comp_iv_done", COMP_PC, "comprehensive", "interview_completed", {}),
    ("regdemo_comp_accept", COMP_PC, "comprehensive", "result_accepted", {}),
    ("regdemo_comp_courses", COMP_PC, "comprehensive", "course_display", {}),
    ("regdemo_comp_pay", COMP_PC, "comprehensive", "payment", {}),
    ("regdemo_comp_done", COMP_PC, "comprehensive", "registration_complete", {}),
    ("regdemo_comp_rej_sup", COMP_PC, "comprehensive", "supervision_rejected", {}),
    ("regdemo_comp_rej_sci", COMP_PC, "comprehensive", "scientific_rejected", {}),
    ("regdemo_comp_rej", COMP_PC, "comprehensive", "result_rejected", {}),
    ("regdemo_comp_rej_sug", COMP_PC, "comprehensive", "result_rejected_with_suggestion", {}),
)


def _hash_pw(password: str) -> str:
    import bcrypt

    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _terminal_for(process_code: str, state: str) -> bool:
    if process_code == INTRO_PC:
        return state in INTRO_TERMINAL
    if process_code == COMP_PC:
        return state in COMP_TERMINAL
    return False


async def _get_admin_actor_id(db: AsyncSession) -> uuid.UUID:
    from app.models.operational_models import User

    r = await db.execute(select(User).where(User.username == "admin"))
    u = r.scalars().first()
    if not u:
        raise RuntimeError("کاربر admin یافت نشد؛ ابتدا scripts/seed_demo_users.py را اجرا کنید.")
    return u.id


async def seed_interview_slots(db: AsyncSession, min_free: int = 8) -> int:
    """اسلات‌های آزاد آینده؛ در صورت کمبود، ردیف جدید اضافه می‌کند."""
    from app.models.operational_models import InterviewSlot

    now = datetime.now(timezone.utc)
    stmt = (
        select(func.count())
        .select_from(InterviewSlot)
        .where(
            InterviewSlot.starts_at > now,
            InterviewSlot.assigned_student_id.is_(None),
        )
    )
    n = int((await db.execute(stmt)).scalar() or 0)
    if n >= min_free:
        return 0

    added = 0
    base = now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
    course_cycle: List[Optional[str]] = ["introductory", "comprehensive", None]
    modes = ["in_person", "online"]
    locs = ["ساختمان مرکزی — اتاق ۳۰۲", None]
    for i in range(min_free - n + 4):
        starts = base + timedelta(days=i // 2, hours=(i % 2) * 3)
        ends = starts + timedelta(hours=1)
        ct = course_cycle[i % len(course_cycle)]
        mode = modes[i % 2]
        loc = locs[i % 2]
        slot = InterviewSlot(
            id=uuid.uuid4(),
            starts_at=starts,
            ends_at=ends,
            course_type=ct,
            mode=mode,
            location_fa=loc,
            meeting_link="https://meet.example.edu/demo" if mode == "online" else None,
            label_fa=f"دمو — {'آشنایی' if ct == 'introductory' else 'جامع' if ct == 'comprehensive' else 'عمومی'}",
        )
        db.add(slot)
        added += 1
    return added


async def backfill_registration_payment_amounts(db: AsyncSession) -> int:
    from app.core.engine import StateMachineEngine
    from app.models.operational_models import ProcessInstance

    engine = StateMachineEngine(db)
    stmt = select(ProcessInstance).where(
        ProcessInstance.process_code.in_((INTRO_PC, COMP_PC)),
        ProcessInstance.current_state_code.in_(("interview_payment", "payment")),
        ProcessInstance.is_completed.is_(False),
        ProcessInstance.is_cancelled.is_(False),
    )
    rows = (await db.execute(stmt)).scalars().all()
    touched = 0
    for inst in rows:
        if await engine.persist_registration_payment_defaults_if_needed(inst):
            touched += 1
    return touched


def _merge_ctx(base: Optional[dict], extra: Dict[str, Any]) -> dict:
    out = dict(base or {})
    out.update(extra)
    return out


async def _ensure_user_student(
    db: AsyncSession,
    username: str,
    full_name_fa: str,
    course_type: str,
    student_code: str,
) -> Tuple[Any, Any]:
    from app.models.operational_models import Student, User

    r = await db.execute(select(User).where(User.username == username))
    user = r.scalars().first()
    hp = _hash_pw(DEMO_PASSWORD)
    if user:
        user.full_name_fa = full_name_fa
        user.role = "student"
        user.hashed_password = hp
        user.is_active = True
    else:
        user = User(
            id=uuid.uuid4(),
            username=username,
            email=f"{username}@regdemo.local",
            hashed_password=hp,
            full_name_fa=full_name_fa,
            role="student",
            is_active=True,
        )
        db.add(user)
        await db.flush()

    r2 = await db.execute(select(Student).where(Student.user_id == user.id))
    st = r2.scalars().first()
    if st:
        st.student_code = student_code
        st.course_type = course_type
        st.term_count = max(st.term_count or 1, 1)
        st.current_term = st.current_term or 1
        st.weekly_sessions = st.weekly_sessions or 2
    else:
        st = Student(
            id=uuid.uuid4(),
            user_id=user.id,
            student_code=student_code,
            course_type=course_type,
            weekly_sessions=2,
            term_count=4,
            current_term=1,
            therapy_started=(course_type == "comprehensive"),
        )
        db.add(st)
        await db.flush()
    return user, st


async def _set_primary_instance(student: Any, instance_id: uuid.UUID) -> None:
    extra = dict(student.extra_data or {})
    extra["primary_instance_id"] = str(instance_id)
    student.extra_data = extra
    flag_modified(student, "extra_data")


async def ensure_instance_at_state(
    db: AsyncSession,
    engine: Any,
    actor_id: uuid.UUID,
    student: Any,
    process_code: str,
    target_state: str,
    extra_ctx: Dict[str, Any],
) -> Any:
    from app.models.operational_models import ProcessInstance

    stmt = (
        select(ProcessInstance)
        .where(
            ProcessInstance.student_id == student.id,
            ProcessInstance.process_code == process_code,
        )
        .order_by(ProcessInstance.started_at.desc())
    )
    rows = list((await db.execute(stmt)).scalars().all())
    active = [x for x in rows if not x.is_completed and not x.is_cancelled]
    if active:
        inst = active[0]
    else:
        inst = await engine.start_process(
            process_code=process_code,
            student_id=student.id,
            actor_id=actor_id,
            actor_role="student" if process_code == COMP_PC else "applicant",
            initial_context={},
        )
        await db.flush()

    inst.current_state_code = target_state
    terminal = _terminal_for(process_code, target_state)
    inst.is_completed = terminal
    if terminal and not inst.completed_at:
        inst.completed_at = datetime.now(timezone.utc)
    if not terminal:
        inst.is_completed = False
        inst.completed_at = None

    merged = _merge_ctx(inst.context_data, extra_ctx)
    inst.context_data = merged
    flag_modified(inst, "context_data")
    await engine.persist_registration_payment_defaults_if_needed(inst)
    await _set_primary_instance(student, inst.id)
    return inst


async def run_matrix(db: AsyncSession) -> None:
    from app.core.engine import StateMachineEngine

    actor_id = await _get_admin_actor_id(db)
    engine = StateMachineEngine(db)
    for i, row in enumerate(DEMO_MATRIX):
        username, pc, course_type, state, extra = row
        label = state.replace("_", " ")
        full_name = f"دمو {label[:24]}"
        code = f"REGD-{(i+1):03d}"
        _, st = await _ensure_user_student(db, username, full_name, course_type, code)
        await ensure_instance_at_state(db, engine, actor_id, st, pc, state, extra)
        print(f"  [matrix] {username} -> {pc} / {state}")


async def main() -> int:
    parser = argparse.ArgumentParser(description="Seed registration portal demo data")
    parser.add_argument(
        "--matrix",
        action="store_true",
        help="ساخت کاربران regdemo_* با وضعیت‌های نمایشی (برای دیدن همهٔ حالت‌های UI)",
    )
    parser.add_argument(
        "--skip-slots",
        action="store_true",
        help="عدم افزودن اسلات مصاحبه",
    )
    parser.add_argument(
        "--skip-backfill",
        action="store_true",
        help="عدم backfill مبلغ پرداخت روی نمونه‌های موجود",
    )
    args = parser.parse_args()

    print("Connecting...")
    eng = create_async_engine(DATABASE_URL)
    factory = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)

    async with factory() as db:
        try:
            await db.execute(text("SELECT 1 FROM process_instances LIMIT 1"))
        except Exception as e:
            print(f"DB error: {e}")
            await eng.dispose()
            return 1

        if not args.skip_slots:
            n_slots = await seed_interview_slots(db)
            print(f"Interview slots added: {n_slots}")
        if not args.skip_backfill:
            n_bf = await backfill_registration_payment_amounts(db)
            print(f"Registration payment context backfilled (instances updated): {n_bf}")

        if args.matrix:
            print("Applying demo state matrix (regdemo_* users)...")
            await run_matrix(db)

        await db.commit()

    await eng.dispose()
    print("Done.")
    if args.matrix:
        print(f"Log in as any regdemo_* / {DEMO_PASSWORD} to browse each scenario.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
