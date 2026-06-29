#!/usr/bin/env python3
"""
راهنمای PDF اپراتور — فرایند ۶: حضور و غیاب جلسات درمان آموزشی
(بدون جزئیات فنی؛ مناسب تست و پذیرش UI)

اجرا از ریشهٔ ریپو:
  python scripts/generate_attendance_tracking_operator_guide_pdf.py

خروجی:
  docs/راهنمای_تست_فرایند_۶_حضور_و_غیاب_درمان.pdf
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
OUT_PDF = ROOT / "docs" / "راهنمای_تست_فرایند_۶_حضور_و_غیاب_درمان.pdf"

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
                f"راهنمای تست فرایند ۶ — حضور و غیاب درمان — {self._footer_ts} — ص {self.page_no()}"
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
    ("درمانگر آموزشی", "therapist1", "demo123"),
    ("مسئول سایت", "site_manager1", "demo123"),
    ("معاون آموزش", "deputy_education1", "demo123"),
    ("مدیر سامانه (در صورت نیاز)", "admin", "admin123"),
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
        """rows: (سؤال/کار, ستون نتیجه خالی)"""
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
            _fa("فرایند ۶ — حضور و غیاب جلسات درمان آموزشی"),
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
                "صفحه‌های ساخته‌شده برای ثبت حضور و غیاب جلسات درمان را امتحان کند "
                "و مطمئن شود همهٔ نقش‌ها (دانشجو، درمانگر، مسئول سایت) درست کار می‌کنند."
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
            "حداقل یک جلسهٔ پرداخت‌شده در تقویم داشته باشد."
        )

    def part_intro(self) -> None:
        p = self.pdf
        p.add_page()
        self._section_bar("بخش ۱ — این فرایند چیست؟")
        self._body(
            "وقتی دانشجو درمان آموزشی را شروع کرده و برای جلسه پرداخت کرده، "
            "بعد از برگزاری جلسه درمانگر باید مشخص کند دانشجو «حاضر» بوده یا «غایب». "
            "هر بار که «حاضر» ثبت شود، یک ساعت به پیشرفت درمان دانشجو اضافه می‌شود. "
            "دانشجو خودش حضور را ثبت نمی‌کند؛ فقط پیشرفت ساعات را می‌بیند."
        )
        self._section_bar("بخش ۲ — چه کسانی درگیرند؟")
        roles = [
            ("درمانگر آموزشی", "بعد از هر جلسه، حاضر / غایب موجه / غایب غیرموجه را ثبت می‌کند."),
            ("دانشجو", "ساعات جمع‌شده و وضعیت جلسات اخیر را در پروفایل می‌بیند."),
            ("مسئول سایت", "اگر درمانگر به‌موقع ثبت نکند، پیگیری می‌کند."),
            ("معاون آموزش", "فقط در صورت تأخیر طولانی پیگیری مسئول سایت، پرونده به او می‌رسد."),
        ]
        for role, desc in roles:
            self._body(f"{role}: {desc}", bold=True)

        self._section_bar("بخش ۳ — علامت‌گذاری نتیجه")
        self._bullet_list([
            "بله — یعنی موفق؛ همان‌طور که انتظار داشتید انجام شد.",
            "خیر — یعنی ناموفق؛ کار نشد یا رفتار اشتباه بود.",
            "خط تیره — یعنی انجام نشد یا خارج از دامنهٔ این آزمایش.",
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
            "برای عوض کردن نقش: «خروج»، سپس دوباره ورود با حساب دیگر.",
        ])
        self._section_bar("بخش ۵ — حساب‌های لازم برای این آزمایش")
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
            "اگر student1 درمان را شروع نکرده، از مسئول فنی بخواهید "
            "ابتدا فرایند «آغاز درمان» و «پرداخت جلسه» را برای او تکمیل کند."
        )

    def part_before_test(self) -> None:
        p = self.pdf
        p.add_page()
        self._section_bar("بخش ۶ — قبل از شروع (چک‌لیست آماده‌سازی)")
        self._body(
            "اپراتور یا مسئول فنی این موارد را یک‌بار بررسی کند. "
            "اگر هر مورد «خیر» بود، قبل از ادامه با مسئول فنی هماهنگ کنید."
        )
        prep = [
            "سامانه باز می‌شود و صفحهٔ ورود خطا نمی‌دهد.",
            "با therapist1 می‌توان وارد پورتال درمانگر شد.",
            "با student1 می‌توان وارد پورتال دانشجو شد.",
            "دانشجو student1 درمان آموزشی را «شروع کرده» است.",
            "حداقل یک جلسهٔ درمان برای این دانشجو «پرداخت‌شده» است.",
            "تاریخ آن جلسه امروز یا گذشته است (نه فقط آینده).",
        ]
        self._check_table([(q, "") for q in prep])

    def part_therapist(self) -> None:
        p = self.pdf
        p.add_page()
        self._section_bar("فاز الف — درمانگر: ثبت حضور و غیاب")
        self._body("با حساب: therapist1", bold=True)
        self._body("مسیر: بعد از ورود، منو، پورتال درمانگر، تب «حضور و غیاب»", bold=True)
        self._body("قدم‌به‌قدم:", bold=True)
        self._numbered_list([
            "با therapist1 وارد شوید.",
            "به پورتال درمانگر بروید.",
            "تب «حضور و غیاب» را باز کنید (کنار تب‌های کارهای من، جلسات آنلاین و...).",
            "بالای صفحه سه عدد می‌بینید: «نیاز به ثبت»، «ثبت‌شده»، «بسته / غیرقابل ثبت».",
            "فیلتر «نیاز به ثبت» را انتخاب کنید.",
            "برای یک جلسهٔ پرداخت‌شده، یکی از دکمه‌ها را بزنید: "
            "«حاضر (+۱ ساعت)» یا «غایب موجه» یا «غایب غیرموجه».",
            "پیام موفقیت (سبز) باید بیاید و آن جلسه از لیست «نیاز به ثبت» خارج شود.",
            "دکمه «بروزرسانی» را بزنید و ببینید عدد «ثبت‌شده» زیاد شده است.",
        ])
        self._ok_box(
            "بعد از زدن «حاضر»، جلسه در فیلتر «ثبت‌شده» دیده می‌شود "
            "و برچسب «حاضر» روی همان ردیف نمایش داده می‌شود."
        )
        self._section_bar("چک‌لیست فاز الف — درمانگر")
        checks_a = [
            "تب «حضور و غیاب» بدون خطا باز شد.",
            "جلسهٔ نیازمند ثبت در لیست دیده شد.",
            "دکمه «حاضر» کار کرد و پیام موفقیت آمد.",
            "جلسه از «نیاز به ثبت» خارج شد.",
            "متن راهنما بالای صفحه قابل فهم بود.",
            "دکمه یا متن گیج‌کننده بود (یادداشت کنید).",
        ]
        self._check_table([(q, "") for q in checks_a])
        self._blank_lines("یادداشت / مشکل:", 3)

    def part_therapist_absence(self) -> None:
        p = self.pdf
        p.add_page()
        self._section_bar("فاز ب — درمانگر: ثبت غیبت (اختیاری ولی توصیه می‌شود)")
        self._body("با حساب: therapist1 — همان تب «حضور و غیاب»", bold=True)
        self._numbered_list([
            "اگر جلسهٔ دیگری در «نیاز به ثبت» هست، «غایب موجه» یا «غایب غیرموجه» را امتحان کنید.",
            "بعد از ثبت، جلسه باید «ثبت‌شده» شود و نوع غیبت روی آن نوشته شود.",
        ])
        self._warn_box(
            "غیبت غیرموجه ممکن است پیامدهای مالی یا آموزشی داشته باشد؛ "
            "در محیط آزمایشی فقط مسیر دکمه را بررسی کنید."
        )
        self._check_table([
            ("ثبت «غایب موجه» یا «غایب غیرموجه» انجام شد", ""),
            ("وضعیت روی کارت جلسه درست نمایش داده شد", ""),
        ])

    def part_student(self) -> None:
        p = self.pdf
        p.add_page()
        self._section_bar("فاز ج — دانشجو: دیدن پیشرفت ساعات")
        self._body("با حساب: student1", bold=True)
        self._body("مسیر: پورتال دانشجو، تب «پروفایل»", bold=True)
        self._numbered_list([
            "خارج شوید و با student1 وارد شوید.",
            "به پورتال دانشجو بروید.",
            "تب «پрофایل» را باز کنید.",
            "کارت «پیشرفت ساعات درمان آموزشی (فرایند ۶)» را پیدا کنید.",
            "نوار پیشرفت (مثلاً «۴۵ از ۲۵۰») و درصد را ببینید.",
            "بخش «آخرین جلسات» را بخوانید — برای جلسه‌ای که درمانگر «حاضر» زد، "
            "باید «حاضر» یا وضعیت پرداخت دیده شود.",
            "دکمه «بروزرسانی» را بزنید — اعداد نباید خطا بدهند.",
        ])
        self._ok_box(
            "اگر درمانگر «حاضر» ثبت کرده باشد، عدد ساعات دانشجو "
            "باید حداقل یک واحد بیشتر از قبل باشد (بعد از بروزرسانی صفحه)."
        )
        self._section_bar("چک‌لیست فاز ج — دانشجو")
        checks_c = [
            "کارت پیشرفت ساعات در پروفایل دیده شد.",
            "نوار پیشرفت و عدد «از ۲۵۰» نمایش داده شد.",
            "لیست آخرین جلسات خطا نداد.",
            "بعد از ثبت «حاضر» توسط درمانگر، ساعات به‌روز شد.",
            "متن راهنما پایین کارت قابل فهم بود.",
        ]
        self._check_table([(q, "") for q in checks_c])
        self._blank_lines("عدد ساعات قبل از تست / بعد از تست:", 1)

    def part_site_manager(self) -> None:
        p = self.pdf
        p.add_page()
        self._section_bar("فاز د — مسئول سایت: پیگیری (در صورت امکان)")
        self._body(
            "این بخش فقط وقتی معنی دارد که سامانه جلسه‌ای نشان دهد "
            "«درمانگر ثبت نکرده» و پرونده منتظر مسئول سایت باشد. "
            "اگر در محیط آزمایشی چنین موردی نیست، این فاز را «خط تیره» بزنید."
        )
        self._body("با حساب: site_manager1", bold=True)
        self._body("مسیر: پورتال مسئول سایت، تب «هشدارها» یا «پیگیری‌ها»", bold=True)
        self._numbered_list([
            "با site_manager1 وارد شوید.",
            "به پورتال مسئول سایت بروید.",
            "تب «هشدارها» را باز کنید.",
            "اگر مورد «حضور و غیاب درمان» دیدید، روی آن کلیک کنید.",
            "متن راهنمای قرمز رنگ دربارهٔ «پیگیری عدم ثبت» را بخوانید.",
            "پس از تماس با درمانگر (در واقعیت)، دکمهٔ «مسئول سایت پیگیری کرد» را بزنید.",
            "پیام موفقیت بیاید و وضعیت پرونده عوض شود.",
        ])
        self._check_table([
            ("تب هشدارها باز شد", ""),
            ("راهنمای فارسی پیگیری دیده شد (در صورت وجود پرونده)", ""),
            ("دکمهٔ پیگیری کار کرد (در صورت وجود پرونده)", ""),
        ])

    def part_negative(self) -> None:
        p = self.pdf
        p.add_page()
        self._section_bar("فاز ه — موارد خاص (در صورت امکان)")
        self._body("این موارد را اگر دادهٔ آزمایشی اجازه داد بررسی کنید:", bold=True)
        cases = [
            (
                "جلسه پرداخت‌نشده",
                "در لیست درمانگر باید «پرداخت نشده» یا «غیرقابل ثبت» "
                "ببینید — نباید بتوانید «حاضر» بزنید.",
            ),
            (
                "جلسه کنسل‌شده",
                "باید «بسته» یا «کنسل» نشان داده شود.",
            ),
            (
                "ثبت مجدد همان جلسه",
                "بعد از ثبت «حاضر»، همان جلسه نباید دوباره "
                "در «نیاز به ثبت» بیاید.",
            ),
        ]
        for title, desc in cases:
            self._body(title, bold=True)
            self._body(desc)
            p.ln(1)
        self._check_table([
            ("جلسه پرداخت‌نشده — ثبت مسدود بود", ""),
            ("ثبت تکراری ممکن نبود", ""),
        ])

    def part_quick_demo(self) -> None:
        p = self.pdf
        p.add_page()
        self._section_bar("پیوست — مسیر سریع ۱۰ دقیقه‌ای (دمو)")
        self._numbered_list([
            "therapist1: پورتال درمانگر، حضور و غیاب، «حاضر» برای یک جلسه.",
            "student1: پروفایل، بررسی به‌روز شدن ساعات و جلسه.",
            "therapist1: تب «کارهای من»، در صورت پرونده باز، دکمه‌های حاضر/غایب در جزئیات.",
            "site_manager1: هشدارها (در صورت وجود مورد).",
        ])
        self._tip_box(
            "اگر وقت کم دارید، فازهای الف و ج را کامل کنید؛ "
            "همان‌ها برای پذیرش اصلی کافی است."
        )

    def part_final(self) -> None:
        p = self.pdf
        p.add_page()
        self._section_bar("جمع‌بندی و تأیید نهایی")
        self._body("تاریخ تست: _______________     اپراتور: _______________", bold=True)
        summary_rows = [
            ("فاز الف — درمانگر (تب حضور و غیاب)", ""),
            ("فاز ب — ثبت غیبت", ""),
            ("فاز ج — دانشجو (پیشرفت ساعات)", ""),
            ("فاز د — مسئول سایت", ""),
            ("فاز ه — موارد خاص", ""),
        ]
        self._check_table(summary_rows)
        p.ln(2)
        self._body("نتیجهٔ کلی (یکی را علامت بزنید):", bold=True)
        self._bullet_list([
            "[ ]  قبول — UI برای استفادهٔ عملیاتی آماده است.",
            "[ ]  قبول مشروط — کار می‌کند ولی متن/جزئیات نیاز به بهبود دارد.",
            "[ ]  رد — مسئلهٔ جدی وجود دارد و باید قبل از استفاده رفع شود.",
        ])
        self._blank_lines("سه مهم‌ترین مشکل یا پیشنهاد:", 4)
        self._blank_lines("امضا اپراتور:", 1)
        p.ln(4)
        self._body(
            "این فایل را پر شده همراه عکس از صفحه (در صورت مشکل) "
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
    builder.part_therapist()
    builder.part_therapist_absence()
    builder.part_student()
    builder.part_site_manager()
    builder.part_negative()
    builder.part_quick_demo()
    builder.part_final()
    builder.save(OUT_PDF)
    print(f"PDF written: {OUT_PDF}")
    print(f"Size: {OUT_PDF.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
