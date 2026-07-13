#!/usr/bin/env python3
"""
PDF سادهٔ تست فرایندهای حیاتی — بدون جدول فنی و اصطلاحات پیچیده.

اجرا:
  python scripts/generate_phase1_simple_test_pdf.py

خروجی:
  docs/راهنمای_تست_ساده_فرایندهای_حیاتی.pdf
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
from scripts.lib.process_test_guide_data import (
    DEMO_ACCOUNTS,
    PHASE_1_CRITICAL,
    ProcessTestSpec,
    build_process_specs,
    derive_ui_start,
    filter_phase1_specs,
)

OUT_PDF = ROOT / "docs" / "راهنمای_تست_ساده_فرایندهای_حیاتی.pdf"

SITE_URL = "https://lms.psychoanalysis.ir/"
DEFAULT_PASSWORD = "demo123"
ADMIN_PASSWORD = "admin123"

# همهٔ حساب‌های لازم برای فاز ۱ (از DEMO_ACCOUNTS)
PHASE1_ACCOUNTS = list(DEMO_ACCOUNTS)

# قدم‌های سادهٔ ثابت (اگر در متادیتا نبود)
SIMPLE_STEPS_FALLBACK: dict[str, list[str]] = {
    "fall_semester_preparation": [
        f"در مرورگر بروید به {SITE_URL}",
        "با نام کاربری deputy_education1 و رمز demo123 وارد شوید.",
        "منوی کناری / آماده‌سازی ترم را باز کنید.",
        "مراحل را یکی‌یکی جلو ببرید (تقویم، شهریه، دروس، …).",
        "تا وضعیت «انتشار» ادامه دهید.",
    ],
    "introductory_course_registration": [
        f"در مرورگر بروید به {SITE_URL}",
        "با regdemo_intro_app / demo123 وارد شوید.",
        "پنل آموزشی / تب فرایندها را باز کنید.",
        "ثبت‌نام آشنایی را شروع کنید.",
        "برای مصاحبه و پذیرش با demo_interviewer و demo_admissions وارد شوید.",
    ],
    "lesson_start_per_term": [
        f"در مرورگر بروید به {SITE_URL}",
        "با staff1 / demo123 وارد شوید.",
        "پنل مدرس / کارهای من را باز کنید.",
        "فرایند آغاز درس را پیدا یا شروع کنید.",
    ],
    "start_therapy": [
        f"در مرورگر بروید به {SITE_URL}",
        "با student1 / demo123 وارد شوید و درخواست درمان ثبت کنید.",
        "خروج؛ سپس با therapist1 / demo123 وارد شوید و درخواست را تأیید کنید.",
    ],
    "attendance_tracking": [
        f"در مرورگر بروید به {SITE_URL}",
        "با therapist1 / demo123 وارد شوید.",
        "پنل درمانگر / کارهای من — حضور یا غیاب را ثبت کنید.",
    ],
    "session_payment": [
        f"در مرورگر بروید به {SITE_URL}",
        "با student1 / demo123 وارد شوید.",
        "پنل آموزشی / فرایندها — پرداخت جلسه را انجام دهید.",
    ],
    "supervision_block_transition": [
        f"در مرورگر بروید به {SITE_URL}",
        "با student1 درخواست سوپرویژن ثبت کنید.",
        "با supervisor1 / demo123 بررسی کنید.",
        "پرداخت جلسه اول بلوک جدید را انجام دهید.",
    ],
    "educational_leave": [
        f"در مرورگر بروید به {SITE_URL}",
        "با student1 درخواست مرخصی ثبت کنید.",
        "با progress_committee1 / demo123 بررسی کنید.",
    ],
    "violation_registration": [
        f"در مرورگر بروید به {SITE_URL}",
        "با supervision_committee1 / demo123 وارد شوید.",
        "پنل کمیته نظارت / بررسی‌ها — پرونده تخلف را بررسی کنید.",
    ],
    "comprehensive_course_registration": [
        f"در مرورگر بروید به {SITE_URL}",
        "با student2 / demo123 وارد شوید.",
        "پنل آموزشی / فرایندها — ثبت‌نام دوره جامع.",
    ],
    "comprehensive_term_start": [
        f"در مرورگر بروید به {SITE_URL}",
        "با student2 / demo123 وارد شوید.",
        "پنل آموزشی / فرایندها — آغاز ترم جامع.",
    ],
}

SIMPLE_EXPECT: dict[str, str] = {
    "fall_semester_preparation": "ترم پاییز منتشر شود و ثبت‌نام آشنایی باز شود.",
    "introductory_course_registration": "متقاضی تا ثبت‌نام نهایی برسد.",
    "lesson_start_per_term": "درس در سامانه فعال شود.",
    "start_therapy": "درمان دانشجو فعال شود.",
    "attendance_tracking": "حضور/غیاب ثبت و در پروفایل دیده شود.",
    "session_payment": "پرداخت جلسه ثبت شود.",
    "supervision_block_transition": "بلوک سوپرویژن جدید فعال شود.",
    "educational_leave": "مرخصی تأیید یا رد شود و وضعیت عوض شود.",
    "violation_registration": "پرونده تخلف قابل پیگیری باشد.",
    "comprehensive_course_registration": "ثبت‌نام جامع کامل شود.",
    "comprehensive_term_start": "ترم جامع آغاز شود.",
}


class SimplePhase1Builder:
    def __init__(self, specs: list[ProcessTestSpec], phase_meta: list[tuple[str, str]]) -> None:
        self.specs = specs
        self.phase_meta = phase_meta
        self.by_code = {s.code: s for s in specs}
        self.pdf = GuidePDF(footer_label="تست ساده — فرایندهای حیاتی")
        register_fonts(self.pdf)
        self.pdf.set_margins(MARGIN, MARGIN, MARGIN)
        self.pdf.set_auto_page_break(auto=True, margin=16)
        self.sb = PdfSectionBuilder(self.pdf)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.pdf.output(str(path))

    def _simple_steps(self, spec: ProcessTestSpec) -> list[str]:
        enrich = spec.enrichment or {}
        if enrich.get("steps"):
            return [str(s) for s in enrich["steps"][:6]]
        if spec.code in SIMPLE_STEPS_FALLBACK:
            return SIMPLE_STEPS_FALLBACK[spec.code]
        ui = derive_ui_start(spec)
        return [
            f"با {ui.account} وارد شوید.",
            f"به {ui.menu_nav} بروید.",
            ui.first_click,
            "کار خواسته‌شده را انجام و ثبت کنید.",
        ]

    def _simple_expect(self, spec: ProcessTestSpec) -> str:
        enrich = spec.enrichment or {}
        if spec.code in SIMPLE_EXPECT:
            return SIMPLE_EXPECT[spec.code]
        if enrich.get("expect"):
            return str(enrich["expect"])
        ui = derive_ui_start(spec)
        return ui.success_signal

    def _password_for(self, username: str) -> str:
        if username == "admin":
            return ADMIN_PASSWORD
        return DEFAULT_PASSWORD

    def _login_block(self, spec: ProcessTestSpec) -> list[str]:
        ui = derive_ui_start(spec)
        user = ui.account
        pw = self._password_for(user)
        return [
            f"آدرس سایت: {SITE_URL}",
            f"نام کاربری: {user}",
            f"رمز: {pw}",
            f"نقش: {ui.role_fa}",
        ]

    def _menu_line(self, spec: ProcessTestSpec) -> str:
        ui = derive_ui_start(spec)
        return ui.menu_nav

    def cover_and_intro(self) -> None:
        p = self.pdf
        p.add_page()
        p.set_font("Vazir", "B", TITLE)
        p.ln(4)
        p.cell(0, 11, fa("راهنمای تست ساده — فرایندهای حیاتی"), align="C", new_x="LMARGIN", new_y="NEXT")
        p.set_font("Vazir", "", 10)
        p.cell(0, 8, fa("۱۱ فرایند مهم — برای اپراتور غیرفنی"), align="C", new_x="LMARGIN", new_y="NEXT")
        p.ln(4)
        p.set_font("Vazir", "", BODY)
        p.cell(0, 7, fa(f"نام تست‌کننده: ________________________"), align="R", new_x="LMARGIN", new_y="NEXT")
        p.cell(0, 7, fa(f"تاریخ: ________________________"), align="R", new_x="LMARGIN", new_y="NEXT")
        p.cell(0, 7, fa(f"آدرس سایت: {SITE_URL}"), align="R", new_x="LMARGIN", new_y="NEXT")
        p.ln(2)
        self.sb.ok_box(
            f"سایت تست روی اینترنت است: {SITE_URL} — نه روی کامپیوتر شخصی. "
            "نیازی به دانش فنی یا اجرای دستور ندارید؛ فقط مرورگر (Chrome یا Edge) کافی است."
        )
        self.sb.body("چطور وارد شوم؟", bold=True)
        self.sb.numbered_list([
            f"مرورگر را باز کنید و بروید به {SITE_URL}",
            "نام کاربری و رمز را از جدول پایین یا همان صفحهٔ هر تست وارد کنید.",
            "دکمهٔ ورود را بزنید.",
            "اگر ورود نشد: با پشتیبانی فنی تماس بگیرید (شما کاری جز گزارش ندارید).",
        ])
        self.sb.body("روش تست:", bold=True)
        self.sb.numbered_list([
            "فرایندها را به ترتیب شماره زیر تست کنید.",
            "با حساب همان صفحه وارد شوید و منو را باز کنید.",
            "کارها را انجام دهید؛ ببینید نتیجه درست است یا نه.",
            "اگر نشد: بنویسید «انتظار داشتم … / دیدم …».",
        ])
        self.sb.section_bar("فهرست ۱۱ فرایند (به همین ترتیب)")
        for i, (code, why) in enumerate(self.phase_meta, 1):
            spec = self.by_code.get(code)
            name = spec.name_fa if spec else code
            self.sb.body(f"{i}. {name}")
        self.sb.section_bar("جدول همهٔ حساب‌های ورود")
        self.sb.body(
            "رمز همهٔ حساب‌ها demo123 است — به‌جز مدیر سامانه (admin) که رمز admin123 دارد. "
            "نام کاربری را دقیقاً همان‌طور که نوشته شده تایپ کنید."
        )
        self.sb.simple_table(
            headers=["نقش", "نام کاربری", "رمز"],
            rows=[list(row) for row in PHASE1_ACCOUNTS],
            col_widths=[48, 52, 26],
            fa_cols=[True, False, False],
            font_size=SMALL,
            line_height=5.0,
        )

    def process_pages(self) -> None:
        for i, (code, why) in enumerate(self.phase_meta, 1):
            spec = self.by_code.get(code)
            if not spec:
                continue
            self.pdf.add_page()
            self.sb.section_bar(f"تست {i} از {len(self.phase_meta)}: {spec.name_fa}")

            self.sb.body("این فرایند چیست؟", bold=True)
            desc = why
            if spec.description and len(spec.description) < 200:
                desc = spec.description
            self.sb.body(desc)

            self.sb.body("ورود به سایت:", bold=True)
            for line in self._login_block(spec):
                self.sb.body(line)

            self.sb.body("کجا بروید:", bold=True)
            self.sb.body(self._menu_line(spec))

            self.sb.body("چه کار کنید:", bold=True)
            self.sb.numbered_list(self._simple_steps(spec))

            self.sb.body("باید چه ببینید (نتیجه درست):", bold=True)
            self.sb.body(self._simple_expect(spec))

            self.sb.body("اگر نشد، بنویسید:", bold=True)
            self.sb.body("انتظار داشتم: _________________________________________________")
            self.sb.body("در عوض دیدم: _________________________________________________")

            self.sb.body("نتیجه تست:  [ ] موفق     [ ] ناموفق")
            self.sb.blank_lines("یادداشت (اختیاری):", 2)

    def summary_page(self) -> None:
        self.pdf.add_page()
        self.sb.section_bar("جمع‌بندی")
        rows = []
        for i, (code, _) in enumerate(self.phase_meta, 1):
            spec = self.by_code.get(code)
            name = spec.name_fa[:28] if spec else code
            rows.append([str(i), name, "[ ]", "[ ]", ""])
        self.sb.simple_table(
            headers=["#", "فرایند", "موفق", "ناموفق", "یادداشت کوتاه"],
            rows=rows,
            col_widths=[10, 62, 14, 14, 38],
            font_size=SMALL,
        )


def main() -> int:
    all_specs = build_process_specs()
    phase_specs = filter_phase1_specs(all_specs)
    builder = SimplePhase1Builder(phase_specs, PHASE_1_CRITICAL)
    builder.cover_and_intro()
    builder.process_pages()
    builder.summary_page()
    builder.save(OUT_PDF)
    print(f"PDF written: {OUT_PDF}")
    print(f"Pages: {builder.pdf.page_no()}")
    print(f"Size: {OUT_PDF.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
