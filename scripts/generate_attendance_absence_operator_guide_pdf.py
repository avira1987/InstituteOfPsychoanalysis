#!/usr/bin/env python3
"""
راهنمای PDF اپراتور — فرایند ۶ (حضور و غیاب درمان) و فرایند ۱۵ (واکنش به غیبت بدون اطلاع)
بدون جزئیات فنی؛ مناسب تست و پذیرش UI ساخته‌شده

اجرا از ریشهٔ ریپو:
  python scripts/generate_attendance_absence_operator_guide_pdf.py

خروجی:
  docs/راهنمای_تست_فرایندهای_۶_و_۱۵_حضور_و_غیبت.pdf
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
OUT_PDF = ROOT / "docs" / "راهنمای_تست_فرایندهای_۶_و_۱۵_حضور_و_غیبت.pdf"

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
                f"راهنمای تست فرایندهای ۶ و ۱۵ — {self._footer_ts} — ص {self.page_no()}"
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
    ("رئیس کمیته درمان آموزشی", "therapy_committee_chair1", "demo123"),
    ("مجری کمیته درمان آموزشی", "therapy_committee_executor1", "demo123"),
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

    def _check_table(self, rows_data: list[str]) -> None:
        self._ensure_space(12 + len(rows_data) * 6)
        p = self.pdf
        hs = _heading_style()
        rows = [[_fa("کار / سؤال"), _fa("بله"), _fa("خیر"), _fa("یادداشت")]]
        for q in rows_data:
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
            _fa("فرایند ۶ — حضور و غیاب درمان آموزشی"),
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        p.cell(
            0,
            10,
            _fa("فرایند ۱۵ — واکنش به غیبت بدون اطلاع (No-Show)"),
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
                "صفحه‌های راهنمای ساخته‌شده در سامانه را گام‌به‌گام امتحان کند "
                "و مطمئن شود هر نقش (درمانگر، مسئول سایت، کمیته درمان) "
                "کار درستی را می‌بیند و می‌تواند انجام دهد."
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
            "دانشجوی آزمایشی باید درمان آموزشی را شروع کرده و "
            "حداقل یک جلسهٔ پرداخت‌شده داشته باشد."
        )

    def part_overview(self) -> None:
        p = self.pdf
        p.add_page()
        self._section_bar("بخش ۱ — این دو فرایند چه می‌کنند؟")
        self._body("فرایند ۶ — حضور و غیاب جلسات درمان", bold=True)
        self._body(
            "بعد از هر جلسهٔ درمان، درمانگر مشخص می‌کند دانشجو حاضر بوده یا غایب. "
            "هر «حاضر» یک ساعت به پیشرفت درمان اضافه می‌کند. "
            "اگر درمانگر به‌موقع ثبت نکند، مسئول سایت پیگیری می‌کند."
        )
        p.ln(2)
        self._body("فرایند ۱۵ — واکنش به غیبت بدون اطلاع", bold=True)
        self._body(
            "اگر دانشجو بدون اطلاع قبلی در جلسه حاضر نشود (No-Show)، سامانه واکنش نشان می‌دهد: "
            "غیبت اول فقط پیامک یادآوری است؛ دو جلسهٔ پشت‌سرهم بدون اطلاع "
            "پرونده را به مسئول سایت و در صورت نیاز به کمیته درمان می‌فرستد."
        )
        self._section_bar("بخش ۲ — چه کسانی درگیرند؟")
        roles = [
            ("درمانگر", "ثبت حاضر / غایب؛ دیدن کارت راهنمای فرایند ۶ در «کارهای من»."),
            ("دانشجو", "دیدن پیشرفت ساعات در پروفایل (بدون ثبت حضور)."),
            ("مسئول سایت", "پیگیری عدم ثبت درمانگر؛ تصمیم دربارهٔ دو غیبت پیوسته."),
            ("رئیس کمیته درمان", "واگذاری پرونده به مجری کمیته."),
            ("مجری کمیته درمان", "ثبت نتیجهٔ نهایی (قطع درمان یا پذیرش بازگشت)."),
            ("معاون آموزش", "فقط اگر مسئول سایت بیش از ۲ روز پیگیری نکند."),
        ]
        for role, desc in roles:
            self._body(f"{role}: {desc}", bold=True)

        self._section_bar("بخش ۳ — علامت‌گذاری نتیجه")
        self._bullet_list([
            "بله — یعنی موفق؛ همان‌طور که انتظار داشتید انجام شد.",
            "خیر — یعنی ناموفق؛ کار نشد یا رفتار اشتباه بود.",
            "خط تیره — یعنی انجام نشد / دادهٔ آزمایشی نبود.",
        ])

    def part_login(self) -> None:
        p = self.pdf
        p.add_page()
        self._section_bar("بخش ۴ — ورود به سامانه")
        self._numbered_list([
            "مرورگر (Chrome یا Edge) را باز کنید.",
            "آدرس ورود را از مسئول فنی بگیرید.",
            "روی «ورود با رمز عبور» بزنید.",
            "سؤال ریاضی ساده را جواب دهید.",
            "نام کاربری و رمز را وارد کنید و «ورود» بزنید.",
            "برای عوض کردن نقش: «خروج» سپس دوباره ورود با حساب دیگر.",
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
            "اگر student1 درمان را شروع نکرده، از مسئول فنی بخواهید "
            "ابتدا «آغاز درمان» و «پرداخت جلسه» را تکمیل کند."
        )

    def part_prep(self) -> None:
        p = self.pdf
        p.add_page()
        self._section_bar("بخش ۶ — چک‌لیست قبل از شروع")
        prep = [
            "سامانه باز می‌شود و صفحهٔ ورود خطا نمی‌دهد.",
            "با therapist1 می‌توان وارد پورتال درمانگر شد.",
            "با student1 می‌توان وارد پورتال دانشجو شد.",
            "دانشجو student1 درمان آموزشی را شروع کرده است.",
            "حداقل یک جلسهٔ پرداخت‌شده برای این دانشجو وجود دارد.",
            "با site_manager1 پورتال مسئول سایت باز می‌شود.",
        ]
        self._check_table(prep)

    def part_p6_therapist_tab(self) -> None:
        p = self.pdf
        p.add_page()
        self._section_bar("فرایند ۶ — فاز الف: درمانگر (تب حضور و غیاب)")
        self._body("حساب: therapist1", bold=True)
        self._body("مسیر: پورتال درمانگر، تب «حضور و غیاب»", bold=True)
        self._numbered_list([
            "با therapist1 وارد شوید.",
            "به پورتال درمانگر بروید.",
            "تب «حضور و غیاب» را باز کنید.",
            "بالای صفحه سه عدد می‌بینید: نیاز به ثبت، ثبت‌شده، بسته.",
            "فیلتر «نیاز به ثبت» را انتخاب کنید.",
            "برای یک جلسه «حاضر (+۱ ساعت)» یا «غایب موجه» یا «غایب غیرموجه» بزنید.",
            "پیام موفقیت بیاید و جلسه از «نیاز به ثبت» خارج شود.",
        ])
        self._ok_box("جلسه در فیلتر «ثبت‌شده» با برچسب «حاضر» دیده می‌شود.")
        self._check_table([
            "تب حضور و غیاب بدون خطا باز شد",
            "جلسه در لیست «نیاز به ثبت» دیده شد",
            "دکمه «حاضر» کار کرد",
            "متن راهنما بالای صفحه قابل فهم بود",
        ])

    def part_p6_therapist_panel(self) -> None:
        p = self.pdf
        p.add_page()
        self._section_bar("فرایند ۶ — فاز ب: درمانگر (کارت راهنما در کارهای من)")
        self._body("حساب: therapist1", bold=True)
        self._body("مسیر: پورتال درمانگر، تب «کارهای من»، باز کردن پرونده حضور و غیاب", bold=True)
        self._numbered_list([
            "تب «کارهای من» را باز کنید.",
            "اگر پروندهٔ «تکمیل ساعات درمان آموزشی» در لیست است، روی آن کلیک کنید.",
            "کارت آبی با عنوان «تکمیل ساعات درمان آموزشی (فرایند ۶)» را ببینید.",
            "نوار مراحل (جلسه برنامه‌ریزی، ثبت درمانگر، ...) باید مرحلهٔ فعلی را نشان دهد.",
            "راهنمای فارسی زیر کارت بگوید چه کاری باید انجام شود.",
            "اگر وضعیت «ثبت حضور و غیاب توسط درمانگر» است، "
            "دکمه‌های «حاضر»، «غایب موجه»، «غایب غیرموجه» را ببینید و یکی را امتحان کنید.",
            "تاریخ جلسه و شناسه جلسه (در صورت نمایش) باید خوانا باشد.",
        ])
        self._ok_box(
            "کارت راهنما با وضعیت فعلی و راهنمای گام بعدی نمایش داده می‌شود "
            "و دکمه‌های ثبت حضور کار می‌کنند."
        )
        self._check_table([
            "کارت «فرایند ۶» در جزئیات پرونده دیده شد",
            "نوار مراحل (stepper) مرحلهٔ درست را نشان داد",
            "راهنمای فارسی قابل فهم بود",
            "دکمه‌های حاضر/غایب در همان صفحه کار کردند",
        ])

    def part_p6_student(self) -> None:
        p = self.pdf
        p.add_page()
        self._section_bar("فرایند ۶ — فاز ج: دانشجو (پیشرفت ساعات)")
        self._body("حساب: student1", bold=True)
        self._body("مسیر: پورتال دانشجو، تب «پروفایل»", bold=True)
        self._numbered_list([
            "با student1 وارد شوید.",
            "تب «پروفایل» را باز کنید.",
            "کارت «پیشرفت ساعات درمان آموزشی» را پیدا کنید.",
            "نوار پیشرفت (مثلاً «۴۵ از ۲۵۰») را ببینید.",
            "بخش «آخرین جلسات» را بخوانید.",
            "بعد از ثبت «حاضر» توسط درمانگر، ساعات باید بیشتر شده باشد.",
        ])
        self._check_table([
            "کارت پیشرفت ساعات دیده شد",
            "ساعات بعد از ثبت «حاضر» به‌روز شد",
            "لیست آخرین جلسات خطا نداد",
        ])

    def part_p6_site_manager(self) -> None:
        p = self.pdf
        p.add_page()
        self._section_bar("فرایند ۶ — فاز د: مسئول سایت (پیگیری عدم ثبت)")
        self._body(
            "این بخش وقتی معنی دارد که درمانگر به‌موقع ثبت نکرده باشد. "
            "اگر چنین پرونده‌ای ندارید، از مسئول فنی بخواهید یک مورد آماده کند "
            "یا این فاز را «—» بزنید.",
            bold=True,
        )
        self._body("حساب: site_manager1", bold=True)
        self._body("مسیر: پورتال مسئول سایت، تب «پیگیری‌ها» یا «هشدارها»", bold=True)
        self._numbered_list([
            "با site_manager1 وارد شوید.",
            "پورتال مسئول سایت را باز کنید.",
            "پروندهٔ «تکمیل ساعات درمان آموزشی» را از لیست انتخاب کنید.",
            "کارت راهنمای فرایند ۶ را ببینید — باید بگوید «پیگیری مسئول سایت».",
            "بنر زرد یا قرمز «مهلت پیگیری (۲ روز)» را بخوانید.",
            "متن قرمز «پیگیری عدم ثبت حضور و غیاب» را ببینید.",
            "پس از تماس با درمانگر، دکمه «مسئول سایت پیگیری کرد» را بزنید.",
            "پیام موفقیت بیاید و وضعیت عوض شود.",
        ])
        self._ok_box("پس از پیگیری، پرونده به مرحلهٔ ثبت درمانگر برمی‌گردد.")
        self._check_table([
            "کارت راهنمای فرایند ۶ دیده شد",
            "بنر مهلت ۲ روزه نمایش داده شد",
            "دکمه «مسئول سایت پیگیری کرد» کار کرد (در صورت وجود پرونده)",
        ])

    def part_p15_intro(self) -> None:
        p = self.pdf
        p.add_page()
        self._section_bar("فرایند ۱۵ — آشنایی با مسیر")
        self._body(
            "فرایند ۱۵ معمولاً خودکار از فرایند ۶ شروع می‌شود "
            "وقتی دانشجو دو جلسهٔ پشت‌سرهم بدون اطلاع غایب باشد. "
            "اپراتور مستقیماً این فرایند را «شروع» نمی‌کند؛ "
            "باید پروندهٔ آماده در پورتال مسئول سایت یا کمیته ببینید."
        )
        self._body("مراحل کلی:", bold=True)
        self._numbered_list([
            "شناسایی غیبت بدون اطلاع",
            "بررسی مسئول سایت (۳ گزینه)",
            "در برخی مسیرها: انتظار ۳ هفته",
            "بررسی رئیس کمیته درمان (واگذاری)",
            "پیگیری مجری کمیته (۲ گزینه)",
        ])
        self._warn_box(
            "برای تست فرایند ۱۵، از مسئول فنی بخواهید "
            "یک پروندهٔ نمونه در مرحلهٔ «بررسی مسئول سایت» "
            "یا «کمیته درمان» آماده کند."
        )

    def part_p15_site_manager(self) -> None:
        p = self.pdf
        p.add_page()
        self._section_bar("فرایند ۱۵ — فاز ه: مسئول سایت (دو غیبت پیوسته)")
        self._body("حساب: site_manager1", bold=True)
        self._body("مسیر: پورتال مسئول سایت، تب «هشدارها» یا «پیگیری‌ها»", bold=True)
        self._numbered_list([
            "پروندهٔ «واکنش به غیبت بدون اطلاع» را باز کنید.",
            "کارت بنفش/آبی با عنوان «فرایند ۱۵ — No-Show» را ببینید.",
            "نوار مراحل باید «مسئول سایت» را فعال نشان دهد.",
            "سه کارت گزینه را بخوانید:",
            "  • گزینه ۱: قصد غیبت معین — ثبت تخلف",
            "  • گزینه ۲: قطع قطعی درمان — ارجاع به کمیته",
            "  • گزینه ۳: وضعیت مبهم — تایمر ۳ هفته",
            "در بخش «تصمیم شما» یکی از دکمه‌های مربوط به گزینه‌ها را بزنید.",
            "پیام موفقیت بیاید و وضعیت عوض شود.",
        ])
        self._ok_box(
            "بعد از انتخاب گزینه، پرونده به مرحلهٔ بعد (تخلف، کمیته، یا تایمر) می‌رود "
            "و کارت راهنما متن جدید نشان می‌دهد."
        )
        self._check_table([
            "کارت «فرایند ۱۵» دیده شد",
            "سه گزینه با توضیح فارسی نمایش داده شد",
            "دکمهٔ تصمیم کار کرد",
            "وضعیت پرونده بعد از تصمیم عوض شد",
        ])

    def part_p15_committee(self) -> None:
        p = self.pdf
        p.add_page()
        self._section_bar("فرایند ۱۵ — فاز و: کمیته درمان آموزشی")
        self._body("این فاز دو نقش دارد: رئیس کمیته و مجری کمیته.", bold=True)

        self._body("و — ۱) رئیس کمیته", bold=True)
        self._body("حساب: therapy_committee_chair1", bold=True)
        self._body("مسیر: پورتال کمیته، تب «کارهای من»", bold=True)
        self._numbered_list([
            "پروندهٔ «واکنش به غیبت بدون اطلاع» را در لیست «در انتظار بررسی» ببینید.",
            "پرونده را باز کنید.",
            "کارت فرایند ۱۵ باید بگوید «در انتظار رئیس کمیته درمان».",
            "دکمه «واگذار کردم» را بزنید.",
            "پیام موفقیت بیاید و پرونده به مجری کمیته برود.",
        ])
        self._check_table([
            "پرونده در لیست کارهای رئیس کمیته دیده شد",
            "کارت راهنما متن واگذاری را نشان داد",
            "دکمه «واگذار کردم» کار کرد",
        ])

        p.ln(3)
        self._body("و — ۲) مجری کمیته", bold=True)
        self._body("حساب: therapy_committee_executor1", bold=True)
        self._numbered_list([
            "پرونده را در پورتال کمیته باز کنید.",
            "کارت راهنما باید «پیگیری مجری کمیته» را نشان دهد.",
            "دو گزینه را بخوانید: «قطع درمان قطعی» و «پذیرفته بازگشت».",
            "یکی از دکمه‌های تصمیم را بزنید.",
            "پرونده به مرحلهٔ پایانی (ثبت تخلف) برسد.",
        ])
        self._check_table([
            "دو گزینهٔ مجری با توضیح فارسی دیده شد",
            "دکمهٔ تصمیم کار کرد",
            "پرونده به پایان رسید",
        ])

    def part_p15_ambiguous(self) -> None:
        p = self.pdf
        p.add_page()
        self._section_bar("فرایند ۱۵ — فاز ز: وضعیت مبهم (۳ هفته) — در صورت امکان")
        self._body(
            "اگر مسئول سایت «گزینه ۳ — وضعیت مبهم» را زده باشد، "
            "پرونده وارد تایمر ۳ هفته می‌شود. این فاز را فقط اگر چنین پرونده‌ای دارید تست کنید."
        )
        self._numbered_list([
            "کارت راهنما باید «تایمر ۳ هفته» را نشان دهد.",
            "بنر زرد «مهلت ۳ هفته برای بازگشت» را ببینید.",
            "اگر دانشجو درمان را از سر بگیرد، پرونده خودکار بسته می‌شود.",
            "اگر ۳ هفته بگذرد، پرونده به رئیس کمیته می‌رود.",
        ])
        self._check_table([
            "بنر مهلت ۳ هفته نمایش داده شد",
            "متن راهنما وضعیت مبهم را توضیح داد",
        ])

    def part_quick_demo(self) -> None:
        p = self.pdf
        p.add_page()
        self._section_bar("پیوست — مسیر سریع ۲۰ دقیقه‌ای")
        self._numbered_list([
            "فرایند ۶: therapist1، حضور و غیاب، «حاضر» برای یک جلسه.",
            "فرایند ۶: therapist1، کارهای من، کارت راهنمای فرایند ۶ را ببینید.",
            "فرایند ۶: student1، پروفایل، ساعات به‌روز شده.",
            "فرایند ۶: site_manager1، پیگیری (اگر پروندهٔ عدم ثبت دارید).",
            "فرایند ۱۵: site_manager1، هشدارها، یکی از ۳ گزینه (با پروندهٔ آماده).",
            "فرایند ۱۵: therapy_committee_chair1، واگذاری به مجری.",
            "فرایند ۱۵: therapy_committee_executor1، تصمیم نهایی.",
        ])
        self._tip_box("حداقل برای پذیرش: فازهای الف، ب و ج فرایند ۶ + فاز ه فرایند ۱۵.")

    def part_final(self) -> None:
        p = self.pdf
        p.add_page()
        self._section_bar("جمع‌بندی و تأیید نهایی")
        self._body("تاریخ تست: _______________     اپراتور: _______________", bold=True)
        self._check_table([
            "فرایند ۶ — تب حضور و غیاب درمانگر",
            "فرایند ۶ — کارت راهنما در کارهای من",
            "فرایند ۶ — پیشرفت ساعات دانشجو",
            "فرایند ۶ — پیگیری مسئول سایت",
            "فرایند ۱۵ — تصمیم مسئول سایت (۳ گزینه)",
            "فرایند ۱۵ — رئیس و مجری کمیته",
            "فرایند ۱۵ — تایمر ۳ هفته (در صورت امکان)",
        ])
        p.ln(2)
        self._body("نتیجهٔ کلی:", bold=True)
        self._bullet_list([
            "[ ]  قبول — UI برای استفادهٔ عملیاتی آماده است.",
            "[ ]  قبول مشروط — کار می‌کند ولی متن یا جزئیات نیاز به بهبود دارد.",
            "[ ]  رد — مسئلهٔ جدی وجود دارد.",
        ])
        self._blank_lines("سه مهم‌ترین مشکل یا پیشنهاد:", 4)
        self._blank_lines("امضا اپراتور:", 1)
        p.ln(4)
        self._body(
            "این فایل را پر شده — همراه عکس از صفحه در صورت مشکل — "
            "برای مسئول پروژه بفرستید.",
            bold=True,
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.pdf.output(str(path))


def main() -> int:
    builder = PdfBuilder()
    builder.cover()
    builder.part_overview()
    builder.part_login()
    builder.part_prep()
    builder.part_p6_therapist_tab()
    builder.part_p6_therapist_panel()
    builder.part_p6_student()
    builder.part_p6_site_manager()
    builder.part_p15_intro()
    builder.part_p15_site_manager()
    builder.part_p15_committee()
    builder.part_p15_ambiguous()
    builder.part_quick_demo()
    builder.part_final()
    builder.save(OUT_PDF)
    print(f"PDF written: {OUT_PDF}")
    print(f"Size: {OUT_PDF.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
