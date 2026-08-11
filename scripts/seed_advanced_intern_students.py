#!/usr/bin/env python3
"""
ایجاد دانشجویان با تگ «انترن پیشرفته» (is_intern=True + extra_data).

رمز پیش‌فرض: demo123
نقش: student

اجرا:
  docker exec -w /app -e PYTHONPATH=/app anistito-api python /app/scripts/seed_advanced_intern_students.py
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

DEFAULT_PASSWORD = "demo123"
ROLE = "student"
TAG_FA = "انترن پیشرفته"

# (username, full_name_fa, student_code) — نام نمایشی با پسوند (درمانگر پیوسته)
ADVANCED_INTERNS: list[tuple[str, str, str]] = [
    ("raheleh_nobakht", "راحله نوبخت (درمانگر پیوسته)", "INT-ADV-001"),
    ("zahra_gharavi", "زهرا غروی (درمانگر پیوسته)", "INT-ADV-002"),
    ("sogand_ghasemi", "سوگند قاسمی (درمانگر پیوسته)", "INT-ADV-003"),
    ("shirin_asghari", "شیرین اصغری (درمانگر پیوسته)", "INT-ADV-004"),
    ("omid_sina", "امید سینا (درمانگر پیوسته)", "INT-ADV-005"),
    ("laya_norouzi", "لعیا نوروزی (درمانگر پیوسته)", "INT-ADV-006"),
    ("miadeh_azizi_moghaddam", "میعاده عزیزی مقدم (درمانگر پیوسته)", "INT-ADV-007"),
    # هانیه پور جبار قبلاً با نقش faculty_1 ثبت شده؛ حساب دانشجویی جدا
    ("hanieh_pourjabar_stu", "هانیه پور جبار (درمانگر پیوسته)", "INT-ADV-008"),
    ("homa_khorasani", "هما خراسانی (درمانگر پیوسته)", "INT-ADV-009"),
    ("elnaz_bahmanzad", "الناز بهمن زاد (درمانگر پیوسته)", "INT-ADV-010"),
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
    extra["intern_kind"] = "advanced"
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

        for username, full_name_fa, student_code in ADVANCED_INTERNS:
            name = _normalize_name(full_name_fa)
            email = f"{username}@student.anistito.local"

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
                # اگر کد دانشجویی تکراری است، با همان کد رکورد قبلی را پیدا کن
                by_code = await db.execute(select(Student).where(Student.student_code == student_code))
                student = by_code.scalars().first()

            if student:
                student.user_id = user.id
                student.student_code = student_code
                student.course_type = "comprehensive"
                student.is_intern = True
                student.therapy_started = True
                student.term_count = max(int(student.term_count or 1), 4)
                student.current_term = max(int(student.current_term or 1), 4)
                student.weekly_sessions = max(int(student.weekly_sessions or 1), 2)
                student.extra_data = _intern_extra(student.extra_data if isinstance(student.extra_data, dict) else {})
                flag_modified(student, "extra_data")
                updated_students += 1
            else:
                db.add(
                    Student(
                        id=uuid.uuid4(),
                        user_id=user.id,
                        student_code=student_code,
                        course_type="comprehensive",
                        is_intern=True,
                        therapy_started=True,
                        term_count=4,
                        current_term=4,
                        weekly_sessions=2,
                        extra_data=_intern_extra(),
                    )
                )
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
