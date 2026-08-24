#!/usr/bin/env python3
"""
ایجاد دانشجویان با تگ «انترن» (is_intern=True + extra_data).
شماره و نام کاربری یکپارچه: STU-1001 به‌بعد (کد قدیمی INT-… در extra_data نگه داشته می‌شود).

رمز پیش‌فرض: demo123
نقش: student

اجرا:
  docker exec -w /app -e PYTHONPATH=/app anistito-api python /app/scripts/seed_intern_students.py
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
import uuid

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, str(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.api.auth import get_password_hash
from app.database import async_session_factory
from app.models.operational_models import Student, User
from app.services.student_identity import (
    find_user_for_password_login,
    next_student_code,
    unify_student_identity,
)

DEFAULT_PASSWORD = "demo123"
ROLE = "student"
TAG_FA = "انترن"

# (username, full_name_fa, student_code) — نام نمایشی با پسوند (انترن)
INTERNS: list[tuple[str, str, str]] = [
    ("azadeh_yousefi", "آزاده یوسفی (انترن)", "INT-001"),
    ("parastoo_nasri", "پرستو نصری (انترن)", "INT-002"),
    ("masoumeh_haji_esfandiyari", "معصومه حاجی اسفندیاری (انترن)", "INT-003"),
    ("hengameh_ekrami", "هنگامه اکرامی (انترن)", "INT-004"),
    ("mobina_hamzavi", "مبینا حمزوی (انترن)", "INT-005"),
    ("mohammad_hosseini", "محمد حسینی (انترن)", "INT-006"),
    ("fereshteh_tanideh_dezh", "فرشته تنیده دژ (انترن)", "INT-007"),
    ("mohsen_haji_mohammadpour", "محسن حاجی محمد پور (انترن)", "INT-008"),
    ("shokoofeh_samyari", "شکوفه سمیاری (انترن)", "INT-009"),
    ("fatemeh_nouri", "فاطمه نوری (انترن)", "INT-010"),
    ("shokoofeh_rouhalamini", "شکوفه روح المینی (انترن)", "INT-011"),
    ("sadaf_kazemi", "صدف کاظمی (انترن)", "INT-012"),
    ("hamideh_kasayian", "حمیده کساییان (انترن)", "INT-013"),
    ("zeynab_eskandari", "زینب اسکندری (انترن)", "INT-014"),
    ("azadeh_dolati", "آزاده دولتی (انترن)", "INT-015"),
    ("reyhaneh_zeinali", "ریحانه زینلی (انترن)", "INT-016"),
    ("ava_hojjat_ansari", "آوا حجت انصاری (انترن)", "INT-017"),
    ("azin_darayan", "آذین دارایان (انترن)", "INT-018"),
]


def _normalize_name(name: str) -> str:
    s = (name or "").strip()
    s = re.sub(r"^(آقای|خانم|دکتر)\s+", "", s)
    s = s.replace("ي", "ی").replace("ك", "ک")
    s = re.sub(r"\s+", " ", s)
    return s


def _intern_extra(existing: dict | None = None) -> dict:
    extra = dict(existing or {})
    tags = list(extra.get("tags") or [])
    if TAG_FA not in tags:
        tags.append(TAG_FA)
    extra["tags"] = tags
    extra["intern_kind"] = "standard"
    extra["intern_label_fa"] = TAG_FA
    extra["conditional_intern"] = False
    return extra


async def main() -> int:
    pwd_hash = get_password_hash(DEFAULT_PASSWORD)

    async with async_session_factory() as db:
        created_users = 0
        updated_users = 0
        created_students = 0
        updated_students = 0

        for username, full_name_fa, legacy_code in INTERNS:
            name = _normalize_name(full_name_fa)
            email = f"{username}@student.anistito.local"

            user = await find_user_for_password_login(db, username)
            if user is None:
                res = await db.execute(select(User).where(User.username == username))
                user = res.scalars().first()
            if user:
                user.full_name_fa = name
                user.email = email
                user.role = ROLE
                user.roles = [ROLE]
                user.is_active = True
                user.hashed_password = pwd_hash
                user.portal_password_plain = DEFAULT_PASSWORD
                updated_users += 1
            else:
                user = User(
                    id=uuid.uuid4(),
                    username=username,
                    email=email,
                    hashed_password=pwd_hash,
                    portal_password_plain=DEFAULT_PASSWORD,
                    full_name_fa=name,
                    role=ROLE,
                    roles=[ROLE],
                    is_active=True,
                )
                db.add(user)
                await db.flush()
                created_users += 1

            st_res = await db.execute(select(Student).where(Student.user_id == user.id))
            student = st_res.scalars().first()
            if student is None:
                by_code = await db.execute(select(Student).where(Student.student_code == legacy_code))
                student = by_code.scalars().first()

            intern_extra = _intern_extra(
                student.extra_data if student and isinstance(student.extra_data, dict) else {}
            )
            intern_extra.setdefault("legacy_username", username)
            intern_extra.setdefault("legacy_student_code", legacy_code)

            if student:
                student.user_id = user.id
                student.course_type = "comprehensive"
                student.is_intern = True
                student.therapy_started = True
                student.term_count = max(int(student.term_count or 1), 3)
                student.current_term = max(int(student.current_term or 1), 3)
                student.weekly_sessions = max(int(student.weekly_sessions or 1), 2)
                student.extra_data = intern_extra
                flag_modified(student, "extra_data")
                await unify_student_identity(db, student, user)
                updated_students += 1
            else:
                student = Student(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    student_code=await next_student_code(db),
                    course_type="comprehensive",
                    is_intern=True,
                    therapy_started=True,
                    term_count=3,
                    current_term=3,
                    weekly_sessions=2,
                    extra_data=intern_extra,
                )
                db.add(student)
                await db.flush()
                await unify_student_identity(db, student, user)
                created_students += 1

        await db.commit()

    print(
        f"done: users_created={created_users} users_updated={updated_users} "
        f"students_created={created_students} students_updated={updated_students} "
        f"password={DEFAULT_PASSWORD} tag={TAG_FA!r}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
