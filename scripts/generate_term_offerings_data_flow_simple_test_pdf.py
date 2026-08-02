#!/usr/bin/env python3
"""
PDF سادهٔ تست اتصال دادهٔ آماده‌سازی ترم به مسیر دانشجو.

قالب: docs/قالب_تولید_راهنمای_تست_ساده_PDF.md

اجرا:
  python scripts/generate_term_offerings_data_flow_simple_test_pdf.py

خروجی:
  docs/راهنمای_تست_ساده_اتصال_داده_آماده_سازی_ترم.pdf
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

from scripts.lib.pdf_fa_utils import (
    BODY,
    MARGIN,
    SMALL,
    TITLE,
    GuidePDF,
    PdfSectionBuilder,
    fa,
    register_fonts,
)

OUT_PDF = ROOT / "docs" / "راهنمای_تست_ساده_اتصال_داده_آماده_سازی_ترم.pdf"

SITE_URL = "https://lms.psychoanalysis.ir/"
DEFAULT_PASSWORD = "demo123"

# (عنوان کوتاه, چرا مهم است, حساب, منو, قدم‌ها, انتظار)
TERM_DATA_FLOW_TESTS: list[dict] = [
    {
        "title": "انتشار دروس از آماده‌سازی ترم پاییز",
        "why": "دروس باید پس از نهایی‌سازی در سامانه منتشر شوند تا دانشجو ببیند.",
        "user": "deputy_education1",
        "role": "معاون آموزشی",
        "menu": "منوی کناری / آماده‌سازی ترم / میزکار آماده‌سازی ترم پاییز",
        "steps": [
            f"در مرورگر بروید به {SITE_URL}",
            "با deputy_education1 و رمز demo123 وارد شوید.",
            "فرایند آماده‌سازی ترم پاییز را باز کنید.",
            "دروس را ثبت و در نهایی‌سازی روز، ساعت و کلاس را پر کنید.",
            "تا پس از نهایی‌سازی دروس جلو بروید؛ خطای انتشار نبینید.",
        ],
        "expect": "پس از نهایی‌سازی، فرایند بدون گیر ادامه یابد و دروس برای دانشجو قابل استفاده شود.",
    },
    {
        "title": "بسته بودن ثبت‌نام بدون دروس منتشرشده",
        "why": "ثبت‌نام آشنایی نباید بدون فهرست دروس منتشرشده باز شود.",
        "user": "regdemo_intro_app",
        "role": "متقاضی آشنایی",
        "menu": "پنل آموزشی / تب فرایندها",
        "steps": [
            f"در مرورگر بروید به {SITE_URL}",
            "با regdemo_intro_app و رمز demo123 وارد شوید.",
            "سعی کنید ثبت‌نام دورهٔ آشنایی را شروع کنید.",
            "پیام بالای صفحه را بخوانید.",
        ],
        "expect": "پیام بسته بودن یا «لیست دروس هنوز منتشر نشده» — نه لیست ثابت ۵ درس.",
    },
    {
        "title": "نمایش دروس واقعی در ثبت‌نام آشنایی",
        "why": "دانشجو باید همان دروس آماده‌سازی را با نام فارسی ببیند.",
        "user": "regdemo_intro_app",
        "role": "متقاضی آشنایی",
        "menu": "پنل آموزشی / ثبت‌نام دورهٔ آشنایی / انتخاب درس",
        "steps": [
            f"در مرورگر بروید به {SITE_URL}",
            "با regdemo_intro_app وارد شوید.",
            "تا مرحلهٔ انتخاب درس برسید (در صورت نیاز با مصاحبه‌گر نتیجه ثبت شود).",
            "نام دروس checkbox را با آماده‌سازی ترم مقایسه کنید.",
            "بررسی کنید فیلد ورود دستی کد درس وجود ندارد.",
        ],
        "expect": "نام فارسی دروس مطابق آماده‌سازی؛ بدون theory_1 و بدون ورود دستی.",
    },
    {
        "title": "شهریه و هزینهٔ مصاحبه از آماده‌سازی",
        "why": "مبالغ پرداخت باید از اعداد ثبت‌شده در آماده‌سازی ترم بیاید.",
        "user": "regdemo_intro_app",
        "role": "متقاضی آشنایی",
        "menu": "ثبت‌نام آشنایی / پرداخت مصاحبه و پرداخت شهریه",
        "steps": [
            f"در مرورگر بروید به {SITE_URL}",
            "با regdemo_intro_app وارد شوید.",
            "مبلغ پرداخت مصاحبه را یادداشت کنید.",
            "دروس را انتخاب و مبلغ شهریه را ببینید.",
            "با اعداد مرحلهٔ شهریه در آماده‌سازی ترم مقایسه کنید.",
        ],
        "expect": "مبالغ با آماده‌سازی ترم هم‌خوان باشند.",
    },
    {
        "title": "ثبت‌نام ترم دوم آشنایی",
        "why": "دروس ترم دوم از فهرست منتشرشده باشد — نه نام ساختگی.",
        "user": "student1",
        "role": "دانشجوی آشنایی",
        "menu": "پنل آموزشی / ثبت‌نام ترم دوم آشنایی",
        "steps": [
            f"در مرورگر بروید به {SITE_URL}",
            "با student1 و رمز demo123 وارد شوید.",
            "فرایند ثبت‌نام ترم دوم را باز کنید.",
            "لیست دروس مرحلهٔ انتخاب را بخوانید.",
        ],
        "expect": "نام فارسی دروس؛ بدون کدهایی مثل introductory_term2_course1.",
    },
    {
        "title": "ثبت‌نام دورهٔ جامع",
        "why": "دانشجوی جامع نباید دروس placeholder ببیند.",
        "user": "student2",
        "role": "دانشجوی جامع",
        "menu": "پنل آموزشی / ثبت‌نام یا آغاز ترم جامع",
        "steps": [
            f"در مرورگر بروید به {SITE_URL}",
            "با student2 و رمز demo123 وارد شوید.",
            "فرایند مربوط به دروس ترم را باز کنید.",
            "فهرست دروس را بررسی کنید.",
        ],
        "expect": "دروس فارسی از آماده‌سازی؛ بدون comprehensive_term3_course1.",
    },
    {
        "title": "پیام مناسب وقتی داده نیست",
        "why": "بدون داده، پیام واضح باشد — نه ورود دستی.",
        "user": "regdemo_intro_app",
        "role": "متقاضی",
        "menu": "هر فرم انتخاب درس",
        "steps": [
            "در محیطی که دروس منتشر نشده، به فرم انتخاب درس بروید.",
            "صفحه را کامل بخوانید.",
            "بررسی کنید کادر ورود دستی نیست.",
        ],
        "expect": "پیام «لیست دروس هنوز منتشر نشده» و بدون امکان تایپ کد درس.",
    },
    {
        "title": "برنامهٔ کلاسی در جلسات آنلاین",
        "why": "روز و ساعت کلاس از آماده‌سازی نمایش داده شود.",
        "user": "student1",
        "role": "دانشجو",
        "menu": "پنل آموزشی / جلسات آنلاین",
        "steps": [
            f"در مرورگر بروید به {SITE_URL}",
            "با student1 وارد شوید.",
            "بخش جلسات آنلاین را باز کنید.",
            "عنوان و توضیحات هر درس را بخوانید.",
        ],
        "expect": "روز/ساعت/کلاس در عنوان یا توضیح — یا پیام «برنامه کلاسی منتشر نشده».",
    },
    {
        "title": "کارنامه پایان ترم",
        "why": "نام درس در کارنامه فارسی و از فهرست منتشرشده باشد.",
        "user": "student1",
        "role": "دانشجو",
        "menu": "پنل آموزشی / پایان ترم آشنایی",
        "steps": [
            f"در مرورگر بروید به {SITE_URL}",
            "با student1 وارد شوید.",
            "فرایند پایان ترم را باز کنید.",
            "نام دروس در جدول کارنامه را بخوانید.",
        ],
        "expect": "نام فارسی درس — نه فقط theory_1.",
    },
    {
        "title": "ویرایش دروس توسط پذیرش",
        "why": "پذیرش فقط از فهرست منتشرشده ویرایش کند — نه تایپ دستی.",
        "user": "demo_admissions",
        "role": "پذیرش",
        "menu": "پنل پذیرش / پروندهٔ دانشجو / تغییر دروس",
        "steps": [
            f"در مرورگر بروید به {SITE_URL}",
            "با demo_admissions و رمز demo123 وارد شوید.",
            "پروندهٔ ثبت‌نام آشنایی را باز کنید.",
            "بخش تغییر دروس را پیدا کنید.",
            "بررسی کنید فقط checkbox از فهرست است.",
        ],
        "expect": "لیست checkbox؛ بدون کادر «کد با ویرگول».",
    },
]

ACCOUNTS = [
    ("معاون آموزشی", "deputy_education1", "demo123"),
    ("متقاضی آشنایی", "regdemo_intro_app", "demo123"),
    ("مصاحبه‌گر", "demo_interviewer", "demo123"),
    ("پذیرش", "demo_admissions", "demo123"),
    ("دانشجوی آشنایی", "student1", "demo123"),
    ("دانشجوی جامع", "student2", "demo123"),
    ("مدیر سامانه", "admin", "admin123"),
]


class TermOfferingsTestBuilder:
    def __init__(self) -> None:
        self.pdf = GuidePDF(footer_label="تست — اتصال داده آماده‌سازی ترم")
        register_fonts(self.pdf)
        self.pdf.set_margins(MARGIN, MARGIN, MARGIN)
        self.pdf.set_auto_page_break(auto=True, margin=16)
        self.sb = PdfSectionBuilder(self.pdf)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.pdf.output(str(path))

    def cover(self) -> None:
        p = self.pdf
        p.add_page()
        p.set_font("Vazir", "B", TITLE)
        p.ln(4)
        p.cell(
            0,
            11,
            fa("راهنمای تست — اتصال دادهٔ آماده‌سازی ترم"),
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        p.set_font("Vazir", "", 10)
        p.cell(
            0,
            8,
            fa("۱۰ سناریو — دروس، شهریه و برنامهٔ کلاسی از آماده‌سازی ترم"),
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        p.ln(4)
        p.set_font("Vazir", "", BODY)
        p.cell(0, 7, fa("نام تست‌کننده: ________________________"), align="R", new_x="LMARGIN", new_y="NEXT")
        p.cell(0, 7, fa("تاریخ: ________________________"), align="R", new_x="LMARGIN", new_y="NEXT")
        p.cell(0, 7, fa(f"آدرس سایت: {SITE_URL}"), align="R", new_x="LMARGIN", new_y="NEXT")
        p.ln(2)
        self.sb.ok_box(
            f"سایت تست: {SITE_URL} — فقط مرورگر کافی است. "
            "ابتدا تست ۱ (انتشار دروس) را انجام دهید؛ بقیه به آن وابسته‌اند."
        )
        self.sb.body("چطور وارد شوم؟", bold=True)
        self.sb.numbered_list([
            f"مرورگر را باز کنید و بروید به {SITE_URL}",
            "نام کاربری و رمز را از جدول پایین وارد کنید.",
            "دکمهٔ ورود را بزنید.",
            "اگر ورود نشد: با پشتیبانی تماس بگیرید.",
        ])
        self.sb.body("روش تست:", bold=True)
        self.sb.numbered_list([
            "سناریوها را به ترتیب شماره تست کنید.",
            "کارها را انجام دهید؛ ببینید نتیجه درست است یا نه.",
            "اگر نشد: «انتظار داشتم … / دیدم …» بنویسید.",
            "در انتها جدول جمع‌بندی را پر کنید.",
        ])
        self.sb.section_bar(f"فهرست {len(TERM_DATA_FLOW_TESTS)} سناریو")
        for i, t in enumerate(TERM_DATA_FLOW_TESTS, 1):
            self.sb.body(f"{i}. {t['title']}")
        self.sb.section_bar("جدول حساب‌های ورود")
        self.sb.simple_table(
            headers=["نقش", "نام کاربری", "رمز"],
            rows=[list(r) for r in ACCOUNTS],
            col_widths=[48, 52, 26],
            fa_cols=[True, False, False],
            font_size=SMALL,
            line_height=5.0,
        )

    def test_pages(self) -> None:
        total = len(TERM_DATA_FLOW_TESTS)
        for i, t in enumerate(TERM_DATA_FLOW_TESTS, 1):
            self.pdf.add_page()
            self.sb.section_bar(f"تست {i} از {total}: {t['title']}")

            self.sb.body("این فرایند چیست؟", bold=True)
            self.sb.body(t["why"])

            self.sb.body("ورود به سایت:", bold=True)
            self.sb.body(f"آدرس سایت: {SITE_URL}")
            self.sb.body(f"نام کاربری: {t['user']}")
            self.sb.body(f"رمز: {DEFAULT_PASSWORD if t['user'] != 'admin' else 'admin123'}")
            self.sb.body(f"نقش: {t['role']}")

            self.sb.body("کجا بروید:", bold=True)
            self.sb.body(t["menu"])

            self.sb.body("چه کار کنید:", bold=True)
            self.sb.numbered_list(t["steps"])

            self.sb.body("باید چه ببینید (نتیجه درست):", bold=True)
            self.sb.body(t["expect"])

            self.sb.body("اگر نشد، بنویسید:", bold=True)
            self.sb.body("انتظار داشتم: _________________________________________________")
            self.sb.body("در عوض دیدم: _________________________________________________")

            self.sb.body("نتیجه تست:  [ ] موفق     [ ] ناموفق")
            self.sb.blank_lines("یادداشت (اختیاری):", 2)

    def summary(self) -> None:
        self.pdf.add_page()
        self.sb.section_bar("جمع‌بندی")
        rows = []
        for i, t in enumerate(TERM_DATA_FLOW_TESTS, 1):
            rows.append([str(i), t["title"][:30], "[ ]", "[ ]", ""])
        self.sb.simple_table(
            headers=["#", "سناریو", "موفق", "ناموفق", "یادداشت"],
            rows=rows,
            col_widths=[10, 62, 14, 14, 38],
            font_size=SMALL,
        )


def main() -> int:
    builder = TermOfferingsTestBuilder()
    builder.cover()
    builder.test_pages()
    builder.summary()
    builder.save(OUT_PDF)
    print(f"PDF written: {OUT_PDF}")
    print(f"Pages: {builder.pdf.page_no()}")
    print(f"Size: {OUT_PDF.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
