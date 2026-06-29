#!/usr/bin/env python3
"""
راهنمای PDF اپراتور — فرایند ۳۸: ۱۲ ماه پس از گذشت قبولی به صورت مشروط در انترنی
(بدون جزئیات فنی؛ مناسب تست و پذیرش UI)

اجرا از ریشهٔ ریپو:
  python scripts/generate_internship_12month_conditional_review_operator_guide_pdf.py

خروجی:
  docs/راهنمای_تست_فرایند_۳۸_۱۲_ماه_مشروط_انترنی.pdf
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
OUT_PDF = ROOT / "docs" / "راهنمای_تست_فرایند_۳۸_۱۲_ماه_مشروط_انترنی.pdf"

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
    ("کمیته نظارت", "supervision_committee1", "demo123"),
    ("کمیته پیشرفت", "progress_committee1", "demo123"),
    ("مدیر سیستم (آماده‌سازی پروندهٔ آزمایشی)", "admin", "admin123"),
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
                f"راهنمای تست فرایند ۳۸ — ۱۲ ماه مشروط انترنی — {self._footer_ts} — ص {self.page_no()}"
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
            _fa("فرایند ۳۸ — ۱۲ ماه پس از گذشت قبولی به صورت مشروط در انترنی"),
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
                "این کتابچه به شما کمک می‌کند فرایند «ارزیابی مجدد انترن مشروط در ماه دوازدهم» "
                "را فقط از طریق پنل وب آزمایش کنید. "
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
            "شرط شروع این فرایند: انترنی که پذیرش اولیهٔ او «مشروط» بوده، وارد ماه دوازدهم دورهٔ انترنی شده باشد. "
            "برای آزمایش، از مسئول سامانه بخواهید یک پروندهٔ نمونه آماده کند یا فرایند را برای یک انترن آزمایشی فعال کند."
        )

    def part_what_is_process(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۱ — این فرایند چیست؟")
        self._body(
            "پس از یک سال فعالیت انترنی با پذیرش مشروط، انستیتو باید دوباره صلاحیت انترن را "
            "بررسی کند: آیا می‌تواند محدودیت‌های قبلی برداشته شود یا باید مسیر محدود ادامه یابد؟ "
            "این فرایند عمدتاً در پنل کمیته‌ها انجام می‌شود."
        )
        self._body("مراحل اصلی (به زبان ساده):", bold=True)
        self._numbered_list([
            "سامانه فرایند را برای انترن مشروط در ماه ۱۲ آغاز می‌کند (خودکار).",
            "کمیته نظارت وضعیت انضباطی را بررسی و مجوز ارزیابی مجدد را صادر می‌کند (یا رد می‌کند).",
            "کمیته پیشرفت تاریخ و ساعت مصاحبه ارزیابی را ثبت می‌کند — پیامک به دانشجو و مسئولین ارسال می‌شود.",
            "پس از برگزاری مصاحبه، مسئول علمی کمیته پیشرفت یکی از دو نتیجه را ثبت می‌کند:",
            "  • ادامه با رفع کامل محدودیت (الگوی استاندارد افزایش ساعات از ماه ۱۶)",
            "  • ادامه مشروط انترنی (الگوی محدودتر افزایش ساعات)",
        ])
        self._body("چه کسانی در این تست دخیل‌اند؟", bold=True)
        self._bullet_list([
            "کمیته نظارت — بررسی انضباطی و صدور یا عدم صدور مجوز.",
            "کمیته پیشرفت (مسئول پروژه) — تنظیم وقت مصاحبه.",
            "کمیته پیشرفت (مسئول علمی) — ثبت نتیجهٔ مصاحبه.",
            "دانشجو — فقط پیامک دعوت به مصاحبه دریافت می‌کند (در این نسخهٔ UI تمرکز روی پنل کمیته است).",
        ])

    def part_before_start(self) -> None:
        self._section_bar("بخش ۲ — قبل از آزمایش")
        self._numbered_list([
            "سامانه روشن باشد و بتوانید با حساب‌های آزمایشی وارد شوید.",
            "یک پروندهٔ فرایند ۳۸ برای انترن آزمایشی از قبل فعال شده باشد (از مسئول سامانه بپرسید).",
            "وضعیت فعلی پرونده باید در یکی از مراحل «بررسی نظارت»، «تنظیم وقت مصاحبه» یا «برگزاری مصاحبه» باشد.",
            "برای هر مرحله، پس از کار با یک نقش، «خروج» کنید و با نقش بعدی وارد شوید.",
            "در پنل کمیته: ابتدا فرم مرحله را تکمیل و «ثبت فرم این مرحله» را بزنید، سپس دکمهٔ تصمیم (انتقال) را بزنید.",
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
                "آدرس سایت + /login — تب «ورود با رمز عبور».",
            ),
            (
                "پنل کمیته نظارت",
                "/panel/portal/committee/supervision — تب «کارهای من» یا «بررسی‌ها» — "
                "پرونده‌های منتظر با عنوان «۱۲ ماه پس از گذشت قبولی به صورت مشروط در انترنی».",
            ),
            (
                "پنل کمیته پیشرفت",
                "/panel/portal/committee/progress — تب «کارهای من» — "
                "پرونده در مراحل «تنظیم وقت مصاحبه» یا «برگزاری مصاحبه».",
            ),
            (
                "جزئیات پرونده",
                "با کلیک روی پرونده: نام فرایند، وضعیت فعلی (فارسی)، فرم مرحله (آبی)، "
                "دکمه‌های تصمیم در پایین صفحه.",
            ),
        ]
        for title, desc in places:
            self._body(title, bold=True)
            self._body(desc)
        self._body("عناصر مهم که باید ببینید:", bold=True)
        self._bullet_list([
            "عنوان فارسی فرایند ۳۸ در لیست پرونده‌ها.",
            "وضعیت فعلی به فارسی (مثلاً «بررسی انضباطی و صدور مجوز کمیته نظارت»).",
            "فرم «تنظیم وقت مصاحبه ارزیابی مجدد» در مرحلهٔ تنظیم وقت.",
            "فرم «نتیجه مصاحبه ارزیابی مجدد» در مرحلهٔ برگزاری مصاحبه.",
            "دکمهٔ «صدور مجوز ارزیابی مجدد» یا «عدم صدور مجوز» در مرحلهٔ نظارت.",
            "دکمهٔ «مصاحبه تنظیم شد» پس از ثبت تاریخ و ساعت.",
            "دکمه‌های «ادامه با رفع کامل محدودیت» یا «ادامه مشروط انترنی» در مرحلهٔ نتیجه.",
        ])

    def part_scenario_happy_path(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۴ — سناریوی اصلی (مسیر موفق — رفع محدودیت)")
        self._ok_box(
            "در پایان، وضعیت «ادامه با رفع کامل محدودیت» نمایش داده شود و فرایند تکمیل شود."
        )

        steps = [
            (
                "گام ۱ — مجوز کمیته نظارت",
                "کمیته نظارت",
                [
                    "با حساب supervision_committee1 وارد پنل کمیته نظارت شوید.",
                    "در تب «کارهای من» پروندهٔ فرایند ۳۸ را پیدا و باز کنید.",
                    "وضعیت باید «بررسی انضباطی و صدور مجوز کمیته نظارت» باشد.",
                    "پس از بررسی پرونده انضباطی، دکمهٔ «صدور مجوز ارزیابی مجدد» را بزنید.",
                ],
                "وضعیت به «تنظیم وقت مصاحبه ارزیابی مجدد» برود.",
            ),
            (
                "گام ۲ — تنظیم وقت مصاحبه",
                "کمیته پیشرفت",
                [
                    "خروج کنید. با progress_committee1 وارد پنل کمیته پیشرفت شوید.",
                    "در تب «کارهای من» همان پرونده را باز کنید.",
                    "فرم «تنظیم وقت مصاحبه ارزیابی مجدد» را پر کنید:",
                    "  — تاریخ مصاحبه (الزامی)",
                    "  — ساعت مصاحبه (الزامی)",
                    "  — لینک جلسه (اگر آنلاین) یا مکان برگزاری (اگر حضوری)",
                    "دکمهٔ «ثبت فرم این مرحله» را بزنید.",
                    "سپس دکمهٔ «مصاحبه تنظیم شد» (یا معادل آن) را بزنید.",
                ],
                "وضعیت به «برگزاری مصاحبه» برود. پیامک با تاریخ و ساعت ارسال شود.",
            ),
            (
                "گام ۳ — ثبت نتیجه مصاحبه",
                "کمیته پیشرفت (مسئول علمی)",
                [
                    "همان پرونده را در پنل کمیته پیشرفت باز کنید.",
                    "وضعیت باید «برگزاری مصاحبه» باشد.",
                    "فرم «نتیجه مصاحبه ارزیابی مجدد» را باز کنید.",
                    "گزینهٔ «ادامه با رفع کامل محدودیت» را انتخاب کنید.",
                    "فرم را ثبت کنید؛ سپس دکمهٔ «ادامه با رفع کامل محدودیت» را بزنید.",
                ],
                "وضعیت نهایی «ادامه با رفع کامل محدودیت» — فرایند تکمیل شده.",
            ),
        ]
        for title, role, actions, expect in steps:
            self._body(title, bold=True)
            self._body(f"نقش: {role}")
            self._numbered_list(actions)
            self._ok_box(expect)
            self.pdf.ln(1)

    def part_scenario_conditional(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۵ — سناریوی دوم (ادامه مشروط)")
        self._body(
            "اگر می‌خواهید مسیر «ادامه مشروط» را هم آزمایش کنید، یک پروندهٔ جدید "
            "یا بازگشت به مرحلهٔ قبل (با کمک مسئول سامانه) لازم است."
        )
        self._numbered_list([
            "گام‌های ۱ و ۲ را مانند بخش ۴ انجام دهید.",
            "در گام ۳، به‌جای «رفع کامل محدودیت»، گزینهٔ «ادامه مشروط انترنی» را انتخاب کنید.",
            "فرم را ثبت کنید و دکمهٔ «ادامه مشروط انترنی» را بزنید.",
        ])
        self._ok_box(
            "وضعیت نهایی «ادامه مشروط انترنی» — فرایند تکمیل شده."
        )

    def part_scenario_rejections(self) -> None:
        self._section_bar("بخش ۶ — سناریوی رد (عدم مجوز نظارت)")
        self._numbered_list([
            "با حساب کمیته نظارت پرونده را در مرحلهٔ «بررسی انضباطی» باز کنید.",
            "به‌جای صدور مجوز، دکمهٔ «عدم صدور مجوز» (یا معادل ارجاع به تخلفات) را بزنید.",
        ])
        self._ok_box(
            "وضعیت به «عدم مجوز — ارجاع به تخلفات» برود و فرایند در همان نقطه متوقف شود."
        )
        self._warn_box(
            "تا زمان تعیین تکلیف تخلف، ادامهٔ این فرایند ممکن نیست. "
            "این رفتار درست است و نباید به مرحلهٔ مصاحبه برود."
        )

    def part_committee_ui(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۷ — چک‌لیست پنل کمیته")
        self._body("برای هر مورد در پنل کمیته بررسی کنید:")
        self._check_table([
            "پروندهٔ فرایند ۳۸ در تب «کارهای من» کمیته نظارت (مرحلهٔ نظارت) دیده می‌شود",
            "پروندهٔ فرایند ۳۸ در تب «کارهای من» کمیته پیشرفت (مراحل مصاحبه) دیده می‌شود",
            "عنوان فارسی فرایند درست و قابل فهم است",
            "وضعیت فعلی به فارسی و مطابق مرحلهٔ کاری نمایش داده می‌شود",
            "فرم «تنظیم وقت مصاحبه» در مرحلهٔ interview_scheduling باز می‌شود",
            "فیلدهای تاریخ، ساعت، لینک و مکان در فرم تنظیم وقت وجود دارند",
            "فرم «نتیجه مصاحبه» در مرحلهٔ برگزاری مصاحبه باز می‌شود",
            "دو گزینهٔ نتیجه (رفع محدودیت / ادامه مشروط) در فرم دیده می‌شوند",
            "نام یا کد دانشجو در جزئیات پرونده مشخص است",
            "پس از ثبت فرم، دکمهٔ تصمیم فعال می‌شود",
            "بستن و باز کردن مجدد پرونده — اطلاعات ثبت‌شده از بین نمی‌رود",
            "پس از تکمیل، وضعیت نهایی به‌درستی نمایش داده می‌شود",
        ])

    def part_sms_check(self) -> None:
        self._section_bar("بخش ۸ — بررسی پیامک (در صورت فعال بودن ارسال)")
        self._body(
            "پس از ثبت وقت مصاحبه (گام ۲ بخش ۴)، در صورت فعال بودن سرویس پیامک در محیط آزمایش:"
        )
        self._check_table([
            "پیامک به دانشجو با نام، تاریخ و ساعت مصاحبه ارسال شد",
            "متن پیامک فارسی و قابل فهم است",
            "لینک یا مکان برگزاری در پیامک ذکر شده است",
            "پیامک به مسئولین کمیته پیشرفت (در صورت تنظیم شماره) ارسال شد",
        ])
        self._tip_box(
            "اگر پیامک در محیط آزمایش ارسال نشد، از مسئول سامانه بپرسید آیا شبیه‌ساز پیامک فعال است."
        )

    def part_acceptance(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۹ — تأیید نهایی اپراتور")
        self._check_table([
            "مسیر موفق (رفع محدودیت) بدون کمک فنی قابل طی بود",
            "فرم تنظیم وقت مصاحبه به‌درستی کار کرد",
            "فرم نتیجه مصاحبه به‌درستی کار کرد",
            "عدم مجوز نظارت پرونده را درست متوقف کرد",
            "پرونده در «کارهای من» هر کمیته در مرحلهٔ مناسب ظاهر شد",
            "متن‌ها فارسی، بدون اصطلاح گیج‌کننده و بدون خطای واضح",
            "این فرایند با فرایند ۳۷ (آغاز انترنی) یا مرخصی اشتباه گرفته نشد",
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
            "تجربهٔ اپراتورها و انترن‌ها سپاسگزاریم.",
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
    builder.part_scenario_conditional()
    builder.part_scenario_rejections()
    builder.part_committee_ui()
    builder.part_sms_check()
    builder.part_acceptance()
    builder.summary()
    builder.save(OUT_PDF)
    print(f"PDF written: {OUT_PDF}")
    print(f"Size: {OUT_PDF.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
