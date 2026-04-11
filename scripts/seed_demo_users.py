#!/usr/bin/env python3
"""
ایجاد کاربران دمو برای تست سیستم.
همه کاربران رمز عبور: demo123

Users:
- admin (موجود) / admin123
- student1, student2, student3 - دانشجو
- therapist1 - درمانگر
- supervisor1 - سوپروایزر
- staff1 … staff10 - کارمندان دفتر (نقش staff)
- site_manager1 - مسئول سایت
- progress_committee1 - کمیته پیشرفت
"""
import asyncio
import os
import sys
import uuid

# Fix Windows console encoding for Persian output
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, str(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

try:
    from app.website_staff_seed import STAFF_EMPLOYEES
except ImportError:
    STAFF_EMPLOYEES = []

try:
    from app.config import get_settings
    DATABASE_URL = get_settings().DATABASE_URL
except Exception:
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://anistito:anistito@localhost:5432/anistito",
    )


def get_password_hash(password: str) -> str:
    import bcrypt
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


DEMO_PASSWORD = "demo123"

if not STAFF_EMPLOYEES:
    raise RuntimeError("STAFF_EMPLOYEES missing: run from repo root so app.website_staff_seed loads")

# (username, full_name_fa, role, email)
DEMO_USERS = [
    ("admin", "مدیر سیستم", "admin", "admin@anistito.ir"),
    ("student1", "علی دانشجو", "student", "student1@anistito.ir"),
    ("student2", "مریم دانشجو", "student", "student2@anistito.ir"),
    ("student3", "رضا دانشجو", "student", "student3@anistito.ir"),
    ("therapist1", "دکتر احمد درمانگر", "therapist", "therapist1@anistito.ir"),
    ("supervisor1", "دکتر زهرا سوپروایزر", "supervisor", "supervisor1@anistito.ir"),
    ("site_manager1", "فاطمه مسئول سایت", "site_manager", "site_manager1@anistito.ir"),
    ("progress_committee1", "حسین کمیته پیشرفت", "progress_committee", "committee1@anistito.ir"),
    *[(u, name, "staff", email) for u, name, email in STAFF_EMPLOYEES],
]

# (username, student_code, course_type, weekly_sessions)
STUDENT_PROFILES = [
    ("student1", "STU-001", "introductory", 2),
    ("student2", "STU-002", "comprehensive", 3),
    ("student3", "STU-003", "introductory", 1),
]


async def main():
    print("Connecting to database...")
    engine = create_async_engine(DATABASE_URL)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        try:
            await db.execute(text("SELECT 1 FROM users LIMIT 1"))
        except Exception as e:
            print(f"Error: users table may not exist. Run alembic upgrade head first. {e}")
            await engine.dispose()
            return 1

        from app.models.operational_models import User, Student

        created = 0
        updated = 0

        for username, full_name_fa, role, email in DEMO_USERS:
            result = await db.execute(select(User).where(User.username == username))
            user = result.scalars().first()

            password = "admin123" if username == "admin" else DEMO_PASSWORD

            if user:
                user.full_name_fa = full_name_fa
                user.email = email
                user.role = role
                user.hashed_password = get_password_hash(password)
                user.is_active = True
                updated += 1
                print(f"  Updated: {username}")
            else:
                user = User(
                    id=uuid.uuid4(),
                    username=username,
                    email=email,
                    hashed_password=get_password_hash(password),
                    full_name_fa=full_name_fa,
                    role=role,
                    is_active=True,
                )
                db.add(user)
                await db.flush()
                created += 1
                print(f"  Created: {username}")

        # Create student profiles
        for username, student_code, course_type, weekly_sessions in STUDENT_PROFILES:
            result = await db.execute(select(User).where(User.username == username))
            user = result.scalars().first()
            if not user:
                continue

            result = await db.execute(select(Student).where(Student.user_id == user.id))
            student = result.scalars().first()

            if student:
                student.student_code = student_code
                student.course_type = course_type
                student.weekly_sessions = weekly_sessions
                student.term_count = 4
                student.current_term = 1
                print(f"  Updated student: {student_code} ({username})")
            else:
                student = Student(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    student_code=student_code,
                    course_type=course_type,
                    weekly_sessions=weekly_sessions,
                    term_count=4,
                    current_term=1,
                    therapy_started=(course_type == "comprehensive"),
                )
                db.add(student)
                print(f"  Created student: {student_code} ({username})")

        await db.commit()

    await engine.dispose()

    print("\n" + "=" * 50)
    print("Demo users ready to use:")
    print("=" * 50)
    print("  admin / admin123          - Admin")
    print("  student1 / demo123        - Student (STU-001)")
    print("  student2 / demo123        - Student (STU-002)")
    print("  student3 / demo123        - Student (STU-003)")
    print("  therapist1 / demo123      - Therapist")
    print("  supervisor1 / demo123     - Supervisor")
    for u, name, _ in STAFF_EMPLOYEES:
        print(f"  {u} / demo123          - Staff ({name})")
    print("  site_manager1 / demo123   - Site Manager")
    print("  progress_committee1 / demo123 - Progress Committee")
    print("=" * 50)
    print(f"\nCreated: {created} | Updated: {updated}")
    print("Done.")
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
