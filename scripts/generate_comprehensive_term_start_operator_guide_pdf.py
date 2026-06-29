#!/usr/bin/env python3
"""
راهنمای PDF اپراتور — فرایند ۴۰: آغاز ترم‌های دوره جامع
(بدون جزئیات فنی؛ مناسب تست و پذیرش UI)

اجرا از ریشهٔ ریپو:
  python scripts/generate_comprehensive_term_start_operator_guide_pdf.py

خروجی:
  docs/راهنمای_تست_فرایند_۴۰_آغاز_ترم_دوره_جامع.pdf
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

import arabic_reshaper
import jdatetime
from bidi.algorithm import get_display
from fpdf import FPDF
from fpdf.enums import Align, TableBordersLayout, TableCellFillMode, VAlign
from fpdf.fonts import FontFace

ASSETS = ROOT / "app" / "assets" / "fonts"
FONT_REG = ASSETS / "Vazirmatn-Regular.ttf"
FONT_BOLD = ASSETS / "Vazirmatn-Bold.ttf"
OUT_PDF = ROOT / "docs" / "راهنمای_تست_فرایند_۴۰_آغاز_ترم_دوره_جامع.pdf"

_MARGIN = 14
_BODY = 9.5
_SECTION = 11.5
_TITLE = 15
_SMALL = 8
_TINY = 7.5

_COLOR_SECTION_BG = (235, 241, 250)
_COLOR_SECTION_TEXT = (30, 58, 95)
_COLOR_BORDER = (209, 213, 219)
_COLOR_STRIPE = (249, 250, 251)
_COLOR_TIP_BG = (255, 251, 235)
_COLOR_WARN_BG = (254, 242, 242)
_COLOR_OK_BG = (240, 253, 244)

STATE_CHECKS = [
    ("بررسی موانع", "بنر زرد «در حال بررسی موانع…»؛ بدون فرم دانشجو"),
    ("مسدود", "پیام قرمز Pop-up با شماره تماس ۰۲۱۲۲۷۲۸۰۰۰"),
    ("نمایش دروس", "استپر، جدول دروس ثابت، کاشی شهریه، فرم تأیید مشاهده"),
    ("انتخاب پرداخت", "فرم نقدی/اقساطی (۲–۴ قسط)، کاشی روش پرداخت"),
    ("پرداخت", "ویجت سپ + راهنمای تازه‌سازی پس از بانک"),
    ("ثبت‌نام نهایی", "بلوک سبز تکمیل + اقساط باقی‌مانده (در صورت اقساط)"),
]


def _fa(text: str) -> str:
    if not text:
        return ""
    t = str(text).replace("\r", " ").replace("\n", " ")
    try:
        return get_display(arabic_reshaper.reshape(t))
    except Exception:
        return t


def _register_fonts(pdf: FPDF) -> None:
    if not FONT_REG.is_file():
        raise FileNotFoundError(f"فونت یافت نشد: {FONT_REG}")
    pdf.add_font("Vazir", "", str(FONT_REG))
    if FONT_BOLD.is_file():
        pdf.add_font("Vazir", "B", str(FONT_BOLD))


class GuidePDF(FPDF):
    def __init__(self) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self._footer_ts = jdatetime.datetime.now().strftime("%Y/%m/%d")

    def footer(self) -> None:
        self.set_y(-10)
        self.set_font("Vazir", "", _TINY)
        self.set_text_color(120, 120, 120)
        self.cell(
            0,
            5,
            _fa(
                f"راهنمای تست فرایند ۴۰ — آغاز ترم دوره جامع — {self._footer_ts} — ص {self.page_no()}"
            ),
            align="C",
        )


def _heading_style() -> FontFace:
    return FontFace(
        family="Vazir",
        emphasis="BOLD",
        size_pt=_SMALL,
        color=(30, 58, 95),
        fill_color=(220, 230, 245),
    )


class PdfBuilder:
    def __init__(self) -> None:
        self.pdf = GuidePDF()
        _register_fonts(self.pdf)
        self.pdf.set_margins(_MARGIN, _MARGIN, _MARGIN)
        self.pdf.set_auto_page_break(auto=True, margin=16)

    def _ensure_space(self, h: float = 20) -> None:
        p = self.pdf
        if p.get_y() + h > p.h - 18:
            p.add_page()

    def _section_bar(self, text: str) -> None:
        self._ensure_space(12)
        p = self.pdf
        p.set_fill_color(*_COLOR_SECTION_BG)
        p.set_text_color(*_COLOR_SECTION_TEXT)
        p.set_font("Vazir", "B", _SECTION)
        p.cell(0, 9, _fa(text), fill=True, align="R", new_x="LMARGIN", new_y="NEXT")
        p.set_text_color(30, 30, 30)
        p.ln(2)

    def _body(self, text: str, bold: bool = False) -> None:
        p = self.pdf
        p.set_font("Vazir", "B" if bold else "", _BODY)
        p.multi_cell(0, 5.8, _fa(text), align="R")
        p.ln(1)

    def _bullet_list(self, items: list[str]) -> None:
        for item in items:
            self._body(f"• {item}")

    def _numbered_list(self, items: list[str]) -> None:
        for i, item in enumerate(items, 1):
            self._body(f"{i}. {item}")

    def _ok_box(self, text: str) -> None:
        self._ensure_space(16)
        p = self.pdf
        p.set_fill_color(*_COLOR_OK_BG)
        p.set_font("Vazir", "B", _BODY)
        p.multi_cell(0, 5.8, _fa(f"نشانهٔ موفقیت: {text}"), align="R", fill=True)
        p.ln(2)

    def cover(self) -> None:
        p = self.pdf
        p.add_page()
        p.set_font("Vazir", "B", _TITLE)
        p.multi_cell(0, 10, _fa("راهنمای آزمایش UI"), align="C")
        p.ln(4)
        p.set_font("Vazir", "B", 13)
        p.multi_cell(0, 8, _fa("فرایند ۴۰ — آغاز ترم‌های دوره جامع"), align="C")
        p.ln(6)
        p.set_font("Vazir", "", _BODY)
        self._body(
            "این سند برای تست‌کنندهٔ UI است: ثبت‌نام ترم جدید دانشجوی دوره جامع، "
            "مشاهده دروس ثابت، انتخاب نقدی/اقساطی و پرداخت سپ."
        )

    def part_where(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۱ — کجا تست کنیم؟")
        self._numbered_list([
            "با حساب دانشجوی دوره جامع (course_type=comprehensive) وارد پورتال شوید.",
            "در داشبورد: کارت مسیر جاری (StudentQuestCard) باید پنل راهنمای فرایند ۴۰ را نشان دهد.",
            "در تب «فرایندها»: همان کارت بزرگ «آغاز ترم‌های دوره جامع (فرایند ۴۰)».",
            "فرایند معمولاً در پنجره ثبت‌نام ترم به‌صورت خودکار شروع می‌شود.",
        ])
        self._section_bar("بخش ۲ — در هر وضعیت چه ببینید؟")
        p = self.pdf
        with p.table(
            col_widths=(42, 138),
            width=p.epw,
            text_align=Align.R,
            line_height=5.5,
            borders_layout=TableBordersLayout.ALL,
            cell_fill_color=_COLOR_STRIPE,
            cell_fill_mode=TableCellFillMode.ROWS,
            padding=1.5,
        ) as table:
            hr = table.row()
            for h in [_fa("وضعیت"), _fa("انتظار UI")]:
                hr.cell(h, align=Align.C, style=_heading_style())
            for state, desc in STATE_CHECKS:
                row = table.row()
                row.cell(_fa(state))
                row.cell(_fa(desc))

    def part_scenario(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۳ — سناریوی ثبت‌نام موفق")
        self._numbered_list([
            "مسئول فنی instance را در course_display قرار دهد (دروس و شهریه در context).",
            "دانشجو جدول دروس و کاشی شهریه را ببیند؛ فرم را تأیید و «مشاهده دروس» را بزند.",
            "در payment_choice روش پرداخت (نقدی یا ۲–۴ قسط) را انتخاب کند.",
            "پس از «شروع پرداخت»، ویجت سپ نمایش داده شود.",
            "پس از پرداخت موفق (یا شبیه‌سازی callback)، وضعیت registration_complete شود.",
        ])
        self._ok_box("بلوک سبز «ثبت‌نام نهایی» و badge موفقیت در بالای کارت.")

    def part_blocked(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۴ — سناریوی مسدود (blocked)")
        self._body(
            "اگر دانشجو تعلیق یا مرخصی فعال دارد، فرایند به blocked می‌رود."
        )
        self._bullet_list([
            "پیام قرمز با متن SOP و شماره ۰۲۱۲۲۷۲۸۰۰۰",
            "استپر توقف (نه مراحل عادی)",
            "بدون فرم پرداخت یا سپ",
        ])

    def part_checklist(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۵ — چک‌لیست نهایی")
        checks = [
            "پنل فرایند ۴۰ در داشبورد و تب فرایندها دیده می‌شود",
            "استپر چهارمرحله‌ای (دروس → پرداخت → سپ → نهایی) درست است",
            "جدول دروس ثابت در course_display و payment_choice",
            "فرم پرداخت فقط در payment_choice",
            "سپ فقط یک‌بار (داخل پنل) نمایش داده می‌شود",
            "پس از پرداخت، registration_complete",
            "سناریوی blocked: پیام قرمز SOP",
        ]
        for c in checks:
            self._body(f"☐ {c}")
        self._body("امتیاز کلی (۱–۵): _____   نتیجه: ☐ تأیید  ☐ رد")

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.pdf.output(str(path))


def main() -> int:
    b = PdfBuilder()
    b.cover()
    b.part_where()
    b.part_scenario()
    b.part_blocked()
    b.part_checklist()
    b.save(OUT_PDF)
    print(f"Wrote {OUT_PDF}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
