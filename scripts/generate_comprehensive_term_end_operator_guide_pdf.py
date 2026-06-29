#!/usr/bin/env python3
"""
راهنمای PDF اپراتور — فرایند ۳۶: پایان ترم‌های دوره جامع
(بدون جزئیات فنی؛ مناسب تست و پذیرش UI)

اجرا از ریشهٔ ریپو:
  python scripts/generate_comprehensive_term_end_operator_guide_pdf.py

خروجی:
  docs/راهنمای_تست_فرایند_۳۶_پایان_ترم_دوره_جامع.pdf
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
OUT_PDF = ROOT / "docs" / "راهنمای_تست_فرایند_۳۶_پایان_ترم_دوره_جامع.pdf"

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
                f"راهنمای تست فرایند ۳۶ — پایان ترم دوره جامع — {self._footer_ts} — ص {self.page_no()}"
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


ACCOUNTS = [
    ("دانشجوی دوره جامع (نمونه)", "student2", "demo123"),
    ("کارمند آموزشی / پذیرش", "staff1", "demo123"),
    ("معاون آموزش", "deputy_education1", "demo123"),
]

STAGES = [
    ("۱", "ثبت تمام نمرات ترم", "اساتید / سامانه", "پایان ترم — همهٔ نمرات وارد شود"),
    ("۲", "صدور کارنامه", "سامانه (خودکار)", "کارنامه ترمی و کارنامه کلی تولید می‌شود"),
    ("۳", "بررسی اتمام دروس", "سامانه (خودکار)", "آیا همهٔ دروس جامع پاس شده؟"),
    ("۴الف", "همهٔ دروس پاس شده", "سامانه", "فرایند تمام — بدون پیامک ثبت‌نام"),
    ("۴ب", "دروس باقی‌مانده", "سامانه", "پیامک مهلت ثبت‌نام ترم بعد ارسال می‌شود"),
    ("۵", "پایان فرایند", "سامانه", "در مسیر ۴ب: تکمیل پس از ارسال پیامک"),
]

SCENARIO_A = {
    "letter": "الف",
    "title": "دانشجو هنوز دروس باقی‌مانده دارد",
    "what": (
        "دانشجو دوره جامع را کامل نکرده؛ پس از پایان ترم باید پیامک "
        "مهلت ثبت‌نام ترم بعد ببیند و در پنل، دروس باقی‌مانده و مهلت "
        "ثبت‌نام نمایش داده شود."
    ),
    "steps": [
        "از مسئول پروژه بخواهید پروندهٔ نمونهٔ «پایان ترم دوره جامع» "
        "برای یک دانشجوی جامع با دروس باقی‌مانده آماده شود "
        "(یا پس از ثبت نمرات ترم، منتظر بمانید تا سامانه خودکار شروع کند).",
        "با حساب student2 (یا دانشجوی جامع نمونه) وارد پورتال دانشجو شوید.",
        "به تب «فرایندها» بروید.",
        "از فهرست، «پایان ترم‌های دوره جامع (فرایند ۳۶)» را باز کنید.",
        "کارت آبی «پایان ترم‌های دوره جامع» را ببینید.",
        "نوار مراحل سه‌گانه را بررسی کنید: صدور کارنامه، بررسی دروس، پایان.",
        "متن راهنمای آبی رنگ (توضیح مرحلهٔ فعلی) را بخوانید — "
        "باید فارسی و قابل فهم باشد.",
        "اگر کارنامه آماده است: بلوک سبز «کارنامه ترمی و کارنامه کلی» "
        "و دکمهٔ «مشاهده کارنامه‌ها در پروفایل» را ببینید.",
        "دکمهٔ «مشاهده کارنامه‌ها در پروفایل» را بزنید — "
        "باید به تب پروفایل بروید.",
        "به تب «فرایندها» برگردید و دوباره همان فرایند را باز کنید.",
        "اگر دروس باقی‌مانده دارید: بلوک زرد «دروس باقی‌مانده» "
        "با فهرست دروس را ببینید.",
        "اگر پیامک ارسال شده: بلوک زرد «مهلت ثبت‌نام ترم بعد» "
        "با تاریخ شمسی را ببینید.",
        "در پایان فرایند: بلوک سبز «فرایند پایان ترم تکمیل شد» را ببینید.",
    ],
    "expect": [
        "دانشجو هیچ دکمهٔ «ثبت» یا «ارسال» برای این فرایند ندارد.",
        "مراحل به‌صورت خودکار جلو می‌روند؛ فقط وضعیت و راهنما نمایش داده می‌شود.",
        "کارنامه در پروفایل قابل مشاهده است.",
        "دروس باقی‌مانده و مهلت ثبت‌نام واضح نمایش داده می‌شوند.",
        "پیامک در محیط آزمایشی ممکن است شبیه‌سازی شود — "
        "از مسئول پروژه بپرسید کجا دیده می‌شود.",
    ],
    "checks": [
        "کارت فرایند ۳۶ در تب فرایندها دیده می‌شود",
        "عنوان «پایان ترم‌های دوره جامع (فرایند ۳۶)» درست است",
        "نوار سه‌مرحله‌ای (استپر) نمایش داده می‌شود",
        "متن راهنمای مرحله فارسی و واضح است",
        "بلوک کارنامه آماده (سبز) دیده می‌شود",
        "دکمهٔ رفتن به پروفایل کار می‌کند",
        "فهرست دروس باقی‌مانده (در صورت وجود) نمایش داده می‌شود",
        "مهلت ثبت‌نام ترم بعد (در صورت ارسال پیامک) نمایش داده می‌شود",
        "بلوک پایان فرایند در انتها دیده می‌شود",
        "هیچ متن یا دکمهٔ گیج‌کننده‌ای نیست",
    ],
}

SCENARIO_B = {
    "letter": "ب",
    "title": "دانشجو تمام دروس دوره جامع را پاس کرده",
    "what": (
        "دانشجو همهٔ دروس جامع را گذرانده؛ فرایند باید با پیام "
        "تبریک تمام شود و پیامک ثبت‌نام ترم بعد ارسال نشود."
    ),
    "steps": [
        "از مسئول پروژه بخواهید پروندهٔ نمونه برای دانشجویی "
        "که تمام دروس جامع را پاس کرده آماده شود.",
        "با حساب آن دانشجو وارد پورتال شوید.",
        "تب «فرایندها» — «پایان ترم‌های دوره جامع (فرایند ۳۶)» را باز کنید.",
        "در نوار مراحل، مرحلهٔ «پایان فرایند» باید فعال یا تکمیل‌شده باشد.",
        "متن راهنما باید تبریک و «تمام دروس پاس شده» را بگوید.",
        "بلوک سبز «اتمام دروس دوره جامع» را ببینید.",
        "بررسی کنید بلوک «مهلت ثبت‌نام ترم بعد» نمایش داده نشود "
        "(چون پیامک ثبت‌نام ارسال نمی‌شود).",
        "کارنامه‌ها را از پروفایل مشاهده کنید.",
    ],
    "expect": [
        "پیام تبریک برای اتمام دروس جامع نمایش داده می‌شود.",
        "مهلت ثبت‌نام ترم بعد نشان داده نمی‌شود.",
        "فرایند در وضعیت «تمام دروس جامع پاس شده» یا معادل آن تمام می‌شود.",
        "کارنامه ترمی و کلی در پروفایل در دسترس است.",
    ],
    "checks": [
        "بلوک تبریک «اتمام دروس دوره جامع» دیده می‌شود",
        "بلوک مهلت ثبت‌نام نمایش داده نمی‌شود",
        "وضعیت نهایی فرایند مشخص و قابل فهم است",
        "کارنامه در پروفایل قابل دسترس است",
        "متن راهنما با وضعیت واقعی هم‌خوان است",
    ],
}

STATE_CHECKS = [
    (
        "تمام نمرات ترم وارد شده",
        "سامانه در حال تولید کارنامه است؛ متن «این مرحله خودکار است» "
        "و پیشنهاد تازه‌کردن صفحه."
    ),
    (
        "کارنامه‌های ترمی و کلی تولید شده",
        "بلوک سبز کارنامه آماده؛ دکمهٔ رفتن به پروفایل؛ "
        "نمایش معدل ترم/کل در صورت وجود."
    ),
    (
        "بررسی وضعیت اتمام دروس جامع",
        "متن «سامانه در حال بررسی»؛ بدون نیاز به اقدام دانشجو."
    ),
    (
        "تمام دروس جامع پاس شده",
        "بلوک تبریک سبز؛ بدون مهلت ثبت‌نام."
    ),
    (
        "اطلاعیه ثبت‌نام ترم بعدی ارسال شد",
        "بلوک مهلت ثبت‌نام؛ دروس باقی‌مانده (در صورت وجود)."
    ),
    (
        "فرایند تکمیل شد",
        "بلوک پایان فرایند؛ کارنامه در پروفایل."
    ),
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
        p.set_font("Vazir", "B", 12)
        p.cell(
            0,
            10,
            _fa("فرایند ۳۶ — پایان ترم‌های دوره جامع"),
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
                "این کتابچه به شما کمک می‌کند صفحهٔ «پایان ترم دوره جامع» "
                "در پورتال دانشجو را امتحان کنید و مطمئن شوید پس از ثبت "
                "نمرات ترم، کارنامه‌ها، وضعیت دروس و اطلاع‌رسانی ثبت‌نام "
                "درست نمایش داده می‌شود. نیازی به دانش فنی ندارید."
            ),
            align="R",
        )
        p.ln(4)
        for label, blank in [
            ("نام اپراتور / آزمایش‌کننده", "________________________"),
            ("تاریخ آزمایش", "________________________"),
            ("آدرس سایت (از مسئول پروژه)", "________________________"),
        ]:
            p.cell(0, 8, _fa(f"{label}: {blank}"), align="R", new_x="LMARGIN", new_y="NEXT")
        p.ln(2)
        self._warn_box(
            "این فرایند کاملاً خودکار است — دانشجو دکمهٔ «شروع» یا «ثبت» "
            "ندارد. شما فقط وضعیت و راهنما را در پنل می‌بینید و با این "
            "راهنما مقایسه می‌کنید."
        )

    def part_what_is_process(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۱ — این فرایند چیست؟")
        self._body(
            "در پایان هر ترم دوره جامع، وقتی اساتید تمام نمرات را ثبت "
            "کردند، سامانه خودکار این کارها را انجام می‌دهد:"
        )
        self._bullet_list([
            "کارنامه ترمی آن ترم را تولید می‌کند.",
            "کارنامه کلی (شامل بخش آکادمیک، بالینی و نظارتی) را تولید می‌کند.",
            "بررسی می‌کند آیا دانشجو تمام دروس دوره جامع را پاس کرده یا نه.",
            "اگر درس باقی مانده: پیامک مهلت ثبت‌نام ترم بعد را می‌فرستد.",
            "اگر همهٔ دروس پاس شده: فرایند تمام می‌شود — بدون پیامک ثبت‌نام.",
        ])
        self._body("چه کسی این فرایند را «انجام» می‌دهد؟", bold=True)
        self._body(
            "سامانه — بدون دخالت دانشجو یا کارمند. دانشجو فقط نتیجه را "
            "در کارت «پایان ترم‌های دوره جامع» در تب فرایندها می‌بیند. "
            "اپراتور برای آزمایش: با حساب دانشجوی جامع وارد می‌شود و "
            "صفحه را با این راهنما مقایسه می‌کند."
        )
        self._section_bar("تفاوت با «پایان ترم دوره آشنایی» (فرایند ۳۲)")
        self._body(
            "فرایند ۳۲ مربوط به دوره آشنایی است و مراحل اضافه‌ای دارد "
            "(مثل بررسی شرط درمان و پیگیری افت تحصیلی). فرایند ۳۶ "
            "فقط برای دوره جامع است و ساده‌تر است — بدون فرم پر کردن "
            "توسط دانشجو."
        )

    def part_before_start(self) -> None:
        self._section_bar("بخش ۲ — قبل از آزمایش چه چیزهایی باید آماده باشد؟")
        self._numbered_list([
            "دانشجو در دوره جامع ثبت‌نام کرده باشد.",
            "ترم جاری به پایان رسیده و اساتید نمرات را ثبت کرده باشند "
            "(یا مسئول پروژه پروندهٔ نمونه آماده کرده باشد).",
            "فرایند ۳۶ در فهرست فرایندهای دانشجو دیده شود.",
            "برای آزمایش مسیر «دروس باقی‌مانده»: دانشجویی که هنوز "
            "همهٔ دروس جامع را نگذرانده.",
            "برای آزمایش مسیر «اتمام دروس»: دانشجویی که تمام "
            "دروس جامع را پاس کرده.",
        ])
        self._tip_box(
            "اگر فرایند را در لیست نمی‌بینید، از مسئول پروژه بخواهید "
            "پروندهٔ نمونه را برای دانشجوی جامع (مثلاً student2) فعال کند."
        )
        self._section_bar("حساب‌های پیشنهادی برای آزمایش")
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
        self._section_bar("بخش ۳ — صفحهٔ فرایند کجاست؟")
        self._numbered_list([
            "با حساب دانشجوی دوره جامع وارد شوید.",
            "از منوی بالا یا تب‌ها، «فرایندها» را باز کنید.",
            "در فهرست فرایندهای فعال، «پایان ترم‌های دوره جامع» "
            "یا «فرایند ۳۶» را پیدا کنید و روی آن بزنید.",
            "کارت بزرگ با عنوان «پایان ترم‌های دوره جامع (فرایند ۳۶)» "
            "باز می‌شود.",
        ])
        self._body("داخل کارت چه می‌بینید؟", bold=True)
        self._bullet_list([
            "نوار مراحل سه‌گانه (صدور کارنامه، سپس بررسی دروس، سپس پایان).",
            "متن راهنمای آبی برای مرحلهٔ فعلی.",
            "اعداد ترم، معدل ترم و معدل کل (در صورت وجود).",
            "بلوک سبز «کارنامه آماده» با دکمهٔ رفتن به پروفایل.",
            "بلوک سبز «اتمام دروس دوره جامع» (اگر همه پاس شده).",
            "بلوک زرد «دروس باقی‌مانده» (اگر درس مانده).",
            "بلوک زرد «مهلت ثبت‌نام ترم بعد» (اگر پیامک ارسال شده).",
            "بلوک سبز «فرایند تکمیل شد» در پایان.",
        ])
        self._section_bar("مراحل فرایند — نمای کلی")
        p = self.pdf
        with p.table(
            col_widths=(12, 38, 28, 102),
            width=p.epw,
            text_align=Align.R,
            line_height=5.5,
            borders_layout=TableBordersLayout.ALL,
            cell_fill_color=_COLOR_STRIPE,
            cell_fill_mode=TableCellFillMode.ROWS,
            padding=1.5,
        ) as table:
            hr = table.row()
            for h in [_fa("ردیف"), _fa("مرحله"), _fa("مسئول"), _fa("کار شما در آزمایش")]:
                hr.cell(h, align=Align.C, style=_heading_style())
            for num, stage, who, task in STAGES:
                row = table.row()
                row.cell(num, align=Align.C)
                row.cell(_fa(stage))
                row.cell(_fa(who))
                row.cell(_fa(task))
        p.ln(4)

    def part_states(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۴ — در هر وضعیت چه باید ببینید؟")
        self._body(
            "اگر مسئول پروژه پرونده را در مراحل مختلف قرار دهد، "
            "این جدول را برای مقایسه استفاده کنید:"
        )
        p = self.pdf
        with p.table(
            col_widths=(52, 128),
            width=p.epw,
            text_align=Align.R,
            line_height=5.5,
            borders_layout=TableBordersLayout.ALL,
            cell_fill_color=_COLOR_STRIPE,
            cell_fill_mode=TableCellFillMode.ROWS,
            padding=1.5,
        ) as table:
            hr = table.row()
            for h in [_fa("وضعیت"), _fa("چه باید در صفحه ببینید")]:
                hr.cell(h, align=Align.C, style=_heading_style())
            for state, desc in STATE_CHECKS:
                row = table.row()
                row.cell(_fa(state))
                row.cell(_fa(desc))
        p.ln(4)

    def scenario(self, sc: dict) -> None:
        self.pdf.add_page()
        self._section_bar(f"سناریوی {sc['letter']} — {sc['title']}")
        self._body("هدف این سناریو", bold=True)
        self._body(sc["what"])
        self._body("قدم‌به‌قدم:", bold=True)
        self._numbered_list(sc["steps"])
        self._body("باید چه ببینید؟", bold=True)
        self._bullet_list(sc["expect"])
        self._body("چک‌لیست — بعد از انجام علامت بزنید:", bold=True)
        self._check_table(sc["checks"])
        self._blank_lines("مشکل یا باگ (چه انتظار داشتید / چه شد):", 2)

    def part_normal_vs_bug(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۷ — چه چیز «طبیعی» است و باگ نیست")
        self._bullet_list([
            "دانشجو دکمهٔ «شروع» یا «ثبت فرم» برای این فرایند ندارد.",
            "مراحل خودکار هستند — ممکن است چند دقیقه طول بکشد؛ "
            "صفحه را یک‌بار تازه کنید.",
            "اگر هنوز نمرات کامل نشده، فرایند شروع نشده — طبیعی است.",
            "پیامک در محیط آزمایشی ممکن است فقط شبیه‌سازی شود.",
            "کارنامه در تب «پروفایل» است — دکمهٔ «مشاهده کارنامه‌ها» "
            "شما را به آنجا می‌برد.",
            "اگر همهٔ دروس پاس شده، مهلت ثبت‌نام نشان داده نمی‌شود — "
            "این درست است.",
            "این فرایند با «پایان ترم دوره آشنایی» (فرایند ۳۲) "
            "متفاوت است — عنوان را دقیق بخوانید.",
        ])
        self._section_bar("بخش ۸ — اگر مشکلی دیدید چه بنویسید؟")
        self._numbered_list([
            "با چه حساب دانشجویی وارد شدید.",
            "فرایند در کدام وضعیت بود (متن badge بالای کارت).",
            "چه انتظار داشتید ببینید و چه دیدید.",
            "آیا دکمهٔ «مشاهده کارنامه‌ها در پروفایل» کار کرد.",
            "عکس از کل کارت فرایند بگیرید.",
        ])

    def part_checklist(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۹ — چک‌لیست نهایی اپراتور")
        checks = [
            "کارت «پایان ترم‌های دوره جامع (فرایند ۳۶)» در تب فرایندها دیده می‌شود",
            "نوار سه‌مرحله‌ای (استپر) درست و قابل فهم است",
            "متن راهنمای مرحله فارسی و بدون اصطلاح گیج‌کننده است",
            "کارنامه آماده — بلوک سبز و دکمهٔ پروفایل کار می‌کند",
            "معدل ترم/کل (در صورت نمایش) قابل خواندن است",
            "سناریوی دروس باقی‌مانده: فهرست دروس و مهلت ثبت‌نام دیده می‌شود",
            "سناریوی اتمام دروس: بلوک تبریک بدون مهلت ثبت‌نام",
            "بلوک «فرایند تکمیل شد» در پایان مسیر درست نمایش داده می‌شود",
            "با فرایند ۳۲ (پایان ترم آشنایی) اشتباه گرفته نشد",
            "هیچ صفحهٔ سفید یا پیام خطای نامفهوم نبود",
        ]
        self._check_table(checks)
        self._blank_lines("مشکلات مهم (شماره ۱، ۲، ۳):", 3)
        self._blank_lines("پیشنهاد برای بهتر شدن:", 2)
        self._body("امتیاز کلی (۱ = ضعیف — ۵ = عالی):  [ ] ۱  [ ] ۲  [ ] ۳  [ ] ۴  [ ] ۵")
        self._body("نتیجه:  [ ] تأیید   [ ] تأیید مشروط   [ ] رد")

    def summary(self) -> None:
        self.pdf.add_page()
        self._section_bar("پایان — ارسال گزارش")
        self._body(
            "این PDF را پر کنید و همراه عکس‌های صفحه برای مدیر پروژه "
            "یا مسئول سامانه بفرستید. از همکاری شما برای بهتر شدن "
            "تجربهٔ دانشجویان سپاسگزاریم.",
            bold=True,
        )
        self._ok_box(
            "اگر هر دو سناریو (دروس باقی‌مانده و اتمام دروس) درست "
            "نمایش داده شدند، UI فرایند ۳۶ برای استفادهٔ عادی "
            "قابل قبول است."
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
    builder.part_states()
    builder.scenario(SCENARIO_A)
    builder.scenario(SCENARIO_B)
    builder.part_normal_vs_bug()
    builder.part_checklist()
    builder.summary()
    builder.save(OUT_PDF)
    print(f"PDF written: {OUT_PDF}")
    print(f"Size: {OUT_PDF.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
