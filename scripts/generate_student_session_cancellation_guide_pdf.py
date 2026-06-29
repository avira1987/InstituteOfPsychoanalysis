#!/usr/bin/env python3
"""
راهنمای PDF اپراتور — فرایند ۱۷: کنسل جلسات درمان آموزشی توسط دانشجو
(بدون جزئیات فنی؛ مناسب تست و پذیرش UI)

اجرا از ریشهٔ ریپو:
  python scripts/generate_student_session_cancellation_guide_pdf.py

خروجی:
  docs/راهنمای_تست_فرایند_۱۷_کنسل_جلسات_درمان.pdf
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
OUT_PDF = ROOT / "docs" / "راهنمای_تست_فرایند_۱۷_کنسل_جلسات_درمان.pdf"

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
                f"راهنمای تست فرایند ۱۷ — کنسل جلسات درمان — {self._footer_ts} — ص {self.page_no()}"
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
    ("دانشجو (درمان شروع شده)", "student1", "demo123"),
    ("درمانگر (بررسی تقویم)", "therapist1", "demo123"),
    ("مدیر / کارمند (بررسی پرونده)", "admin", "admin123"),
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

    def _check_table(self, rows_data: list[tuple[str, str]]) -> None:
        self._ensure_space(12 + len(rows_data) * 6)
        p = self.pdf
        hs = _heading_style()
        rows = [[_fa("کار / سؤال"), _fa("بله"), _fa("خیر"), _fa("یادداشت")]]
        for q, _ in rows_data:
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
        p.set_font("Vazir", "B", 13)
        p.cell(
            0,
            10,
            _fa("فرایند ۱۷ — کنسل کردن جلسات درمان آموزشی (توسط دانشجو)"),
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
                "این کتابچه برای اپراتور تست و پذیرش است تا بدون نیاز به دانش فنی، "
                "صفحهٔ ساخته‌شده برای کنسل جلسات درمان را امتحان کند و مطمئن شود "
                "قوانین سه‌هفتهٔ متوالی، سقف ۱۲ درصد کنسلی و مسیرهای هشدار/تخلف "
                "درست نمایش داده و اجرا می‌شوند."
            ),
            align="R",
        )
        p.ln(6)
        for label, blank in [
            ("نام اپراتور", "________________________"),
            ("تاریخ آزمایش", "________________________"),
            ("آدرس سایت", "________________________"),
        ]:
            p.cell(0, 8, _fa(f"{label}: {blank}"), align="R", new_x="LMARGIN", new_y="NEXT")
        p.ln(4)
        self._warn_box(
            "قبل از شروع، مسئول فنی باید سامانه را روشن کرده باشد. "
            "دانشجوی آزمایشی باید «درمان آموزشی» را شروع کرده و "
            "حداقل چند جلسهٔ برنامه‌ریزی‌شده در ۳ هفتهٔ آینده داشته باشد."
        )

    def part_intro(self) -> None:
        p = self.pdf
        p.add_page()
        self._section_bar("بخش ۱ — این فرایند چیست؟")
        self._body(
            "گاهی دانشجو نمی‌تواند در جلسهٔ درمان آموزشی حاضر شود و می‌خواهد "
            "همان جلسه را از تقویم خود کنسل کند. این کار فقط از پنل دانشجو و "
            "با نام «کنسل جلسه درمان» (فرایند ۱۷) انجام می‌شود."
        )
        self._body("سه قانون مهم:", bold=True)
        self._bullet_list([
            "فقط جلسات ۳ هفتهٔ آینده در لیست نشان داده می‌شوند.",
            "کنسل کردن بیش از ۳ هفتهٔ پشت‌سرهم (متوالی) از این مسیر مجاز نیست؛ "
            "برای وقفهٔ طولانی باید از «وقفه در درمان آموزشی» (فرایند ۱۶) استفاده شود.",
            "اگر مجموع کنسلی‌ها از ۱۲٪ کل جلسات بگذرد، تخلف آموزشی گزارش می‌شود؛ "
            "بین ۱۰ تا ۱۲٪ هشدار پیشگیری از تخلف ارسال می‌شود.",
        ])
        self._section_bar("بخش ۲ — چه کسانی درگیرند؟")
        roles = [
            ("دانشجو", "جلسات را انتخاب، فرم را ثبت و مرحله را تأیید می‌کند."),
            ("درمانگر", "جلسهٔ کنسل‌شده را در تقویم می‌بیند؛ نمی‌تواند برای آن حضور ثبت کند."),
            ("مدیر / کارمند", "در صورت نیاز، پروندهٔ فرایند و زیرفرایند مالی را بررسی می‌کند."),
        ]
        for role, desc in roles:
            self._body(f"{role}: {desc}", bold=True)

        self._section_bar("بخش ۳ — علامت‌گذاری نتیجه")
        self._bullet_list([
            "بله — یعنی موفق؛ همان‌طور که انتظار داشتید انجام شد.",
            "خیر — یعنی ناموفق؛ کار نشد یا پیام/رفتار اشتباه بود.",
            "خط تیره — یعنی انجام نشد یا دادهٔ آزمایشی برای آن سناریو نبود.",
        ])

    def part_login(self) -> None:
        p = self.pdf
        p.add_page()
        self._section_bar("بخش ۴ — ورود به سامانه")
        self._numbered_list([
            "مرورگر (Chrome یا Edge) را باز کنید.",
            "آدرس ورود را از مسئول فنی بگیرید (مثلاً .../login).",
            "روی «ورود با رمز عبور» بزنید.",
            "سؤال ریاضی ساده را جواب دهید.",
            "نام کاربری و رمز را وارد کنید و «ورود» بزنید.",
            "برای عوض کردن نقش: «خروج» → دوباره ورود با حساب دیگر.",
        ])
        self._section_bar("بخش ۵ — حساب‌های لازم")
        with p.table(
            col_widths=(72, 58, 28),
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
            for role, user, pw in ACCOUNTS:
                row = table.row()
                row.cell(_fa(role))
                row.cell(user, align=Align.C)
                row.cell(pw, align=Align.C)
        p.ln(4)
        self._tip_box(
            "مسیر ورود دانشجو: بعد از ورود به «پورتال دانشجو» بروید. "
            "میانبر «کنسل جلسه درمان» در داشبورد یا تب «درخواست‌های دیگر» است."
        )

    def part_before_test(self) -> None:
        p = self.pdf
        p.add_page()
        self._section_bar("بخش ۶ — قبل از شروع (چک‌لیست آماده‌سازی)")
        self._body(
            "اپراتور یا مسئول فنی این موارد را یک‌بار بررسی کند. "
            "اگر هر مورد «خیر» بود، قبل از ادامه هماهنگ کنید."
        )
        prep = [
            "سامانه باز می‌شود و صفحهٔ ورود خطا نمی‌دهد.",
            "با student1 می‌توان وارد پورتال دانشجو شد.",
            "دانشجو درمان آموزشی را «شروع کرده» است.",
            "حداقل ۲ جلسهٔ «برنامه‌ریزی‌شده» در ۳ هفتهٔ آینده برای دانشجو وجود دارد.",
            "فرایند ۱۷ قبلاً برای همین دانشجو «باز و ناتمام» نیست (یا پروندهٔ قبلی بسته شده).",
        ]
        self._check_table([(q, "") for q in prep])

    def part_student_main(self) -> None:
        p = self.pdf
        p.add_page()
        self._section_bar("فاز الف — دانشجو: شروع و انتخاب جلسات")
        self._body("با حساب: student1", bold=True)
        self._body("مسیر: پورتال دانشجو — شروع «کنسل جلسه درمان» یا تب فرایندها", bold=True)
        self._numbered_list([
            "با student1 وارد شوید و به پورتال دانشجو بروید.",
            "روی «کنسل جلسه درمان» (فرایند ۱۷) بزنید یا از «درخواست‌های دیگر» آن را شروع کنید.",
            "روی همان فرایند کلیک کنید تا جزئیات باز شود.",
            "کارت آبی «کنسل جلسات درمان آموزشی (فرایند ۱۷)» را ببینید.",
            "در کارت: «درصد کنسلی فعلی»، «جلسات ۳ هفتهٔ آینده» و راهنمای آبی بالا را بخوانید.",
            "در فرم پایین، لیست جلسات با تیک را ببینید (فقط ۳ هفتهٔ آینده).",
            "یک یا دو جلسه را تیک بزنید.",
            "دکمهٔ «ثبت فرم» یا «ثبت اطلاعات این مرحله» را بزنید — پیام موفقیت بیاید.",
            "دکمهٔ «ادامه و ثبت مرحله» را بزنید.",
            "وضعیت باید به «جلسات انتخاب شده» برود.",
        ])
        self._ok_box(
            "بعد از انتخاب، در کارت «درصد پس از این کنسلی» به‌روز شود "
            "و تعداد جلسات انتخاب‌شده نمایش داده شود."
        )
        self._section_bar("چک‌لیست فاز الف")
        checks = [
            "کارت فرایند ۱۷ (آبی/قرمز) بدون خطا دیده شد.",
            "لیست جلسات ۳ هفتهٔ آینده پر بود.",
            "تیک زدن و ثبت فرم موفق بود.",
            "«ادامه و ثبت مرحله» وضعیت را عوض کرد.",
            "متن راهنما فارسی و قابل فهم بود.",
        ]
        self._check_table([(q, "") for q in checks])
        self._blank_lines("یادداشت:", 2)

    def part_student_confirm(self) -> None:
        p = self.pdf
        p.add_page()
        self._section_bar("فاز ب — دانشجو: تأیید نهایی (مسیر عادی)")
        self._body(
            "اگر درصد کنسلی پس از انتخاب کمتر از ۱۰٪ است، این فاز را کامل کنید.",
            bold=True,
        )
        self._numbered_list([
            "در همان جزئیات فرایند، وضعیت «جلسات انتخاب شده» را ببینید.",
            "در کارت، «درصد پس از این کنسلی» باید سبز یا زیر ۱۰٪ باشد.",
            "هشدار قرمز «تخلف» نباید باشد (مگر درصد بالا باشد).",
            "«ادامه و ثبت مرحله» (تأیید نهایی) را بزنید.",
            "وضعیت باید به «کنسلی اعمال و تعیین تکلیف مالی» برود.",
            "پیام سبز پایان در کارت: «کنسلی ثبت شد… تعیین تکلیف مالی…»",
        ])
        self._ok_box("فرایند «تمام شده» شود و دیگر دکمهٔ ادامه نباشد.")
        self._section_bar("چک‌لیست فاز ب")
        self._check_table([
            ("تأیید نهایی بدون خطا انجام شد", ""),
            ("پیام پایان سبز دیده شد", ""),
            ("فرایند بسته / تکمیل شد", ""),
        ])

    def part_student_warning(self) -> None:
        p = self.pdf
        p.add_page()
        self._section_bar("فاز ج — مسیر هشدار ۱۰ تا ۱۲٪ (در صورت امکان)")
        self._body(
            "فقط اگر مسئول فنی دانشجویی با «سوابق کنسلی نزدیک ۱۰٪» آماده کرده "
            "یا می‌توانید چند جلسهٔ زیاد کنسل کنید تا به این بازه برسید.",
            bold=True,
        )
        self._numbered_list([
            "بعد از انتخاب جلسات، در کارت «درصد پس از این کنسلی» بین ۱۰ و ۱۲ باشد.",
            "جعبهٔ زرد «هشدار پیشگیری از تخلف» را ببینید.",
            "تأیید نهایی را بزنید.",
            "وضعیت «هشدار ۱۰–۱۲٪ + کنسلی اعمال» و پیام زرد پایان را ببینید.",
        ])
        self._check_table([
            ("هشدار زرد ۱۰–۱۲٪ نمایش داده شد", ""),
            ("پایان با پیام هشدار به کمیته", ""),
        ])

    def part_student_violation(self) -> None:
        p = self.pdf
        p.add_page()
        self._section_bar("فاز د — مسیر تخلف بالای ۱۲٪ (در صورت امکان)")
        self._warn_box(
            "این سناریو فقط برای آزمایش است. در واقعیت، کنسل زیاد تبعات آموزشی دارد."
        )
        self._numbered_list([
            "بعد از انتخاب، «درصد پس از این کنسلی» بالای ۱۲٪ باشد.",
            "جعبهٔ قرمز «هشدار تخلف آموزشی» و متن SOP را ببینید.",
            "در فرم، چک‌باکس «می‌دانم که… تخلف…» را بزنید و فرم را ثبت کنید.",
            "بدون تیک، «ادامه» باید خطا بدهد.",
            "با تیک، تأیید نهایی — وضعیت «تخلف >۱۲٪ + کنسلی اعمال» و پیام قرمز.",
        ])
        self._check_table([
            ("هشدار قرمز بالای ۱۲٪ دیده شد", ""),
            ("بدون چک‌باکس، خطا آمد", ""),
            ("با چک‌باکس، کنسلی ثبت شد", ""),
        ])

    def part_consecutive_block(self) -> None:
        p = self.pdf
        p.add_page()
        self._section_bar("فاز ه — مسدود شدن ۳ هفته متوالی (در صورت امکان)")
        self._body(
            "اگر انتخاب جلسات منجر به کنسل بیش از ۳ هفتهٔ پشت‌سرهم شود، "
            "سامانه باید اجازهٔ ادامه ندهد.",
            bold=True,
        )
        self._numbered_list([
            "جلساتی را انتخاب کنید که کل ۳ هفتهٔ متوالی خالی شوند (با راهنمایی فنی).",
            "جعبهٔ قرمز «محدودیت ۳ هفته متوالی» را در کارت ببینید.",
            "بعد از «ادامه»، وضعیت «مسدود — بیش از ۳ هفته متوالی» یا پیام خطا.",
            "متن پیشنهاد «وقفه در درمان آموزشی (فرایند ۱۶)» نمایش داده شود.",
        ])
        self._check_table([
            ("مسدودسازی ۳ هفته متوالی کار کرد", ""),
            ("پیام راهنما به فرایند ۱۶ اشاره کرد", ""),
        ])

    def part_therapist_verify(self) -> None:
        p = self.pdf
        p.add_page()
        self._section_bar("فاز و — درمانگر: بررسی پس از کنسل")
        self._body("با حساب: therapist1", bold=True)
        self._numbered_list([
            "بعد از ثبت کنسلی توسط دانشجو، با therapist1 وارد شوید.",
            "پورتال درمانگر — تب «جلسات آنلاین» یا لیست جلسات.",
            "جلسهٔ کنسل‌شده باید وضعیت «cancelled» یا «کنسل» داشته باشد.",
            "در تب «حضور و غیاب»، آن جلسه نباید در «نیاز به ثبت» باشد.",
        ])
        self._check_table([
            ("جلسه در تقویم درمانگر «کنسل» است", ""),
            ("ثبت حضور برای همان جلسه ممکن نیست", ""),
        ])

    def part_admin_verify(self) -> None:
        p = self.pdf
        p.add_page()
        self._section_bar("فاز ز — مدیر: بررسی پرونده (اختیاری)")
        self._body("با حساب: admin", bold=True)
        self._numbered_list([
            "وارد پنل مدیریت شوید.",
            "ردیابی دانشجو (Student Tracker) یا لیست فرایندها را باز کنید.",
            "فرایند ۱۷ همان دانشجو را پیدا کنید — باید «تکمیل شده» باشد.",
            "در صورت مسیر هشدار/تخلف، پروندهٔ «ثبت تخلف» ممکن است باز شده باشد.",
            "برای هر جلسه کنسل‌شده، «تعیین تکلیف مالی» ممکن است زیرفرایند باز کرده باشد.",
        ])
        self._tip_box(
            "اگر زیرفرایند مالی را نمی‌بینید، به مسئول فنی بگویید — "
            "ممکن است در محیط دمو هنوز اجرا نشده باشد."
        )
        self._check_table([
            ("پروندهٔ فرایند ۱۷ تکمیل‌شده دیده شد", ""),
            ("وضعیت نهایی با انتظار اپراتور هم‌خوان بود", ""),
        ])

    def part_quick_demo(self) -> None:
        p = self.pdf
        p.add_page()
        self._section_bar("پیوست — مسیر سریع ۱۵ دقیقه‌ای")
        self._numbered_list([
            "student1: شروع فرایند ۱۷، انتخاب ۱ جلسه، ثبت فرم، ادامه.",
            "student1: تأیید نهایی — بررسی کارت و پیام پایان.",
            "therapist1: بررسی کنسل شدن جلسه در تقویم.",
            "admin: بررسی بسته شدن پرونده (اختیاری).",
        ])
        self._tip_box("حداقل فازهای الف، ب و و برای پذیرش اصلی کافی است.")

    def part_ui_elements(self) -> None:
        p = self.pdf
        p.add_page()
        self._section_bar("پیوست — چه چیزهایی باید در صفحه ببینید؟")
        self._body("در کارت «کنسل جلسات درمان آموزشی (فرایند ۱۷)»:", bold=True)
        self._bullet_list([
            "عنوان و برچسب وضعیت فعلی (مثلاً «نمایش تقویم ۳ هفته آینده»).",
            "جعبهٔ راهنمای آبی در ابتدا.",
            "کاشی‌های آماری: سوابق، درصد فعلی، درصد پس از انتخاب، تعداد جلسات قابل انتخاب.",
            "جعبهٔ قرمز محدودیت ۳ هفته (در صورت نقض).",
            "جعبهٔ زرد هشدار ۱۰–۱۲٪ یا قرمز تخلف >۱۲٪.",
            "فرم لیست جلسات با تیک.",
            "دکمهٔ «ادامه و ثبت مرحله» بعد از ثبت فرم.",
        ])
        self._body("در کارت کوئست (داشبورد):", bold=True)
        self._body(
            "پیش‌نمایش کوچک با «درصد کنسلی فعلی» و «جلسات ۳ هفتهٔ آینده» "
            "قبل از باز کردن جزئیات."
        )

    def part_final(self) -> None:
        p = self.pdf
        p.add_page()
        self._section_bar("جمع‌بندی و تأیید نهایی")
        self._body("تاریخ تست: _______________     اپراتور: _______________", bold=True)
        summary_rows = [
            ("فاز الف — انتخاب جلسات", ""),
            ("فاز ب — تأیید عادی (<۱۰٪)", ""),
            ("فاز ج — هشدار ۱۰–۱۲٪", ""),
            ("فاز د — تخلف >۱۲٪", ""),
            ("فاز ه — مسدود ۳ هفته", ""),
            ("فاز و — بررسی درمانگر", ""),
            ("فاز ز — بررسی مدیر", ""),
        ]
        self._check_table(summary_rows)
        p.ln(2)
        self._body("نتیجهٔ کلی:", bold=True)
        self._bullet_list([
            "[ ]  قبول — UI برای استفادهٔ عملیاتی آماده است.",
            "[ ]  قبول مشروط — کار می‌کند ولی متن/جزئیات نیاز به بهبود دارد.",
            "[ ]  رد — مسئلهٔ جدی وجود دارد.",
        ])
        self._blank_lines("سه مهم‌ترین مشکل یا پیشنهاد:", 4)
        self._blank_lines("امضا اپراتور:", 1)
        p.ln(4)
        self._body(
            "این فایل را پر شده — و در صورت مشکل عکس از صفحه — "
            "برای مسئول پروژه بفرستید.",
            bold=True,
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.pdf.output(str(path))


def main() -> int:
    builder = PdfBuilder()
    builder.cover()
    builder.part_intro()
    builder.part_login()
    builder.part_before_test()
    builder.part_student_main()
    builder.part_student_confirm()
    builder.part_student_warning()
    builder.part_student_violation()
    builder.part_consecutive_block()
    builder.part_therapist_verify()
    builder.part_admin_verify()
    builder.part_ui_elements()
    builder.part_quick_demo()
    builder.part_final()
    builder.save(OUT_PDF)
    print(f"PDF written: {OUT_PDF}")
    print(f"Size: {OUT_PDF.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
