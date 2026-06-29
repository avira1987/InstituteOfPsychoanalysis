#!/usr/bin/env python3
"""
راهنمای PDF اپراتور — فرایند ۳۷: مشورت و تعیین آمادگی برای آغاز انترنی
(بدون جزئیات فنی؛ مناسب تست و پذیرش UI)

اجرا از ریشهٔ ریپو:
  python scripts/generate_internship_readiness_consultation_operator_guide_pdf.py

خروجی:
  docs/راهنمای_تست_فرایند_۳۷_آغاز_انترنی.pdf
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
OUT_PDF = ROOT / "docs" / "راهنمای_تست_فرایند_۳۷_آغاز_انترنی.pdf"

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

ACCOUNTS = [
    ("دانشجو (پاس تئوری تکنیک ۳)", "از مسئول فنی بپرسید", "demo123"),
    ("کمیته نظارت", "supervision_committee1", "demo123"),
    ("کمیته پیشرفت", "progress_committee1", "demo123"),
    ("مدیر سیستم (پشتیبان)", "admin", "admin123"),
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
                f"راهنمای تست فرایند ۳۷ — آغاز انترنی — {self._footer_ts} — ص {self.page_no()}"
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

    def _body(self, text: str, bold: bool = False, size: float | None = None) -> None:
        p = self.pdf
        p.set_font("Vazir", "B" if bold else "", size or _BODY)
        p.multi_cell(0, 5.8, _fa(text), align="R")
        p.ln(1)

    def _bullet_list(self, items: list[str]) -> None:
        for item in items:
            self._body(f"• {item}")

    def _numbered_list(self, items: list[str]) -> None:
        for i, item in enumerate(items, 1):
            self._body(f"{i}. {item}")

    def _tip_box(self, text: str) -> None:
        self._ensure_space(16)
        p = self.pdf
        p.set_fill_color(*_COLOR_TIP_BG)
        p.set_font("Vazir", "B", _BODY)
        p.multi_cell(0, 5.8, _fa(f"نکته: {text}"), align="R", fill=True)
        p.ln(2)

    def _warn_box(self, text: str) -> None:
        self._ensure_space(16)
        p = self.pdf
        p.set_fill_color(*_COLOR_WARN_BG)
        p.set_font("Vazir", "B", _BODY)
        p.multi_cell(0, 5.8, _fa(f"توجه: {text}"), align="R", fill=True)
        p.ln(2)

    def _ok_box(self, text: str) -> None:
        self._ensure_space(16)
        p = self.pdf
        p.set_fill_color(*_COLOR_OK_BG)
        p.set_font("Vazir", "B", _BODY)
        p.multi_cell(0, 5.8, _fa(f"نشانهٔ موفقیت: {text}"), align="R", fill=True)
        p.ln(2)

    def _blank_lines(self, label: str, n: int = 3) -> None:
        self._ensure_space(8 + n * 7)
        p = self.pdf
        p.set_font("Vazir", "B", _BODY)
        p.cell(0, 6, _fa(label), new_x="LMARGIN", new_y="NEXT")
        p.set_font("Vazir", "", _BODY)
        p.set_draw_color(*_COLOR_BORDER)
        for _ in range(n):
            y = p.get_y()
            p.line(_MARGIN, y + 4, p.w - _MARGIN, y + 4)
            p.ln(7)

    def _check_table(self, questions: list[str]) -> None:
        self._ensure_space(12 + len(questions) * 6)
        p = self.pdf
        hs = _heading_style()
        rows = [[_fa("سؤال"), _fa("بله"), _fa("خیر"), _fa("توضیح")]]
        for q in questions:
            rows.append([_fa(q), "", "", ""])
        with p.table(
            col_widths=(88, 11, 11, 70),
            width=p.epw,
            first_row_as_headings=False,
            text_align=Align.R,
            v_align=VAlign.M,
            line_height=5.5,
            borders_layout=TableBordersLayout.ALL,
            cell_fill_color=_COLOR_STRIPE,
            cell_fill_mode=TableCellFillMode.ROWS,
            padding=1.5,
        ) as table:
            for i, row in enumerate(rows):
                r = table.row()
                for j, cell in enumerate(row):
                    style = hs if i == 0 and j == 0 else None
                    r.cell(cell, align=Align.R if j == 0 else Align.C, style=style)
        p.ln(2)

    def cover(self) -> None:
        p = self.pdf
        p.add_page()
        p.set_font("Vazir", "B", _TITLE)
        p.ln(8)
        p.cell(0, 12, _fa("راهنمای آزمایش و استفاده"), align="C", new_x="LMARGIN", new_y="NEXT")
        p.set_font("Vazir", "B", 12)
        p.cell(
            0,
            10,
            _fa("فرایند ۳۷ — مشورت و تعیین آمادگی برای آغاز انترنی"),
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        p.set_font("Vazir", "", 10)
        p.cell(
            0,
            8,
            _fa("انستیتو روانکاوی تهران — برای اپراتور و کاربر آزمایشی"),
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        p.ln(6)
        p.set_font("Vazir", "", _BODY)
        p.multi_cell(
            0,
            6,
            _fa(
                "این کتابچه به شما کمک می‌کند مسیر «ارتقا به انترن» را از درخواست دانشجو "
                "تا آغاز سوپرویژن، فقط از طریق پنل وب آزمایش کنید. "
                "نیازی به دانش فنی ندارید؛ کافی است وارد سایت شوید، مراحل را طی کنید "
                "و آنچه می‌بینید را با این راهنما مقایسه کنید."
            ),
            align="R",
        )
        p.ln(4)
        for label, blank in [
            ("نام اپراتور / آزمایش‌کننده", "________________________"),
            ("تاریخ آزمایش", "________________________"),
            ("آدرس سایت", "________________________"),
            ("نتیجه کلی", "[ ] تأیید  [ ] تأیید مشروط  [ ] رد"),
        ]:
            p.cell(0, 8, _fa(f"{label}: {blank}"), align="R", new_x="LMARGIN", new_y="NEXT")
        p.ln(2)
        self._warn_box(
            "شرط شروع این فرایند: دانشجو درس «تئوری تکنیک ۳» را پاس کرده باشد. "
            "اگر پروندهٔ نمونه ندارید، از مسئول فنی بخواهید یک دانشجوی آزمایشی آماده کند."
        )

    def part_what_is_process(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۱ — این فرایند چیست؟")
        self._body(
            "این فرایند، گذار از «دانشجویی» به «انترنی» (درمان تحت نظارت) است. "
            "قبل از شروع کار با بیمار، کمیته نظارت و کمیته پیشرفت صلاحیت دانشجو را "
            "بررسی می‌کنند؛ سپس قراردادها و سفته دریافت می‌شود؛ در نهایت دانشجو "
            "سوپروایزر و زمان جلسه را انتخاب و هزینهٔ جلسهٔ اول را می‌پردازد."
        )
        self._body("مراحل اصلی (به زبان ساده):", bold=True)
        self._numbered_list([
            "دانشجو درخواست ارتقا به انترن را ثبت می‌کند.",
            "کمیته نظارت مجوز می‌دهد یا رد می‌کند.",
            "کمیته پیشرفت وقت مصاحبه را تنظیم می‌کند و مصاحبه برگزار می‌شود.",
            "نتیجه مصاحبه: قبولی ۳ ساعت، قبولی ۱ ساعت، یا درخواست دوباره پس از ۳۰ ساعت درمان.",
            "دانشجو قراردادها را امضا می‌کند و سفته را حضوری تحویل می‌دهد.",
            "بررسی وجود بیمار برای ارجاع.",
            "انتخاب سوپروایزر و پرداخت جلسهٔ اول.",
            "انترنی آغاز می‌شود.",
        ])
        self._body("چه کسانی در این تست دخیل‌اند؟", bold=True)
        self._bullet_list([
            "دانشجو — درخواست، قراردادها، انتخاب سوپروایزر، پرداخت.",
            "کمیته نظارت — مجوز اولیه و بررسی بیمار.",
            "کمیته پیشرفت — تنظیم مصاحبه، ثبت نتیجه، دریافت سفته.",
        ])

    def part_before_start(self) -> None:
        self._section_bar("بخش ۲ — قبل از آزمایش")
        self._numbered_list([
            "سامانه روشن باشد و بتوانید با حساب‌های آزمایشی وارد شوید.",
            "دانشجوی نمونه «تئوری تکنیک ۳» را پاس کرده باشد (یا فرایند از قبل برای او فعال شده باشد).",
            "برای هر مرحله، پس از کار با یک نقش، «خروج» کنید و با نقش بعدی وارد شوید.",
            "در پنل کمیته: ابتدا فرم مرحله را تکمیل و «ثبت» کنید، سپس دکمهٔ تصمیم (انتقال) را بزنید.",
        ])
        self._tip_box(
            "اگر دکمهٔ تصمیم کار نکرد، احتمالاً فرم همان مرحله هنوز ثبت نشده است."
        )
        self._section_bar("حساب‌های پیشنهادی")
        p = self.pdf
        with p.table(
            col_widths=(70, 55, 35),
            width=p.epw,
            text_align=Align.R,
            line_height=5.5,
            borders_layout=TableBordersLayout.ALL,
            cell_fill_color=_COLOR_STRIPE,
            cell_fill_mode=TableCellFillMode.ROWS,
            padding=1.5,
        ) as table:
            hr = table.row()
            for h in [_fa("نقش"), _fa("نام کاربری"), _fa("رمز (نمونه)")]:
                hr.cell(h, align=Align.C, style=_heading_style())
            for role, user, pw in ACCOUNTS:
                row = table.row()
                row.cell(_fa(role))
                row.cell(user, align=Align.C)
                row.cell(pw, align=Align.C)
        p.ln(4)

    def part_where_ui(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۳ — صفحات مهم در سامانه")
        places = [
            (
                "ورود",
                "آدرس سایت + /login — تب «ورود با رمز عبور»."
            ),
            (
                "پورتال دانشجو",
                "/panel/portal/student — تب «فرایندها» — باز کردن فرایند «مشورت و تعیین آمادگی برای آغاز انترنی»."
            ),
            (
                "کارت راهنمای فرایند ۳۷ (دانشجو)",
                "بالای صفحهٔ جزئیات فرایند: نوار مراحل (۷ قدم)، متن راهنمای وضعیت فعلی، "
                "جزئیات مصاحبه، نتیجه، سوپروایزر و درگاه پرداخت (در مرحلهٔ پرداخت)."
            ),
            (
                "یادآور سفته در پروفایل",
                "تب «پروفایل» دانشجو — وقتی در مرحلهٔ «تحویل سفته» است، بنر زرد یادآور دیده می‌شود."
            ),
            (
                "پنل کمیته نظارت",
                "/panel/portal/committee/supervision — تب «بررسی‌ها» — پرونده‌های منتظر."
            ),
            (
                "پنل کمیته پیشرفت",
                "/panel/portal/committee/progress — تب «بررسی‌ها» — مصاحبه و سفته."
            ),
        ]
        for title, desc in places:
            self._body(title, bold=True)
            self._body(desc)
        self._body("عناصر مهم که باید ببینید:", bold=True)
        self._bullet_list([
            "نوار مراحل با مشخص بودن «مرحلهٔ فعلی».",
            "متن راهنمای آبی برای هر وضعیت (فارسی و قابل فهم).",
            "در رد یا توقف: پیام قرمز با توضیح روشن.",
            "در پایان موفق: پیام سبز «انترنی آغاز شد».",
        ])

    def part_scenario_happy_path(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۴ — سناریوی اصلی (مسیر موفق)")
        self._ok_box(
            "در پایان، وضعیت «انترنی آغاز شد» و پیام تبریک سبز نمایش داده شود."
        )

        steps = [
            (
                "گام ۱ — درخواست دانشجو",
                "دانشجو",
                [
                    "وارد پورتال دانشجو شوید و فرایند ۳۷ را باز کنید.",
                    "درخواست ارتقا به انترن را ثبت و ارسال کنید.",
                    "در نوار مراحل، «درخواست ارتقا» انجام‌شده و «بررسی کمیته نظارت» فعال باشد.",
                ],
                "وضعیت به «بررسی کمیته نظارت» برود.",
            ),
            (
                "گام ۲ — مجوز کمیته نظارت",
                "کمیته نظارت",
                [
                    "در تب بررسی‌ها پرونده را باز کنید.",
                    "بلوک راهنمای زرد «بررسی مجوز آغاز انترنی» را ببینید.",
                    "پس از بررسی، دکمهٔ تأیید (صدور مجوز) را بزنید.",
                ],
                "وضعیت به «تنظیم وقت مصاحبه» برود.",
            ),
            (
                "گام ۳ — تنظیم مصاحبه",
                "کمیته پیشرفت",
                [
                    "پرونده را در پنل کمیته پیشرفت باز کنید.",
                    "فرم «تعیین وقت مصاحبه انترنی» را پر کنید: تاریخ، ساعت، حضوری یا آنلاین.",
                    "فرم را ثبت کنید؛ سپس دکمهٔ «مصاحبه تنظیم شد» را بزنید.",
                ],
                "وضعیت «برگزاری مصاحبه» — دانشجو تاریخ و ساعت را در کارت خود ببیند.",
            ),
            (
                "گام ۴ — نتیجه مصاحبه",
                "کمیته پیشرفت (مسئول علمی)",
                [
                    "فرم «نتیجه مصاحبه انترنی» را باز کنید.",
                    "یکی از سه گزینه را انتخاب کنید: قبولی ۳ ساعت / ۱ ساعت / درخواست دوباره.",
                    "فرم را ثبت و تصمیم را بزنید.",
                ],
                "برای قبولی: «ساعت مجاز درمان هفتگی» (۳ یا ۱) در کارت دانشجو دیده شود.",
            ),
            (
                "گام ۵ — قراردادها و سفته",
                "دانشجو + کمیته پیشرفت",
                [
                    "دانشجو: قرارداد پرکیس و قوانین را با کد پیامکی امضا کند.",
                    "دانشجو: سفته را حضوری تحویل دهد — بنر زرد در پروفایل و کارت فرایند.",
                    "کمیته پیشرفت: «سفته دریافت شد» را ثبت کند.",
                ],
                "وضعیت به بررسی بیمار برود.",
            ),
            (
                "گام ۶ — بیمار و سوپروایزر",
                "کمیته نظارت + دانشجو",
                [
                    "کمیته نظارت: در صورت وجود بیمار، تأیید کند.",
                    "دانشجو: سوپروایزر و زمان را از فهرست انتخاب کند.",
                    "دانشجو: هزینهٔ جلسهٔ اول را در همان صفحه (درگاه پرداخت) بپردازد.",
                ],
                "وضعیت «انترنی آغاز شد» و پیام سبز تبریک.",
            ),
        ]
        for title, role, actions, expect in steps:
            self._body(title, bold=True)
            self._body(f"نقش: {role}")
            self._numbered_list(actions)
            self._ok_box(expect)
            self.pdf.ln(1)

    def part_scenario_rejections(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۵ — سناریوهای رد و توقف")
        scenarios = [
            (
                "رد توسط کمیته نظارت",
                "کمیته نظارت",
                [
                    "در مرحلهٔ بررسی مجوز، به‌جای تأیید، «رد» را بزنید.",
                    "با حساب دانشجو فرایند را باز کنید.",
                ],
                "پیام قرمز: کمیته نظارت مجوز نداد — نوار مراحل متوقف شود.",
            ),
            (
                "نتیجه مصاحبه: درخواست دوباره (۳۰ ساعت درمان)",
                "کمیته پیشرفت",
                [
                    "در فرم نتیجه، گزینهٔ «درخواست دوباره پس از ۳۰ ساعت درمان» را انتخاب کنید.",
                    "با حساب دانشجو وضعیت را ببینید.",
                ],
                "پیام قرمز توضیح‌دهنده — فرایند متوقف شود.",
            ),
            (
                "منتظر بیمار",
                "کمیته نظارت",
                [
                    "در مرحلهٔ بررسی بیمار، «بیمار موجود نیست» را ثبت کنید.",
                    "کارت دانشجو را ببینید.",
                ],
                "راهنمای «منتظر بیمار» — بدون گیرکردن غیرمنطقی صفحه.",
            ),
        ]
        for title, role, actions, expect in scenarios:
            self._body(title, bold=True)
            self._body(f"نقش: {role}")
            self._numbered_list(actions)
            self._ok_box(expect)
            self.pdf.ln(1)

    def part_committee_ui(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۶ — چک‌لیست پنل کمیته")
        self._body("برای هر مورد در پنل کمیته بررسی کنید:")
        self._check_table([
            "پرونده در تب «بررسی‌ها» / «منتظر» دیده می‌شود",
            "بلوک راهنمای رنگی (زرد نظارت / سبز پیشرفت) نمایش داده می‌شود",
            "فرم «تعیین وقت مصاحبه» در مرحلهٔ تنظیم وقت باز می‌شود",
            "فرم «نتیجه مصاحبه» در مرحلهٔ برگزاری مصاحبه باز می‌شود",
            "راهنمای ثبت سفته در مرحلهٔ تحویل سفته نمایش داده می‌شود",
            "نام یا کد دانشجو در بلوک راهنما دیده می‌شود",
            "پس از ثبت فرم، دکمهٔ تصمیم فعال می‌شود",
            "بستن و باز کردن مجدد پرونده — اطلاعات از بین نمی‌رود",
        ])

    def part_student_ui(self) -> None:
        self._section_bar("بخش ۷ — چک‌لیست پنل دانشجو")
        self._check_table([
            "کارت «فرایند ۳۷» با عنوان فارسی درست نمایش داده می‌شود",
            "نوار ۷ مرحله‌ای و «مرحلهٔ فعلی» مشخص است",
            "متن راهنمای آبی برای هر وضعیت مناسب و فارسی است",
            "پس از تنظیم مصاحبه: تاریخ، ساعت و حضوری/آنلاین دیده می‌شود",
            "پس از نتیجه مصاحبه: نوع قبولی و ساعت مجاز (۳ یا ۱) نمایش داده می‌شود",
            "در مرحلهٔ سفته: بنر زرد در کارت و پروفایل دیده می‌شود",
            "پس از انتخاب سوپروایزر: نام و زمان در کارت نمایش داده می‌شود",
            "در مرحلهٔ پرداخت: درگاه پرداخت (سپ) در همان صفحه باز می‌شود",
            "در پایان: پیام سبز «انترنی آغاز شد»",
        ])

    def part_acceptance(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۸ — تأیید نهایی اپراتور")
        self._check_table([
            "مسیر موفق (بخش ۴) بدون کمک فنی قابل طی بود",
            "رد نظارت و نتیجه «۳۰ ساعت» به‌درستی به دانشجو نشان داده شد",
            "راهنماهای کمیته واضح و قابل اجرا بودند",
            "فرم‌های مصاحبه مطابق انتظار کار می‌کنند",
            "پرداخت جلسهٔ اول در صفحهٔ دانشجو در دسترس بود",
            "متن‌ها فارسی، بدون اصطلاح گیج‌کننده و بدون خطای واضح",
            "این فرایند با ثبت‌نام دوره یا مرخصی اشتباه گرفته نشد",
        ])
        self._blank_lines("سه مشکل مهم (در صورت وجود):", 3)
        self._blank_lines("پیشنهاد برای بهتر شدن:", 2)
        self._body("امتیاز کلی (۱ = ضعیف — ۵ = عالی):  [ ] ۱  [ ] ۲  [ ] ۳  [ ] ۴  [ ] ۵")
        self._blank_lines("امضا / تاریخ:", 1)

    def summary(self) -> None:
        self._section_bar("پایان — ارسال گزارش")
        self._body(
            "این PDF را پر کنید و همراه عکس از صفحات مهم برای مدیر پروژه "
            "یا مسئول سامانه بفرستید. از همکاری شما برای بهتر شدن "
            "تجربهٔ دانشجویان سپاسگزاریم.",
            bold=True,
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.pdf.output(str(path))


def main() -> int:
    builder = PdfBuilder()
    builder.cover()
    builder.part_what_is_process()
    builder.part_before_start()
    builder.part_where_ui()
    builder.part_scenario_happy_path()
    builder.part_scenario_rejections()
    builder.part_committee_ui()
    builder.part_student_ui()
    builder.part_acceptance()
    builder.summary()
    builder.save(OUT_PDF)
    print(f"PDF written: {OUT_PDF}")
    print(f"Size: {OUT_PDF.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
