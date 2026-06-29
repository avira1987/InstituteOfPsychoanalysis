#!/usr/bin/env python3
"""
راهنمای PDF اپراتور — فرایند «تکمیل و خاتمه درمان آموزشی» (شماره ۸ SOP).

اجرا از ریشهٔ ریپو:
  python scripts/generate_therapy_completion_guide_pdf.py

خروجی:
  docs/راهنمای_تست_فرایند_تکمیل_و_خاتمه_درمان_آموزشی.pdf
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
OUT_PDF = ROOT / "docs" / "راهنمای_تست_فرایند_تکمیل_و_خاتمه_درمان_آموزشی.pdf"

_MARGIN = 14
_BODY = 9.5
_SECTION = 11.5
_TITLE = 15
_SMALL = 8
_TINY = 7.5

_COLOR_SECTION_BG = (243, 232, 255)
_COLOR_SECTION_TEXT = (88, 28, 135)
_COLOR_BORDER = (209, 213, 219)
_COLOR_STRIPE = (249, 250, 251)
_COLOR_TIP_BG = (255, 251, 235)
_COLOR_WARN_BG = (254, 242, 242)
_COLOR_OK_BG = (236, 253, 245)


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
                f"راهنمای تست — تکمیل و خاتمه درمان آموزشی — {self._footer_ts} — صفحه {self.page_no()}"
            ),
            align="C",
        )


def _heading_style() -> FontFace:
    return FontFace(
        family="Vazir",
        emphasis="BOLD",
        size_pt=_SMALL,
        color=(88, 28, 135),
        fill_color=(237, 233, 254),
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
        p.multi_cell(0, 5.8, _fa(text), align="R", fill=True)
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

    def _check_table(self, rows: list[tuple[str, str]]) -> None:
        self._ensure_space(12 + len(rows) * 6)
        p = self.pdf
        hs = _heading_style()
        table_rows = [[_fa("کار"), _fa("انجام شد؟"), _fa("یادداشت")]]
        for work, _ in rows:
            table_rows.append([_fa(work), "[ ] بله  [ ] خیر", ""])
        with p.table(
            col_widths=(78, 28, 74),
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
            for i, row in enumerate(table_rows):
                r = table.row()
                for j, cell in enumerate(row):
                    style = hs if i == 0 and j == 0 else None
                    r.cell(cell, align=Align.R if j != 1 else Align.C, style=style)
        p.ln(2)

    def cover(self) -> None:
        p = self.pdf
        p.add_page()
        p.set_font("Vazir", "B", _TITLE)
        p.ln(8)
        p.cell(
            0,
            12,
            _fa("راهنمای آزمایش و استفاده"),
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        p.set_font("Vazir", "B", 13)
        p.cell(
            0,
            10,
            _fa("فرایند «تکمیل و خاتمه درمان آموزشی»"),
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        p.set_font("Vazir", "", 10)
        p.cell(
            0,
            8,
            _fa("(شماره ۸ در فهرست فرایندهای انستیتو)"),
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
                "این کتابچه برای اپراتور تست، کارشناس پذیرش و مسئول بررسی کیفیت "
                "نوشته شده است. هدف آن است بدون نیاز به دانش فنی، بتوانید "
                "رابط کاربری این فرایند را امتحان کنید و مطمئن شوید درست کار می‌کند."
            ),
            align="R",
        )
        p.ln(5)
        for label, blank in [
            ("نام اپراتور تست", "________________________"),
            ("تاریخ آزمایش", "________________________"),
            ("آدرس سایت (از مسئول پروژه)", "________________________"),
        ]:
            p.cell(0, 8, _fa(f"{label}: {blank}"), align="R", new_x="LMARGIN", new_y="NEXT")
        p.ln(3)
        self._warn_box(
            "قبل از شروع، سامانه باید روشن و در دسترس باشد. "
            "اگر صفحه باز نمی‌شود، با مسئول فنی تماس بگیرید."
        )

    def part_intro(self) -> None:
        self.pdf.add_page()
        self._section_bar("۱ — این فرایند چیست؟")
        self._body(
            "وقتی دانشجو به پایان مسیر درمان آموزشی نزدیک می‌شود، باید یک "
            "«ایست بازرسی نهایی» طی کند. سامانه سه نوع ساعت را با حدنصاب‌های "
            "مشخص مقایسه می‌کند:"
        )
        self._bullet_list([
            "ساعات درمان آموزشی (پیش‌فرض: ۲۵۰ ساعت)",
            "ساعات تجربه بالینی (پیش‌فرض: ۷۵۰ ساعت)",
            "ساعات سوپرویژن (پیش‌فرض: ۱۵۰ ساعت)",
        ])
        self._body(
            "اگر هر سه شرط کامل باشد، درمان آموزشی به‌صورت رسمی «تکمیل و "
            "خاتمه‌یافته» ثبت می‌شود و جلسات آینده لغو می‌گردد. "
            "اگر حتی یکی کم باشد، نتیجه «شرایط احراز نشده» ثبت می‌شود و "
            "دانشجو پس از تکمیل ساعات می‌تواند دوباره همین درخواست را بزند."
        )
        self._section_bar("۲ — چه کسی با این صفحه کار می‌کند؟")
        self._bullet_list([
            "دانشجو: فرایند را شروع می‌کند، ساعات را می‌بیند و دکمهٔ ادامه را می‌زند.",
            "اپراتور / پذیرش: پرونده را آماده می‌کند، نتیجه را در ردیابی دانشجویان بررسی می‌کند.",
            "کمیته نظارت (در صورت نیاز): حدنصاب‌های خاص برای یک دانشجو را از قبل تنظیم کرده است.",
        ])
        self._tip_box(
            "این فرایند فرم پر کردن ندارد؛ فقط یک جعبهٔ رنگی با نوار پیشرفت "
            "و یک دکمهٔ «ادامه و ثبت مرحله» دارد."
        )

    def part_prereq(self) -> None:
        self.pdf.add_page()
        self._section_bar("۳ — قبل از تست چه باید آماده باشد؟")
        self._body("اپراتور این موارد را یک‌بار بررسی می‌کند:", bold=True)
        self._check_table([
            ("سامانه باز می‌شود و صفحهٔ ورود دیده می‌شود", ""),
            ("حداقل یک حساب دانشجوی آزمایشی دارید (مثلاً student1 با رمز demo123)", ""),
            ("برای همان دانشجو «آغاز درمان آموزشی» قبلاً انجام شده باشد", ""),
            ("در پروندهٔ دانشجو وضعیت «درمان شروع شده» دیده می‌شود", ""),
            ("برای آزمایش مسیر موفق: ساعات کافی در پرونده ثبت شده باشد", ""),
            ("برای آزمایش مسیر ناموفق: حداقل یکی از سه ساعت کمتر از حدنصاب باشد", ""),
        ])
        self._section_bar("۴ — ورود به سامانه")
        self._numbered_list([
            "مرورگر (Chrome یا Edge) را باز کنید.",
            "آدرس ورود را از مسئول پروژه بگیرید (معمولاً .../login).",
            "روی «ورود با رمز عبور» بزنید.",
            "سؤال ریاضی ساده را جواب دهید.",
            "نام کاربری و رمز را وارد کنید و «ورود» بزنید.",
        ])
        self._body("حساب‌های آزمایشی رایج:", bold=True)
        p = self.pdf
        with p.table(
            col_widths=(55, 55, 25),
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
            for role, user, pw in [
                ("دانشجو", "student1", "demo123"),
                ("کارمند / پذیرش", "demo_admissions", "demo123"),
                ("مدیر (ردیابی)", "admin", "admin123"),
            ]:
                row = table.row()
                row.cell(_fa(role))
                row.cell(user, align=Align.C)
                row.cell(pw, align=Align.C)
        p.ln(3)

    def part_ui_description(self) -> None:
        self.pdf.add_page()
        self._section_bar("۵ — صفحهٔ دانشجو چه شکلی است؟")
        self._body(
            "پس از ورود با حساب دانشجو، به «پورتال دانشجو» می‌روید. "
            "فرایند را از یکی از این دو جا پیدا می‌کنید:"
        )
        self._bullet_list([
            "تب «داشبورد» — اگر این فرایند مسیر فعال شما باشد، کارت «مسیر فعلی» را می‌بینید.",
            "تب «درخواست‌های دیگر» — دکمهٔ «آغاز فرایند» کنار عنوان «تکمیل و خاتمه درمان آموزشی».",
        ])
        self._body("بعد از شروع یا باز کردن فرایند، باید این‌ها را ببینید:", bold=True)
        self._numbered_list([
            "عنوان: «تکمیل و خاتمه درمان آموزشی»",
            "راهنمای مرحله: توضیح کوتاه دربارهٔ ساعات و دکمهٔ ادامه",
            "جعبهٔ بنفش «ایست بازرسی ساعات (خاتمه درمان)» شامل:",
            "  — برچسب بالا: «همهٔ شرایط احراز شد» (سبز) یا «شرایط هنوز کامل نیست» (زرد)",
            "  — سه ردیف با نوار پیشرفت: درمان آموزشی، تجربه بالینی، سوپرویژن",
            "  — در هر ردیف: عدد فعلی / حدنصاب و «احراز شد» یا «X ساعت مانده»",
            "  — پیام راهنما در پایین جعبه (سبز اگر آمادهٔ خاتمه، زرد اگر نه)",
            "دکمهٔ «ادامه و ثبت مرحله» در بخش «قدم بعد در مسیر»",
        ])
        self._warn_box(
            "اگر دکمهٔ شروع قفل است و می‌نویسد «پس از آغاز درمان آموزشی»، "
            "ابتدا باید فرایند آغاز درمان برای آن دانشجو تکمیل شود."
        )

    def part_operator_prep(self) -> None:
        self.pdf.add_page()
        self._section_bar("۶ — کارهای اپراتور قبل از آزمایش دانشجو")
        self._body(
            "این بخش مخصوص شماست (کارمند پذیرش یا اپراتور تست). "
            "قبل از اینکه دانشجو وارد شود، این مراحل را انجام دهید:"
        )
        self._numbered_list([
            "با حساب مدیر یا کارمند وارد شوید.",
            "از منو به «ردیابی دانشجویان» بروید.",
            "دانشجوی مورد آزمایش را پیدا و باز کنید.",
            "بررسی کنید «درمان آموزشی» برای او شروع شده باشد.",
            "اگر می‌خواهید مسیر موفق را آزمایش کنید: مطمئن شوید ساعات "
            "درمان، بالینی و سوپرویژن در پرونده به حد کافی رسیده‌اند "
            "(از مسئول فنی یا دادهٔ آزمایشی آماده کمک بگیرید).",
            "اگر می‌خواهید مسیر «شرایط احراز نشده» را آزمایش کنید: "
            "دانشجویی انتخاب کنید که حداقل یکی از سه ساعت کمتر از حدنصاب باشد.",
            "یادداشت کنید نام دانشجو و وضعیت ساعات قبل از تست.",
        ])
        self._tip_box(
            "حدنصاب‌ها معمولاً ۲۵۰ / ۷۵۰ / ۱۵۰ است؛ "
            "برای بعضی دانشجویان کمیته نظارت عدد دیگری تعیین کرده باشد — "
            "در جعبهٔ بنفش همان اعداد نمایش داده می‌شود."
        )

    def part_scenario_success(self) -> None:
        self.pdf.add_page()
        self._section_bar("۷ — سناریوی ۱: همهٔ شرایط کامل است (مسیر موفق)")
        self._body("نقش: دانشجو (حساب آزمایشی)", bold=True)
        self._numbered_list([
            "با حساب دانشجو وارد پورتال شوید.",
            "به «درخواست‌های دیگر» بروید.",
            "روی «آغاز فرایند» کنار «تکمیل و خاتمه درمان آموزشی» بزنید "
            "(اگر قبلاً شروع نشده).",
            "جعبهٔ بنفش را ببینید: برچسب بالا باید «همهٔ شرایط احراز شد» باشد.",
            "هر سه نوار پیشرفت سبز و کنار هر ردیف «احراز شد» نوشته شده باشد.",
            "پیام پایین جعبه بگوید با زدن دکمه، خاتمهٔ رسمی ثبت می‌شود.",
            "به پایین صفحه بروید و «ادامه و ثبت مرحله» را بزنید.",
            "صفحه را تازه کنید (F5).",
        ])
        self._ok_box("نشانهٔ موفقیت برای اپراتور:")
        self._bullet_list([
            "وضعیت فرایند: «درمان تکمیل و خاتمه یافت»",
            "پیام «گام بعد پیشنهادی» با متن تأیید خاتمه درمان",
            "در ردیابی دانشجویان: وضعیت درمان «خاتمه‌یافته» یا مشابه",
            "پیامک یا اعلان درون‌برنامه‌ای برای دانشجو (در محیط آزمایشی ممکن است فقط در تاریخچهٔ پیامک دیده شود)",
        ])
        self._section_bar("چک‌لیست مسیر موفق")
        self._check_table([
            ("جعبهٔ ساعات با برچسب سبز «همهٔ شرایط احراز شد»", ""),
            ("سه نوار پیشرفت و اعداد درست نمایش داده شد", ""),
            ("دکمهٔ ادامه بدون خطا کار کرد", ""),
            ("وضعیت نهایی «درمان تکمیل و خاتمه یافت»", ""),
            ("پیام گام بعد نمایش داده شد", ""),
        ])

    def part_scenario_fail(self) -> None:
        self.pdf.add_page()
        self._section_bar("۸ — سناریوی ۲: شرایط کامل نیست")
        self._body("نقش: دانشجو با ساعات ناکافی", bold=True)
        self._numbered_list([
            "با حساب دانشجویی که حداقل یک ساعت کم دارد وارد شوید.",
            "فرایند «تکمیل و خاتمه درمان آموزشی» را شروع کنید.",
            "جعبهٔ بنفش: برچسب «شرایط هنوز کامل نیست» (زرد).",
            "در ردیف‌های ناکافی «X ساعت مانده» دیده شود.",
            "پیام پایین جعبه هشدار دهد که با ادامه، نتیجه «احراز نشده» ثبت می‌شود.",
            "با آگاهی «ادامه و ثبت مرحله» را بزنید.",
            "صفحه را تازه کنید.",
        ])
        self._ok_box("نشانهٔ موفقیت برای اپراتور:")
        self._bullet_list([
            "وضعیت: «شرایط احراز نشده»",
            "پیام راهنما: پس از تکمیل ساعات دوباره همین فرایند را اجرا کنید",
            "درمان هنوز «خاتمه‌یافته» نشده باشد",
        ])
        self._section_bar("چک‌لیست مسیر ناکافی")
        self._check_table([
            ("برچسب زرد «شرایط هنوز کامل نیست»", ""),
            ("«ساعت مانده» برای حداقل یک ردیف", ""),
            ("هشدار قبل از زدن دکمه خوانا بود", ""),
            ("وضعیت نهایی «شرایط احراز نشده»", ""),
            ("درمان هنوز خاتمه نیافته", ""),
        ])

    def part_operator_verify(self) -> None:
        self.pdf.add_page()
        self._section_bar("۹ — بررسی اپراتور پس از تست")
        self._body(
            "بعد از هر دو سناریو، با حساب کارمند یا مدیر این موارد را "
            "در «ردیابی دانشجویان» یا صندوق کارها کنترل کنید:"
        )
        self._check_table([
            ("نمونهٔ فرایند در لیست فرایندهای دانشجو ثبت شده", ""),
            ("وضعیت نهایی با انتظار سناریو یکی است", ""),
            ("تاریخ و زمان ثبت منطقی است", ""),
            ("در مسیر موفق: جلسات آینده درمان لغو شده (در صورت وجود در تقویم)", ""),
            ("در مسیر موفق: وضعیت درمان در پرونده به‌روز شده", ""),
            ("تاریخچهٔ پیامک یا اعلان (در صورت فعال بودن) ثبت شده", ""),
        ])
        self._section_bar("۱۰ — موارد اضافی برای بررسی")
        self._check_table([
            ("اگر فرایند فعال دارد، دکمهٔ شروع دوباره قفل است", ""),
            ("متن‌های فارسی بدون غلط املایی جدی و قابل فهم است", ""),
            ("روی موبایل یا تبلت هم جعبهٔ ساعات خوانا است (اختیاری)", ""),
            ("پس از خروج و ورود مجدد، وضعیت همان است", ""),
        ])

    def part_quick_demo(self) -> None:
        self.pdf.add_page()
        self._section_bar("۱۱ — مسیر سریع دمو (حدود ۱۰ دقیقه)")
        self._numbered_list([
            "اپراتور: ردیابی — سپس انتخاب دانشجو با درمان شروع‌شده و ساعات کافی.",
            "دانشجو: ورود — سپس درخواست‌های دیگر — سپس شروع «تکمیل و خاتمه درمان».",
            "بررسی جعبهٔ بنفش و نوارها.",
            "زدن «ادامه و ثبت مرحله».",
            "تأیید وضعیت «درمان تکمیل و خاتمه یافت».",
            "اپراتور: ردیابی — سپس تأیید تغییر وضعیت پرونده.",
        ])
        self._section_bar("۱۲ — اگر مشکلی دیدید چه بنویسید؟")
        self._numbered_list([
            "با چه حسابی وارد بودید.",
            "در کدام مرحله بودید (شروع، مشاهده ساعات، زدن دکمه، بعد از تازه‌سازی).",
            "چه انتظار داشتید و چه دیدید.",
            "عکس از صفحه بگیرید.",
        ])
        self._tip_box(
            "اگر جعبهٔ بنفش اصلاً نیامد، احتمالاً ساعات در پرونده "
            "هنوز بارگذاری نشده — صفحه را تازه کنید یا با مسئول فنی تماس بگیرید."
        )

    def part_final_form(self) -> None:
        self.pdf.add_page()
        self._section_bar("۱۳ — فرم نتیجهٔ نهایی تست")
        self._blank_lines("نام اپراتور:", 1)
        self._blank_lines("تاریخ:", 1)
        self._blank_lines("نام دانشجوی آزمایشی:", 1)
        p = self.pdf
        p.set_font("Vazir", "B", _BODY)
        p.cell(0, 7, _fa("محیط آزمایش:"), new_x="LMARGIN", new_y="NEXT")
        p.set_font("Vazir", "", _BODY)
        p.cell(0, 7, _fa("[ ] روی کامپیوتر محلی   [ ] سرور آزمایشی   [ ] سرور واقعی"), new_x="LMARGIN", new_y="NEXT")
        p.ln(3)
        self._body("نتیجهٔ هر بخش:", bold=True)
        rows = [
            "آماده‌سازی و ورود",
            "نمایش جعبهٔ ساعات و نوار پیشرفت",
            "سناریوی موفق (خاتمه درمان)",
            "سناریوی ناکافی (احراز نشده)",
            "بررسی در ردیابی دانشجویان",
        ]
        with p.table(
            col_widths=(70, 22, 22, 22, 44),
            width=p.epw,
            text_align=Align.C,
            line_height=5.5,
            borders_layout=TableBordersLayout.ALL,
            cell_fill_color=_COLOR_STRIPE,
            cell_fill_mode=TableCellFillMode.ROWS,
            padding=1.5,
        ) as table:
            hr = table.row()
            for h in [_fa("بخش"), _fa("قبول"), _fa("ناقص"), _fa("رد"), _fa("توضیح")]:
                hr.cell(h, style=_heading_style())
            for name in rows:
                r = table.row()
                r.cell(_fa(name), align=Align.R)
                for _ in range(3):
                    r.cell("")
                r.cell("")
        p.ln(4)
        self._body("نتیجهٔ کلی:", bold=True)
        p.cell(
            0,
            7,
            _fa("[ ] قبول — آمادهٔ استفاده   [ ] قبول مشروط   [ ] رد — نیاز به اصلاح"),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        p.ln(3)
        self._blank_lines("باگ‌ها و یادداشت‌ها:", 5)
        self._blank_lines("امضا:", 1)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.pdf.output(str(path))


def main() -> int:
    builder = PdfBuilder()
    builder.cover()
    builder.part_intro()
    builder.part_prereq()
    builder.part_ui_description()
    builder.part_operator_prep()
    builder.part_scenario_success()
    builder.part_scenario_fail()
    builder.part_operator_verify()
    builder.part_quick_demo()
    builder.part_final_form()
    builder.save(OUT_PDF)
    print(f"PDF written: {OUT_PDF}")
    print(f"Size: {OUT_PDF.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
