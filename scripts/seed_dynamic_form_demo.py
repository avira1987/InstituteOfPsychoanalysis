"""
ایجاد قالب و اتصال نمونه به فرایند ثبت‌نام آشنایی — وضعیت application_submitted.
اجرای دستی: python scripts/seed_dynamic_form_demo.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.database import async_session_factory
import app.models.operational_models  # noqa: F401 — قبل از dynamic_forms برای FK به users
from app.models.dynamic_forms import FormAssignment, FormTemplate, FormTemplateVersion


async def main() -> None:
    async with async_session_factory() as db:
        code = "demo_portal_feedback"
        existing = (await db.execute(select(FormTemplate).where(FormTemplate.code == code))).scalars().first()
        if existing:
            print("Already exists:", code)
            return
        tid = uuid.uuid4()
        t = FormTemplate(
            id=tid,
            code=code,
            name_fa="بازخورد نمونه (داینامیک)",
            description="نمونهٔ اتصال به فرایند برای تست __dynamic_form__ در context",
            audience="student",
            created_by_id=None,
        )
        db.add(t)
        schema = {
            "fields": [
                {
                    "name": "satisfaction",
                    "type": "radio_list",
                    "label_fa": "رضایت از روند ثبت‌نام تا این مرحله",
                    "required": True,
                    "options": [
                        {"value": "good", "label_fa": "خوب"},
                        {"value": "ok", "label_fa": "متوسط"},
                        {"value": "bad", "label_fa": "نیاز به پیگیری"},
                    ],
                },
                {"name": "comment", "type": "textarea", "label_fa": "توضیح (اختیاری)", "required": False},
            ]
        }
        vid = uuid.uuid4()
        v = FormTemplateVersion(
            id=vid,
            template_id=tid,
            version=1,
            schema_json=schema,
            published_at=None,
        )
        db.add(v)
        await db.flush()
        v.published_at = datetime.now(timezone.utc)
        aid = uuid.uuid4()
        a = FormAssignment(
            id=aid,
            template_id=tid,
            template_version_id=vid,
            assignment_type="process",
            process_code="introductory_course_registration",
            state_code="application_submitted",
            context_key="demo_portal_feedback_v1",
            sort_order=0,
            active=True,
        )
        db.add(a)
        await db.commit()
        print("Seeded:", code, "assignment", str(aid))
        print(json.dumps({"template_id": str(tid), "version_id": str(vid), "assignment_id": str(aid)}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
