#!/usr/bin/env python3
"""
راهنمای PDF آزمایش وظایف کمک‌مدرس پس از جلسه کلاس (فرایندهای SOP 43–46).

اجرا از ریشهٔ ریپو:
  python scripts/generate_ta_class_duties_operator_guide_pdf.py

خروجی:
  docs/راهنمای_آزمایش_وظایف_کمک_مدرس_پس_از_جلسه.pdf
"""
from __future__ import annotations

import sys
from pathlib import Path

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fpdf.enums import Align, TableBordersLayout, TableCellFillMode
from fpdf.fonts import FontFace

from scripts.generate_ui_tester_guide_pdf import (
    PdfBuilder,
    _fa,
    _heading_style,
    _BODY,
    _TITLE,
    _COLOR_STRIPE,
)

OUT_PDF = ROOT / "docs" / "راهنمای_آزمایش_وظایف_کمک_مدرس_پس_از_جلسه.pdf"

ACCOUNTS = [
    ("کمک‌مدرس (آپلود / فرم milestone)", "ta_demo", "demo123"),
    ("مدرس (بررسی علمی)", "instructor_demo", "demo123"),
    ("مدیر سامانه (آماده‌سازی پرونده)", "admin", "admin123"),
]

PROCESSES = [
    ("۴۳", "ta_conceptual_questions", "ثبت ۳ سوال تستی‌مفهومی"),
    ("۴۴", "ta_student_consultation", "شناسایی، تشویق و مشورت آموزشی"),
    ("۴۵", "ta_essay_upload", "آپلود جستار و دقایق فیلم"),
    ("۴۶", "ta_blog_content", "ثبت محتوای وبلاگ"),
]

SCENARIOS = [
    {
        "letter": "الف",
        "title": "کمک‌مدرس — آپلود سوالات مفهومی (فرایند ۴۳)",
        "steps": [
            "با حساب کمک‌مدرس وارد شوید و «پنل مدرس و کمک‌مدرس» را باز کنید.",
            "مسیر: /panel/portal/staff/instruction — تب «کارهای من».",
            "پروندهٔ «ثبت ۳ سوال تستی‌مفهومی» را باز کنید.",
            "کارت راهنما با data-testid=ta-class-duties-panel را ببینید.",
            "استپر مراحل و خلاصه درس/جلسه را بررسی کنید.",
            "هشدار SLA ۲۴ ساعته و راهنمای «قالب سوال» را بخوانید.",
            "در فرم پایین، سه فایل PDF آپلود و ارسال کنید.",
        ],
        "checks": [
            "نمایش پنل ta-class-duties-panel",
            "نمایش استپر ta-duty-flow-stepper",
            "نمایش خلاصه درس و شماره جلسه",
            "فرم آپلود سه PDF",
        ],
    },
    {
        "letter": "ب",
        "title": "مدرس — بررسی سوالات / جستار / وبلاگ",
        "steps": [
            "با حساب مدرس وارد پنل instruction شوید.",
            "پروندهٔ در انتظار «بررسی توسط مدرس» را باز کنید.",
            "راهنمای مرحلهٔ مدرس را بخوانید.",
            "فرم بررسی را تکمیل کنید؛ در صورت رد، توضیح اجباری وارد کنید.",
            "دکمهٔ تصمیم (تأیید یا رد) را بزنید.",
        ],
        "checks": [
            "راهنمای مدرس در ta-duty-state-hint",
            "فرم review_decision",
            "انتقال به مرحله بعد یا اصلاح",
        ],
    },
    {
        "letter": "ج",
        "title": "مشورت آموزشی milestone — جلسات ۵ / ۱۰ / ۱۵ (فرایند ۴۴)",
        "steps": [
            "پروندهٔ «شناسایی، تشویق و مشورت آموزشی» را باز کنید.",
            "کارت «جلسه milestone» را در خلاصه ببینید.",
            "هشدار مهلت ۴ روزه را بررسی کنید.",
            "با «افزودن ردیف» دانشجویان را از لیست کلاس انتخاب کنید.",
            "علت انتخاب و محتوای مداخله را بنویسید و فرم را ثبت کنید.",
        ],
        "checks": [
            "نمایش milestone در ta-duty-milestone-summary",
            "لیست پویا با انتخاب دانشجو",
            "ثبت موفق → form_submitted",
        ],
    },
    {
        "letter": "د",
        "title": "وبلاگ — فقط متن (فرایند ۴۶)",
        "steps": [
            "پروندهٔ «ثبت محتوای وبلاگ» را باز کنید.",
            "راهنمای «فقط متن — آپلود فایل مجاز نیست» را ببینید.",
            "متن حدود نیم صفحه A4 را در فیلد blog_content بنویسید.",
            "ارسال کنید و منتظر بررسی مدرس بمانید.",
        ],
        "checks": [
            "هشدار ta-duty-blog-text-hint",
            "textarea بدون file upload",
        ],
    },
]


class TaClassDutiesGuideBuilder(PdfBuilder):
    def cover(self) -> None:
        p = self.pdf
        p.add_page()
        p.set_font("Vazir", "B", _TITLE)
        p.ln(8)
        p.cell(0, 12, _fa("راهنمای آزمایش و استفاده"), align="C", new_x="LMARGIN", new_y="NEXT")
        p.set_font("Vazir", "B", 12.5)
        p.cell(
            0,
            10,
            _fa("وظایف کمک‌مدرس پس از جلسه کلاس (فرایندهای ۴۳ تا ۴۶)"),
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        p.set_font("Vazir", "", 10)
        p.cell(
            0,
            8,
            _fa("پنل هدف: مدرس و کمک‌مدرس — مسیر instruction"),
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        p.ln(6)
        self._body(
            "این کتابچه برای آزمایش رابط کاربری چهار فرایند وظایف کلاسی "
            "کمک‌مدرس نوشته شده است: سوالات مفهومی، مشورت آموزشی milestone، "
            "جستار و دقایق فیلم، و محتوای وبلاگ."
        )

    def process_table(self) -> None:
        self.pdf.add_page()
        self._section_bar("فهرست فرایندها")
        p = self.pdf
        with p.table(
            col_widths=(20, 55, 95),
            width=p.epw,
            text_align=Align.R,
            line_height=5.5,
            borders_layout=TableBordersLayout.ALL,
            cell_fill_color=_COLOR_STRIPE,
            cell_fill_mode=TableCellFillMode.ROWS,
            padding=1.5,
        ) as table:
            hr = table.row()
            for h in [_fa("SOP"), _fa("کد"), _fa("عنوان")]:
                hr.cell(h, align=Align.C, style=_heading_style())
            for sop, code, title in PROCESSES:
                row = table.row()
                row.cell(sop, align=Align.C)
                row.cell(_fa(code), align=Align.R)
                row.cell(_fa(title), align=Align.R)
        p.ln(4)

    def accounts_section(self) -> None:
        self._section_bar("حساب‌های آزمایش پیشنهادی")
        p = self.pdf
        with p.table(
            col_widths=(80, 45, 45),
            width=p.epw,
            text_align=Align.R,
            line_height=5.5,
            borders_layout=TableBordersLayout.ALL,
            cell_fill_color=_COLOR_STRIPE,
            cell_fill_mode=TableCellFillMode.ROWS,
            padding=1.5,
        ) as table:
            hr = table.row()
            for h in [_fa("نقش"), _fa("نام کاربری"), _fa("رمز")]:
                hr.cell(h, align=Align.C, style=_heading_style())
            for label, user, pwd in ACCOUNTS:
                row = table.row()
                row.cell(_fa(label))
                row.cell(_fa(user), align=Align.C)
                row.cell(_fa(pwd), align=Align.C)
        p.ln(4)

    def scenarios_section(self) -> None:
        for sc in SCENARIOS:
            self.pdf.add_page()
            self._section_bar(f"سناریوی {sc['letter']} — {sc['title']}")
            self._body("مراحل:", bold=True)
            self._numbered_list(sc["steps"])
            self._body("چک‌لیست:", bold=True)
            self._check_table(sc["checks"])

    def build(self) -> None:
        self.cover()
        self.process_table()
        self.accounts_section()
        self.scenarios_section()
        OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
        self.pdf.output(str(OUT_PDF))
        print(f"Wrote {OUT_PDF}")


def main() -> int:
    TaClassDutiesGuideBuilder().build()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
