#!/usr/bin/env python3
"""
راهنمای PDF اپراتور — فرایند ۱۸: مدیریت تغییرات سوپرویژن فردی
(آغاز مجدد، تغییر سوپروایزر، تغییر ساعت — بدون جزئیات فنی)

اجرا از ریشهٔ ریپو:
  python scripts/generate_supervision_block_transition_guide_pdf.py

خروجی:
  docs/راهنمای_تست_فرایند_۱۸_مدیریت_تغییرات_سوپرویژن_فردی.pdf
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
OUT_PDF = ROOT / "docs" / "راهنمای_تست_فرایند_۱۸_مدیریت_تغییرات_سوپرویژن_فردی.pdf"

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

PROCESS_TITLE = (
    "مدیریت تغییرات سوپرویژن فردی "
    "(آغاز مجدد، تغییر سوپروایزر، تغییر ساعت)"
)


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
                f"راهنمای تست فرایند ۱۸ — تغییرات سوپرویژن فردی — {self._footer_ts} — ص {self.page_no()}"
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


CHANGE_TYPES = [
    (
        "تغییر سوپروایزر",
        "سوپروایزر فعلی به فهرست گذشته می‌رود (با ساعات گذرانده‌شده). "
        "سوپروایزر و زمان جدید جایگزین می‌شود. وقت آزاد سوپروایزر قبلی "
        "دوباره در شیت وقت‌ها قرار می‌گیرد.",
    ),
    (
        "آغاز مجدد سوپرویژن",
        "برای شروع اولین بلوک یا از سرگیری پس از وقفه. "
        "روز، ساعت و نام سوپروایزر در پرونده ثبت می‌شود.",
    ),
    (
        "تغییر ساعت (همان سوپروایزر)",
        "ساعات جدید جایگزین برنامه فعلی می‌شود. "
        "زمان‌های قبلی به شیت وقت‌های آزاد سوپروایزر برمی‌گردد.",
    ),
]

STAGES = [
    {
        "name": "قصد پرداخت جلسهٔ پنجاهم",
        "student_sees": (
            "کارت «مسیر فعلی» یا تب «فرایندها» با عنوان "
            "«مدیریت تغییرات سوپرویژن فردی» و بلوک بنفش راهنما: "
            "«حضور در بلوک فعلی»، «تا جلسه ۵۰»، و سه کارت راهنمای "
            "انواع تغییر (تغییر سوپروایزر، آغاز مجدد، تغییر ساعت)."
        ),
        "student_does": (
            "دکمهٔ «ادامه و ثبت مرحله» را بزند تا سامانه "
            "بررسی کند آیا واقعاً به جلسهٔ پنجاهم رسیده یا نه."
        ),
        "operator_checks": [
            "اگر هنوز به جلسه ۵۰ نرسیده، پیام یا هدایت منطقی دیده شود.",
            "اگر به جلسه ۵۰ رسیده، مرحلهٔ بعد (نمایش وقت‌ها) باز شود.",
            "سه کارت «انواع تغییر» فارسی و قابل فهم باشند.",
            "متن‌ها بدون اصطلاح گیج‌کننده باشند.",
        ],
    },
    {
        "name": "نمایش سوابق و وقت‌های آزاد",
        "student_sees": (
            "پیام نارنجی «الزام انتقال بلوک»، جدول «سوابق بلوک‌های "
            "۵۰ ساعته»، جدول «وقت‌های آزاد سوپروایزرها»، "
            "و نوار چهار مرحله‌ای مسیر پرداخت در بالای صفحه."
        ),
        "student_does": (
            "سوابق گذشته را بخواند؛ در فرم پایین صفحه یک "
            "سوپروایزر و یک روز و ساعت انتخاب کند؛ "
            "فرم را ثبت کند؛ سپس «ادامه و ثبت مرحله» را بزنید."
        ),
        "operator_checks": [
            "پیام الزام دقیقاً معنای «اول بلوک بعد را انتخاب کن» را می‌رساند.",
            "جدول سوابق (در صورت وجود داده) سوپروایزر و ساعت را نشان می‌دهد.",
            "حداکثر یک جلسه در هفته در راهنما ذکر شده باشد.",
            "بدون پر کردن فرم، ادامه مسدود یا هشدار دهد.",
        ],
    },
    {
        "name": "انتخاب انجام شد — پرداخت جلسه اول بلوک بعد",
        "student_sees": (
            "پیش‌نمایش «انتخاب شما»، «تاریخ آغاز (قانون ۲۴ ساعت)» "
            "و بخش «پرداخت آنلاین» برای جلسهٔ اول دورهٔ جدید."
        ),
        "student_does": (
            "مبلغ را ببیند؛ دکمهٔ پرداخت را بزند؛ "
            "در محیط آزمایشی درگاه را طی کند؛ "
            "پس از بازگشت صفحه را یک‌بار تازه (F5) کند."
        ),
        "operator_checks": [
            "توضیح پرداخت: «جلسه اول دوره سوپرویژن جدید».",
            "تاریخ شروع منطقی است (اگر کمتر از ۲۴ ساعت مانده، هفته بعد).",
            "پس از پرداخت موفق، قفل جلسه ۵۰ «باز» نشان داده شود.",
        ],
    },
    {
        "name": "پرداخت جلسه پنجاهم دوره فعلی",
        "student_sees": (
            "پیام سبز «قفل پرداخت جلسه ۵۰ام باز شد» "
            "و بخش پرداخت برای «جلسه ۵۰ام دوره فعلی»."
        ),
        "student_does": (
            "دومین پرداخت را انجام دهد؛ "
            "پس از موفقیت صفحه را تازه کند."
        ),
        "operator_checks": [
            "بدون پرداخت اول، امکان پرداخت جلسه ۵۰ نباید باز باشد.",
            "پس از هر دو پرداخت، وضعیت «تکمیل» دیده شود.",
            "جزئیات سوپروایزر جدید و تاریخ آغاز در پیام پایانی باشد.",
        ],
    },
    {
        "name": "تکمیل و اطلاع‌رسانی",
        "student_sees": (
            "پیام «انتقال بلوک و هر دو پرداخت با موفقیت انجام شد»؛ "
            "فرایند بسته شده؛ در تاریخچهٔ پیامک (در همان کارت) "
            "متن اطلاع‌رسانی دیده شود."
        ),
        "student_does": "نیازی به اقدام نیست؛ وضعیت را مرور کند.",
        "operator_checks": [
            "فرایند در لیست «تکمیل‌شده» قرار گرفته باشد.",
            "پیامک (در آزمایش: تاریخچه در پورتال) به دانشجو و سوپروایزر جدید.",
            "سوابق بلوک جدید در پرونده (در صورت دسترسی) به‌روز شده باشد.",
        ],
    },
]


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
        p.set_font("Vazir", "B", 11.5)
        p.cell(0, 10, _fa(f"فرایند ۱۸ — {PROCESS_TITLE}"), align="C", new_x="LMARGIN", new_y="NEXT")
        p.set_font("Vazir", "", 10)
        p.cell(
            0,
            8,
            _fa("انستیتو روانکاوی تهران — برای اپراتور آزمایش و پذیرش"),
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
                "این کتابچه به شما کمک می‌کند صفحهٔ «مدیریت تغییرات سوپرویژن فردی» "
                "را در پورتال دانشجو امتحان کنید و مطمئن شوید همهٔ مراحل "
                "درست کار می‌کند. نیازی به دانش فنی ندارید؛ فقط باید "
                "بتوانید وارد سایت شوید، آنچه می‌بینید را با این راهنما "
                "مقایسه کنید و در پایان چک‌لیست را پر کنید."
            ),
            align="R",
        )
        p.ln(4)
        for label, blank in [
            ("نام اپراتور / آزمایش‌کننده", "________________________"),
            ("تاریخ آزمایش", "________________________"),
            ("آدرس سایت (از مسئول پروژه)", "________________________"),
            ("حساب دانشجوی آزمایشی (از مسئول پروژه)", "________________________"),
            ("نتیجه کلی", "☐ تأیید   ☐ تأیید مشروط   ☐ رد"),
        ]:
            p.cell(0, 8, _fa(f"{label}: {blank}"), align="R", new_x="LMARGIN", new_y="NEXT")
        p.ln(2)
        self._warn_box(
            "قبل از شروع، مسئول پروژه باید سامانه را روشن کرده باشد "
            "و پروندهٔ نمونهٔ دانشجو (نزدیک جلسهٔ ۵۰ سوپرویژن) آماده باشد."
        )

    def part_what_is_process(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۱ — این فرایند چیست؟")
        self._body(
            "این فرایند برای ساماندهی تغییرات در «سوپرویژن فردی» دانشجو است. "
            "سه نوع تغییر رایج دارد:"
        )
        for title, desc in CHANGE_TYPES:
            self._body(title, bold=True)
            self._body(desc)
        self._body(
            "علاوه بر این، وقتی دانشجو به جلسهٔ پنجاهم یک بلوک ۵۰ ساعته "
            "می‌رسد و می‌خواهد آن را بپردازد، سامانه یک «قفل منطقی» دارد:"
        )
        self._warn_box(
            "دانشجو باید اول سوپروایزر و زمان بلوک بعدی را انتخاب کند "
            "و هزینهٔ جلسهٔ اول آن بلوک را بپردازد؛ "
            "بعد می‌تواند جلسهٔ پنجاهم بلوک فعلی را پرداخت کند."
        )
        self._body("چرا این کار لازم است؟", bold=True)
        self._bullet_list([
            "وقفهٔ طولانی بین دو بلوک ۵۰ ساعته پیش نیاید.",
            "دانشجو قبل از پایان یک دوره، برنامهٔ دورهٔ بعد را مشخص کند.",
            "سوابق گذشته (با کدام سوپروایزر چند ساعت) شفاف دیده شود.",
            "تغییر سوپروایزر یا ساعت بدون از دست رفتن سوابق ثبت شود.",
        ])
        self._body("چه کسی از این صفحه استفاده می‌کند؟", bold=True)
        self._body(
            "دانشجو — در پورتال خودش. شما برای آزمایش با حساب دانشجوی "
            "نمونه وارد می‌شوید یا کنار دانشجو می‌نشینید و چک‌لیست را پر می‌کنید."
        )

    def part_ui_on_screen(self) -> None:
        self._section_bar("بخش ۲ — در صفحه چه می‌بینید؟")
        self._body(
            "وقتی فرایند را در پورتال دانشجو باز می‌کنید، "
            "بلوک بنفش راهنما با این بخش‌ها دیده می‌شود:"
        )
        ui_parts = [
            (
                "شمارندهٔ پیشرفت",
                "«حضور در بلوک فعلی» (مثلاً ۴۸ از ۵۰) و «تا جلسه ۵۰» "
                "(مثلاً ۲ جلسه مانده)."
            ),
            (
                "سه کارت «انواع تغییر»",
                "تغییر سوپروایزر (آبی)، آغاز مجدد (سبز)، تغییر ساعت (نارنجی) — "
                "هر کدام توضیح کوتاه دارند."
            ),
            (
                "پیام الزام (نارنجی)",
                "در مرحلهٔ انتقال بلوک: «اول زمان و سوپرویژن بعدی را انتخاب کنید…»"
            ),
            (
                "جدول سوابق",
                "بلوک، سوپروایزر، ساعت، وضعیت — برای بلوک‌های ۵۰ ساعتهٔ گذشته."
            ),
            (
                "جدول وقت‌های آزاد",
                "سوپروایزر، روز، ساعت — برای انتخاب بلوک بعد."
            ),
            (
                "پیش‌نمایش انتخاب",
                "بعد از پر کردن فرم: سوپروایزر، روز و ساعت انتخاب‌شده."
            ),
            (
                "تاریخ آغاز",
                "با توضیح «قانون ۲۴ ساعت»."
            ),
            (
                "وضعیت قفل پرداخت جلسه ۵۰",
                "«قفل» یا «باز» — بعد از پرداخت جلسه اول بلوک بعد."
            ),
            (
                "فرم و دکمهٔ «ادامه و ثبت مرحله»",
                "پایین صفحه — برای ثبت هر مرحله."
            ),
        ]
        for title, desc in ui_parts:
            self._body(title, bold=True)
            self._body(desc)
        self._tip_box(
            "در داشبورد (کارت «مسیر فعلی») نسخهٔ فشردهٔ همین راهنما "
            "دیده می‌شود؛ برای آزمایش کامل به تب «فرایندها» بروید."
        )

    def part_flow_simple(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۳ — مسیر کار به زبان ساده")
        self._numbered_list([
            "دانشجو فرایند «مدیریت تغییرات سوپرویژن فردی» را باز می‌کند.",
            "راهنمای صفحه را می‌خواند (پیشرفت بلوک، انواع تغییر).",
            "اگر برای پرداخت جلسه ۵۰ است: «ادامه و ثبت مرحله» را می‌زند.",
            "سامانه می‌پرسد: آیا واقعاً به جلسه ۵۰ رسیده‌ای؟",
            "اگر نه → به پرداخت عادی یا تکمیل بلوک هدایت می‌شود.",
            "اگر بله → سوابق گذشته + لیست وقت‌های آزاد سوپروایزرها نشان داده می‌شود.",
            "دانشجو یک سوپروایزر و یک زمان (حداکثر ۱ جلسه در هفته) انتخاب می‌کند.",
            "تاریخ شروع با «قانون ۲۴ ساعت» محاسبه می‌شود.",
            "دانشجو جلسهٔ اول بلوک بعد را پرداخت می‌کند.",
            "قفل جلسه ۵۰ باز می‌شود.",
            "دانشجو جلسه ۵۰ام بلوک فعلی را پرداخت می‌کند.",
            "پیامک به دانشجو و سوپروایزر جدید — فرایند تمام.",
        ])
        self._tip_box(
            "نوار چهار مرحله‌ای «انتخاب → پرداخت اول → پرداخت ۵۰ → تکمیل» "
            "در بالای بلوک راهنما دیده می‌شود."
        )

    def part_before_start(self) -> None:
        self._section_bar("بخش ۴ — قبل از آزمایش چه چیزهایی باید آماده باشد؟")
        self._numbered_list([
            "آدرس سایت و حساب دانشجوی آزمایشی را از مسئول پروژه بگیرید.",
            "دانشجوی آزمایشی در مسیر سوپرویژن فردی فعال باشد.",
            "ترجیحاً تعداد حضور در بلوک فعلی به ۵۰ رسیده یا نزدیک ۵۰ باشد "
            "(مسیر «هنوز به ۵۰ نرسیده» را هم جداگانه امتحان کنید).",
            "حداقل یک سوپروایزر با «وقت آزاد» در سامانه ثبت شده باشد.",
            "فرایند «مدیریت تغییرات سوپرویژن فردی» برای همان دانشجو باز باشد.",
        ])
        self._body(
            "اگر حساب یا پروندهٔ آماده ندارید، از مسئول پروژه بخواهید "
            "«پروندهٔ نمونه برای فرایند ۱۸» را آماده کند — "
            "خودتان نیازی به کار پشت صحنه ندارید."
        )

    def part_where_ui(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۵ — صفحهٔ این فرایند کجاست؟")
        places = [
            (
                "ورود به سایت",
                "آدرس را از مسئول پروژه بگیرید. "
                "با نام کاربری و رمز دانشجوی آزمایشی وارد شوید."
            ),
            (
                "داشبورد — کارت «مسیر فعلی»",
                "اگر این فرایند فعال باشد، بلوک بنفش راهنما "
                "«مدیریت تغییرات سوپرویژن فردی (فرایند ۱۸)» "
                "و خلاصهٔ پیشرفت دیده می‌شود."
            ),
            (
                "تب «فرایندها»",
                "از لیست، «مدیریت تغییرات سوپرویژن فردی» را باز کنید. "
                "کارت کامل با جداول سوابق، وقت‌ها و فرم مرحله اینجاست."
            ),
            (
                "تب «درخواست‌های دیگر»",
                "اگر فرایند خودکار باز نشده، دکمهٔ شروع "
                "«مدیریت تغییرات سوپرویژن فردی» را ببینید (در صورت مجاز بودن)."
            ),
        ]
        for title, desc in places:
            self._body(title, bold=True)
            self._body(desc)

    def part_operator_scenario(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۶ — سناریوی کامل آزمایش (قدم‌به‌قدم برای اپراتور)")
        self._numbered_list([
            "با حساب دانشجوی آزمایشی وارد پورتال شوید.",
            "به تب «فرایندها» بروید و «مدیریت تغییرات سوپرویژن فردی» را باز کنید.",
            "بلوک بنفش راهنما را بخوانید: «حضور در بلوک فعلی»، «تا جلسه ۵۰»، سه کارت انواع تغییر.",
            "دکمهٔ «ادامه و ثبت مرحله» را بزنید.",
            "اگر به جلسه ۵۰ رسیده: پیام نارنجی الزام + جدول سوابق + جدول وقت‌ها را ببینید.",
            "در فرم پایین صفحه: سوپروایزر، روز و ساعت را انتخاب کنید.",
            "فرم را «ثبت» کنید؛ سپس دوباره «ادامه و ثبت مرحله».",
            "«تاریخ آغاز» و «انتخاب شما» را با انتخاب خود مقایسه کنید.",
            "بخش پرداخت — «جلسه اول دوره جدید» — را ببینید و پرداخت آزمایشی انجام دهید.",
            "پس از بازگشت از بانک، F5 بزنید؛ باید «قفل جلسه ۵۰ — باز» دیده شود.",
            "پرداخت دوم — «جلسه ۵۰ام دوره فعلی» — را انجام دهید.",
            "وضعیت «تکمیل» و پیام سبز پایانی را ببینید.",
            "در «تاریخچه پیامک» همان کارت، متن اطلاع‌رسانی را بررسی کنید.",
        ])
        self._ok_box(
            "اگر هر دو پرداخت بدون خطا انجام شد و پیام‌ها و جداول "
            "با این راهنما هم‌خوان بودند، صفحهٔ این فرایند برای "
            "استفادهٔ عادی قابل قبول است."
        )

    def part_stages_detail(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۷ — جزئیات هر مرحله")
        for st in STAGES:
            self._ensure_space(45)
            self._body(f"مرحله: {st['name']}", bold=True)
            self._body("دانشجو چه می‌بیند:", bold=True)
            self._body(st["student_sees"])
            self._body("دانشجو چه کار می‌کند:", bold=True)
            self._body(st["student_does"])
            self._body("اپراتور چه را بررسی می‌کند:", bold=True)
            self._bullet_list(st["operator_checks"])
            self.pdf.ln(2)

    def part_rules(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۸ — قوانین مهم")
        self._body("قانون ۲۴ ساعت:", bold=True)
        self._body(
            "اگر از لحظهٔ انتخاب تا اولین جلسه کمتر از ۲۴ ساعت "
            "مانده باشد، تاریخ شروع به هفتهٔ بعد موکول می‌شود. "
            "تاریخ نمایش‌داده‌شده در صفحه را با این قانون مقایسه کنید."
        )
        self._body("حداکثر ۱ جلسه در هفته:", bold=True)
        self._body(
            "دانشجو نباید بیش از یک جلسهٔ هفتگی برای سوپرویژن "
            "در این مرحله انتخاب کند. اگر سامانه اجازهٔ بیشتر داد، "
            "در چک‌لیست «خیر» بزنید."
        )
        self._body("انتخاب سوپروایزر متناسب با شماره بلوک:", bold=True)
        self._bullet_list([
            "بلوک اول و دوم: از بین اعضای هیئت علمی پیوسته ۱ تا ۵.",
            "بلوک سوم به بعد: از اعضای هیئت علمی ۶ به بالا.",
            "در آزمایش، اگر لیست وقت‌ها خالی است، با مسئول پروژه هماهنگ کنید.",
        ])
        self._body("قفل پرداخت جلسه ۵۰:", bold=True)
        self._body(
            "تا وقتی پرداخت جلسهٔ اول بلوک بعد انجام نشود، "
            "نباید بتوان جلسه ۵۰ام را پرداخت کرد. "
            "این را حتماً در آزمایش بررسی کنید."
        )

    def part_negative_scenarios(self) -> None:
        self._section_bar("بخش ۹ — سناریوهای اضافی (توصیه می‌شود)")
        scenarios = [
            (
                "هنوز به جلسه ۵۰ نرسیده",
                "با دانشجویی که کمتر از ۵۰ جلسه حضور دارد آزمایش کنید. "
                "باید پیام مناسب ببیند و به مسیر پرداخت عادی یا تکمیل بلوک هدایت شود."
            ),
            (
                "فرم ناقص",
                "بدون انتخاب سوپروایزر یا زمان، دکمهٔ ادامه را بزنید. "
                "باید هشدار یا عدم امکان ادامه باشد."
            ),
            (
                "پرداخت ناموفق",
                "در درگاه پرداخت را لغو کنید. "
                "وضعیت نباید «تکمیل» شود؛ باید بتوان دوباره پرداخت کرد."
            ),
            (
                "خواندن راهنمای انواع تغییر",
                "سه کارت آبی/سبز/نارنجی را بخوانید و مطمئن شوید "
                "برای دانشجو قابل فهم هستند (بدون اصطلاح فنی)."
            ),
        ]
        for title, desc in scenarios:
            self._body(title, bold=True)
            self._body(desc)

    def part_normal_vs_bug(self) -> None:
        self._section_bar("بخش ۱۰ — چه چیز «طبیعی» است و باگ نیست")
        self._bullet_list([
            "پرداخت در محیط آزمایشی واقعی نیست — فقط مسیر درگاه طی می‌شود.",
            "اگر جدول وقت‌های آزاد خالی است، شاید هنوز دادهٔ نمونه وارد نشده — از مسئول پروژه بپرسید.",
            "پیامک ممکن است به موبایل واقعی نرسد؛ فقط «تاریخچه پیامک» در همان کارت را ببینید.",
            "گاهی پس از پرداخت باید یک‌بار صفحه را تازه (F5) کنید.",
            "نام سوپروایزر در جدول ممکن است به‌صورت شناسه باشد — مهم این است که انتخاب ذخیره شود.",
        ])
        self._section_bar("بخش ۱۱ — اگر مشکلی دیدید چه بنویسید؟")
        self._numbered_list([
            "در کدام مرحله بودید (مثلاً «پرداخت جلسه اول بلوک بعد»).",
            "با چه حساب دانشجو وارد بودید.",
            "چه انتظار داشتید و چه دیدید.",
            "عکس از صفحه بگیرید.",
            "این PDF و چک‌لیست پایانی را پر کنید.",
        ])

    def part_checklist(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۱۲ — چک‌لیست نهایی اپراتور")
        checks = [
            "فرایند در داشبورد یا تب «فرایندها» پیدا می‌شود",
            "بلوک راهنما «مدیریت تغییرات سوپرویژن فردی (فرایند ۱۸)» دیده می‌شود",
            "«حضور در بلوک فعلی» و «تا جلسه ۵۰» نمایش داده می‌شود",
            "سه کارت «انواع تغییر» (سوپروایزر / آغاز مجدد / ساعت) دیده می‌شوند",
            "پیام الزام «اول بلوک بعد را انتخاب کنید» واضح است",
            "جدول سوابق بلوک‌های قبلی (در صورت داده) درست است",
            "جدول وقت‌های آزاد سوپروایزرها نمایش داده می‌شود",
            "فرم انتخاب سوپروایزر و زمان کار می‌کند",
            "تاریخ آغاز با قانون ۲۴ ساعت منطقی است",
            "پرداخت اول — جلسهٔ بلوک بعد — موفق است",
            "قفل جلسه ۵۰ پس از پرداخت اول «باز» می‌شود",
            "پرداخت دوم — جلسه ۵۰ام — موفق است",
            "وضعیت نهایی «تکمیل» است",
            "پیام/تاریخچهٔ اطلاع‌رسانی به دانشجو دیده می‌شود",
            "متن‌ها فارسی و قابل فهم هستند",
            "هیچ توقف یا خطای نامفهوم نبود",
        ]
        self._check_table(checks)
        self._blank_lines("مشکلات مهم (شماره ۱، ۲، ۳):", 3)
        self._blank_lines("پیشنهاد برای بهتر شدن:", 2)
        p = self.pdf
        p.ln(2)
        p.set_font("Vazir", "B", _BODY)
        p.cell(
            0,
            8,
            _fa("نتیجهٔ کلی:  ☐ قبول   ☐ قبول مشروط   ☐ رد"),
            align="R",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        p.cell(0, 8, _fa("امضا / تاریخ: ________________________"), align="R")

    def summary(self) -> None:
        self.pdf.add_page()
        self._section_bar("پایان — ارسال گزارش")
        self._body(
            "این PDF را پر کنید و همراه عکس‌های صفحه برای مسئول پروژه "
            "بفرستید. از همکاری شما برای اطمینان از "
            "درست بودن مسیر سوپرویژن دانشجویان سپاسگزاریم.",
            bold=True,
        )
        self._tip_box(
            "برای دمو سریع ۱۵ دقیقه‌ای: ورود دانشجو → تب فرایندها → "
            "خواندن راهنما → ادامه تا وقت‌ها → انتخاب → "
            "پرداخت اول → پرداخت ۵۰ → تکمیل."
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.pdf.output(str(path))


def main() -> int:
    builder = PdfBuilder()
    builder.cover()
    builder.part_what_is_process()
    builder.part_ui_on_screen()
    builder.part_flow_simple()
    builder.part_before_start()
    builder.part_where_ui()
    builder.part_operator_scenario()
    builder.part_stages_detail()
    builder.part_rules()
    builder.part_negative_scenarios()
    builder.part_normal_vs_bug()
    builder.part_checklist()
    builder.summary()
    builder.save(OUT_PDF)
    print(f"PDF written: {OUT_PDF}")
    print(f"Size: {OUT_PDF.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
