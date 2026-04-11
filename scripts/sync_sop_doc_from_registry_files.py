#!/usr/bin/env python3
"""
همگام‌سازی متن و تصویر SOP از پوشهٔ رجیستری به جدول process_definitions.

فایل‌ها (نسبت به ریشهٔ مخزن):
  metadata/process_registry/processes/{code}/SOP_document.txt
  metadata/process_registry/processes/{code}/SOP_flowchart.png  (اختیاری)

پیش‌فرض sop_order در config (در صورت نبود): educational_leave=1، start_therapy=2، therapy_changes=3، extra_session=4، session_payment=5، attendance_tracking=6، fee_determination=7، therapy_completion=8، therapy_session_increase=9، therapy_session_reduction=10، therapy_early_termination=11، specialized_commission_review=12، committees_review=13، therapist_session_cancellation=14، unannounced_absence_reaction=15، therapy_interruption=16، student_session_cancellation=17، supervision_block_transition=18، supervision_50h_completion=20، supervision_session_increase=21، extra_supervision_session=22، supervision_session_reduction=24، student_supervision_cancellation=25، supervisor_session_cancellation=26، unannounced_supervision_absence_reaction=27، supervision_interruption=28، fall_semester_preparation=29، winter_semester_preparation=30، introductory_course_registration=31، introductory_term_end=32، intro_second_semester_registration=33، introductory_course_completion=34، comprehensive_course_registration=35، comprehensive_term_end=36، internship_readiness_consultation=37، internship_12month_conditional_review=38، intern_hours_increase=39، comprehensive_term_start=40، lesson_start_per_term=41، student_non_registration=42، ta_conceptual_questions=43، ta_student_consultation=44، ta_essay_upload=45، ta_blog_content=46، upgrade_to_ta=47، mentor_private_sessions=48، ta_to_assistant_faculty=49، ta_to_instructor_auto=50، ta_track_change=51، ta_track_completion=52، ta_instructor_leave=53، class_attendance=54، violation_registration=55، class_session_cancellation=56، student_instructor_evaluation=57، process_merged_to_one=58، full_education_leave=59، return_to_full_education=60، theory_course_completion=61، group_supervision_course_completion=62، skills_course_completion=63، film_observation_course_completion=64، live_therapy_observation_course_completion=65، live_therapy_observation_session_prep=66، live_supervision_course_completion=67، live_supervision_session_prep=68، article_writing_completion=69، thesis_defense_request=70، upgrade_to_educational_therapist=71، intern_bulk_patient_referral=72، live_supervision_ta_evaluation=73، live_therapy_observation_ta_attendance_completion=74، film_observation_ta_attendance_completion=75 (مطابق INDEX/SOP).

اجرا (با DATABASE_URL معتبر، مثلاً داخل کانتینر api):
  python scripts/sync_sop_doc_from_registry_files.py
  python scripts/sync_sop_doc_from_registry_files.py --code start_therapy --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.database import async_session_factory
from app.models.meta_models import ProcessDefinition


def _merge_sop_order(cfg: dict | None, order: int) -> dict:
    out = dict(cfg) if isinstance(cfg, dict) else {}
    out.setdefault("sop_order", order)
    return out


# هم‌راستا با metadata/process_registry/INDEX و app/meta/sop_registry
_DEFAULT_SOP_ORDER_BY_CODE: dict[str, int] = {
    "educational_leave": 1,
    "start_therapy": 2,
    "therapy_changes": 3,
    "extra_session": 4,
    "session_payment": 5,
    "attendance_tracking": 6,
    "fee_determination": 7,
    "therapy_completion": 8,
    "therapy_session_increase": 9,
    "therapy_session_reduction": 10,
    "therapy_early_termination": 11,
    "specialized_commission_review": 12,
    "committees_review": 13,
    "therapist_session_cancellation": 14,
    "unannounced_absence_reaction": 15,
    "therapy_interruption": 16,
    "student_session_cancellation": 17,
    "supervision_block_transition": 18,
    "supervision_50h_completion": 20,
    "supervision_session_increase": 21,
    "extra_supervision_session": 22,
    "supervision_session_reduction": 24,
    "student_supervision_cancellation": 25,
    "supervisor_session_cancellation": 26,
    "unannounced_supervision_absence_reaction": 27,
    "supervision_interruption": 28,
    "fall_semester_preparation": 29,
    "winter_semester_preparation": 30,
    "introductory_course_registration": 31,
    "introductory_term_end": 32,
    "intro_second_semester_registration": 33,
    "introductory_course_completion": 34,
    "comprehensive_course_registration": 35,
    "comprehensive_term_end": 36,
    "internship_readiness_consultation": 37,
    "internship_12month_conditional_review": 38,
    "intern_hours_increase": 39,
    "comprehensive_term_start": 40,
    "lesson_start_per_term": 41,
    "student_non_registration": 42,
    "ta_conceptual_questions": 43,
    "ta_student_consultation": 44,
    "ta_essay_upload": 45,
    "ta_blog_content": 46,
    "upgrade_to_ta": 47,
    "mentor_private_sessions": 48,
    "ta_to_assistant_faculty": 49,
    "ta_to_instructor_auto": 50,
    "ta_track_change": 51,
    "ta_track_completion": 52,
    "ta_instructor_leave": 53,
    "class_attendance": 54,
    "violation_registration": 55,
    "class_session_cancellation": 56,
    "student_instructor_evaluation": 57,
    "process_merged_to_one": 58,
    "full_education_leave": 59,
    "return_to_full_education": 60,
    "theory_course_completion": 61,
    "group_supervision_course_completion": 62,
    "skills_course_completion": 63,
    "film_observation_course_completion": 64,
    "live_therapy_observation_course_completion": 65,
    "live_therapy_observation_session_prep": 66,
    "live_supervision_course_completion": 67,
    "live_supervision_session_prep": 68,
    "article_writing_completion": 69,
    "thesis_defense_request": 70,
    "upgrade_to_educational_therapist": 71,
    "intern_bulk_patient_referral": 72,
    "live_supervision_ta_evaluation": 73,
    "live_therapy_observation_ta_attendance_completion": 74,
    "film_observation_ta_attendance_completion": 75,
}


async def run(*, code: str, dry_run: bool, sop_order: int | None = None) -> int:
    base = os.path.join(ROOT, "metadata", "process_registry", "processes", code)
    text_path = os.path.join(base, "SOP_document.txt")
    img_path = os.path.join(base, "SOP_flowchart.png")

    if not os.path.isfile(text_path):
        print(f"خطا: فایل متن یافت نشد: {text_path}", file=sys.stderr)
        return 1

    text = open(text_path, encoding="utf-8").read()
    img_bytes: bytes | None = None
    content_type: str | None = None
    if os.path.isfile(img_path):
        img_bytes = open(img_path, "rb").read()
        lower = img_path.lower()
        if lower.endswith(".png"):
            content_type = "image/png"
        elif lower.endswith(".jpg") or lower.endswith(".jpeg"):
            content_type = "image/jpeg"
        elif lower.endswith(".webp"):
            content_type = "image/webp"
        elif lower.endswith(".gif"):
            content_type = "image/gif"
        else:
            content_type = "image/png"

    print(f"code={code}")
    print(f"text: {text_path} ({len(text)} chars)")
    print(f"image: {img_path} ({len(img_bytes) if img_bytes else 0} bytes)")

    if dry_run:
        print("dry-run: بدون تغییر در دیتابیس")
        return 0

    async with async_session_factory() as session:
        r = await session.execute(select(ProcessDefinition).where(ProcessDefinition.code == code))
        p = r.scalar_one_or_none()
        if p is None:
            print(f"خطا: فرایندی با code={code!r} در دیتابیس نیست. ابتدا متادیتا را sync کنید.", file=sys.stderr)
            return 1

        p.source_text = text
        if img_bytes is not None:
            p.flowchart_image = img_bytes
            p.flowchart_content_type = content_type
        if sop_order is not None:
            p.config = _merge_sop_order(p.config, sop_order)
            flag_modified(p, "config")
        p.version = (p.version or 1) + 1
        await session.commit()
        print(f"به‌روز شد: {p.name_fa} (id={p.id}, version={p.version})")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", default="educational_leave", help="کد فرایند در DB")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--sop-order",
        type=int,
        default=None,
        help="در صورت ارسال، sop_order در config درج می‌شود؛ وگرنه از نگاشت پیش‌فرض فرایند",
    )
    args = ap.parse_args()
    sop = args.sop_order
    if sop is None:
        sop = _DEFAULT_SOP_ORDER_BY_CODE.get(args.code)
    rc = asyncio.run(run(code=args.code, dry_run=args.dry_run, sop_order=sop))
    sys.exit(rc)


if __name__ == "__main__":
    main()
