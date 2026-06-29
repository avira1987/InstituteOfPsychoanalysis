#!/usr/bin/env python3
"""
راهنمای PDF اپراتور — فرایند ۷: تعیین تکلیف هزینه جلسه درمان آموزشی
(بدون جزئیات فنی؛ مناسب تست و پذیرش UI)

اجرا از ریشهٔ ریپو:
  python scripts/generate_fee_determination_operator_guide_pdf.py

خروجی:
  docs/راهنمای_تست_فرایند_۷_تعیین_تکلیف_هزینه_جلسات.pdf
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
OUT_PDF = ROOT / "docs" / "راهنمای_تست_فرایند_۷_تعیین_تکلیف_هزینه_جلسات.pdf"

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
                f"راهنمای تست فرایند ۷ — تعیین تکلیف هزینه جلسات — {self._footer_ts} — ص {self.page_no()}"
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


SCENARIOS = [
    {
        "name": "سناریو ۱ — بازگشت اعتبار",
        "when": (
            "دانشجو برای آن جلسه پرداخت کرده بود و هنوز در سهمیهٔ سالانه "
            "غیبت/کنسلی مجاز باقی مانده است."
        ),
        "student_sees": (
            "در «سوابق تعیین تکلیف» یک ردیف سبز با عنوان «بازگشت اعتبار» "
            "و متنی شبیه «یک جلسه به بستانکاری شما اضافه شد»."
        ),
        "operator_checks": [
            "شمارنده «بازگشت اعتبار» یک واحد زیاد شده.",
            "شمارنده «مصرف‌شده» از سهمیه یک واحد زیاد شده.",
            "«باقی‌مانده» سهمیه یک واحد کم شده.",
            "در کارت «مالی درمان» (فرایند ۵) موجودی اعتبار جلسه افزایش یافته.",
        ],
    },
    {
        "name": "سناریو ۲ — بدون اقدام مالی",
        "when": (
            "دانشجو برای آن جلسه پرداخت نکرده بود و هنوز در سهمیهٔ مجاز است."
        ),
        "student_sees": (
            "ردیف خاکستری با عنوان «بدون اقدام مالی» و توضیح "
            "«در محدوده سهمیه سالانه بدون اقدام مالی ثبت شد»."
        ),
        "operator_checks": [
            "بدهی یا اعتبار جدیدی ایجاد نشده.",
            "فقط شمارنده «مصرف‌شده» یک واحد زیاد شده.",
            "متن فارسی واضح و بدون اصطلاح فنی است.",
        ],
    },
    {
        "name": "سناریو ۳ — مصادره هزینه",
        "when": (
            "دانشجو برای آن جلسه پرداخت کرده بود اما سهمیهٔ سالانه "
            "تمام شده بود."
        ),
        "student_sees": (
            "ردیف قرمز با عنوان «مصادره هزینه» و هشدار زرد "
            "«سهمیهٔ غیبت سالانه به پایان رسیده» در بالای کارت."
        ),
        "operator_checks": [
            "شمارنده «مصادره» یک واحد زیاد شده.",
            "پول جلسه برگشت داده نشده (اعتبار اضافه نشده).",
            "هشدار اتمام سهمیه نمایش داده می‌شود.",
        ],
    },
    {
        "name": "سناریو ۴ — ایجاد بدهی",
        "when": (
            "دانشجو برای آن جلسه پرداخت نکرده بود و سهمیهٔ سالانه "
            "تمام شده بود."
        ),
        "student_sees": (
            "ردیف نارنجی با عنوان «ایجاد بدهی» و متن راهنما "
            "«بدهی یا تسویه از بستانکاری ثبت شد — از فرایند پرداخت جلسات پیگیری کنید»."
        ),
        "operator_checks": [
            "شمارنده «بدهی ایجادشده» یک واحد زیاد شده.",
            "در کارت «مالی درمان» (فرایند ۵) بدهی جلسه دیده می‌شود.",
            "دانشجو می‌تواند از «پرداخت جلسات» بدهی را تسویه کند.",
        ],
    },
    {
        "name": "خارج از شمول (وقفه یا لغو توسط درمانگر)",
        "when": (
            "دانشجو در وقفهٔ درمان است، یا جلسه را درمانگر/سوپروایزر "
            "لغو کرده — نه دانشجو."
        ),
        "student_sees": (
            "ردیف آبی با عنوان «خارج از شمول» و توضیح "
            "«این مورد خارج از شمول مالی بود»."
        ),
        "operator_checks": [
            "هیچ تغییر مالی (بدهی/اعتبار/مصادره) برای این مورد ثبت نشده.",
            "شمارنده سهمیه لزوماً تغییر نکرده (بسته به نوع مورد).",
        ],
    },
]


ACCOUNTS = [
    ("دانشجو (درمان شروع شده)", "student1", "demo123"),
    ("درمانگر آموزشی", "therapist1", "demo123"),
    ("کارمند / پذیرش (در صورت نیاز)", "demo_admissions", "demo123"),
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
            _fa("فرایند ۷ — تعیین تکلیف هزینه جلسه درمان آموزشی"),
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
                "این کتابچه به شما کمک می‌کند صفحهٔ «تعیین تکلیف هزینه جلسات» "
                "در پورتال دانشجو را امتحان کنید و مطمئن شوید پس از غیبت یا "
                "کنسل جلسه، نتیجهٔ مالی درست نمایش داده می‌شود. "
                "نیازی به دانش فنی ندارید؛ فقط باید بتوانید وارد سایت شوید، "
                "روی دکمه‌ها بزنید و آنچه می‌بینید را با این راهنما مقایسه کنید."
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
            "این فرایند خودکار است — دانشجو دکمهٔ «شروع» ندارد. "
            "شما با ثبت غیبت (درمانگر) یا کنسل جلسه (دانشجو) آن را فعال می‌کنید "
            "و سپس نتیجه را در کارت مربوط می‌بینید."
        )

    def part_what_is_process(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۱ — این فرایند چیست؟")
        self._body(
            "وقتی دانشجو در یک جلسهٔ درمان غیبت می‌کند (یا خودش جلسه را "
            "کنسل می‌کند)، سامانه باید تصمیم بگیرد پول آن جلسه چه می‌شود: "
            "برگردد؟ مصادره شود؟ بدهی ثبت شود؟ یا اصلاً کاری نشود؟ "
            "این کار در «فرایند ۷» انجام می‌شود."
        )
        self._body("قانون سهمیه (به زبان ساده):", bold=True)
        self._body(
            "هر سال، دانشجو حق دارد به تعداد مشخصی غیبت یا کنسل «رایگان» "
            "داشته باشد. این تعداد = ۳ برابر تعداد جلسات هفتگی اوست. "
            "مثال: اگر هفته‌ای ۲ جلسه دارد، سهمیهٔ سال = ۶ مورد."
        )
        self._body("چهار نتیجهٔ ممکن:", bold=True)
        self._bullet_list([
            "پرداخت کرده + در سهمیه → یک جلسه به اعتبارش برمی‌گردد (بازگشت اعتبار).",
            "پرداخت نکرده + در سهمیه → فقط از سهمیه کم می‌شود، بدهی جدید نیست.",
            "پرداخت کرده + خارج سهمیه → پول جلسه سوخت می‌شود (مصادره).",
            "پرداخت نکرده + خارج سهمیه → بدهی ثبت می‌شود (ایجاد بدهی).",
        ])
        self._body("چه کسی این فرایند را «انجام» می‌دهد؟", bold=True)
        self._body(
            "سامانه خودکار — بدون دخالت دانشجو. دانشجو فقط نتیجه را "
            "در کارت «تعیین تکلیف هزینه جلسات» می‌بیند. "
            "اپراتور برای آزمایش: غیبت ثبت می‌کند یا جلسه کنسل می‌کند، "
            "سپس کارت را بررسی می‌کند."
        )

    def part_before_start(self) -> None:
        self._section_bar("بخش ۲ — قبل از آزمایش چه چیزهایی باید آماده باشد؟")
        self._numbered_list([
            "دانشجو «آغاز درمان آموزشی» را تکمیل کرده باشد (درمان فعال است).",
            "حداقل یک جلسهٔ درمان در تقویم ثبت شده باشد.",
            "برای آزمایش «بازگشت اعتبار» یا «مصادره»، آن جلسه باید "
            "قبلاً پرداخت شده باشد (فرایند ۵).",
            "برای آزمایش «ایجاد بدهی»، جلسهٔ بدون پرداخت و سهمیهٔ "
            "تمام‌شده لازم است (از مسئول فنی بخواهید پروندهٔ نمونه آماده کند).",
        ])
        self._tip_box(
            "اگر کارت «تعیین تکلیف هزینه جلسات» را نمی‌بینید، "
            "اول بررسی کنید «آغاز درمان» کامل شده باشد."
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
        self._section_bar("بخش ۳ — صفحهٔ تعیین تکلیف کجاست؟")
        self._body("بعد از ورود با حساب دانشجو، این بخش‌ها را ببینید:")
        places = [
            (
                "تب «پروفایل»",
                "کارت «تعیین تکلیف هزینه جلسات (فرایند ۷)» — "
                "سهمیه سالانه، مصرف‌شده، باقی‌مانده، شمارش هر سناریو "
                "و جدول «سوابق تعیین تکلیف»."
            ),
            (
                "تب «فرایندها» — هنگام باز کردن فرایند ۶ (حضور و غیاب)",
                "همان کارت به‌صورت فشرده در بالای صفحهٔ فرایند دیده می‌شود "
                "تا دانشجو بفهمد غیبت چه اثر مالی داشته."
            ),
            (
                "تب «فرایندها» — هنگام باز کردن فرایند ۱۷ (کنسل جلسه توسط دانشجو)",
                "همان کارت فشرده برای دیدن نتیجهٔ مالی کنسل."
            ),
            (
                "کارت «مالی درمان آموزشی» (فرایند ۵)",
                "برای بررسی اعتبار یا بدهی پس از تعیین تکلیف — "
                "باید با کارت فرایند ۷ هم‌خوان باشد."
            ),
        ]
        for title, desc in places:
            self._body(title, bold=True)
            self._body(desc)
        self._body("عناصر مهم داخل کارت:", bold=True)
        self._bullet_list([
            "سهمیهٔ سالانه — عدد کل مجاز در سال جاری.",
            "مصرف‌شده — چند غیبت/کنسل تا الان ثبت شده.",
            "باقی‌مانده — چند مورد دیگر «رایگان» باقی مانده.",
            "جلسات در هفته — برای فهمیدن چرا سهمیه این عدد است.",
            "بازگشت اعتبار / مصادره / بدهی ایجادشده — شمارش هر نوع نتیجه.",
            "سوابق تعیین تکلیف — لیست رنگی هر مورد با تاریخ و توضیح فارسی.",
            "دکمه «بروزرسانی» — برای تازه کردن اطلاعات پس از ثبت غیبت.",
        ])

    def part_operator_scenario(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۴ — سناریوی اصلی آزمایش (قدم‌به‌قدم)")
        self._numbered_list([
            "با حساب student1 (یا دانشجویی که درمان فعال دارد) وارد شوید.",
            "به تب «پروفایل» بروید. کارت «تعیین تکلیف هزینه جلسات» را پیدا کنید.",
            "اعداد «سهمیه»، «مصرف‌شده» و «باقی‌مانده» را یادداشت کنید.",
            "خارج شوید. با therapist1 (درمانگر) وارد شوید.",
            "در پنل درمانگر، جلسهٔ امروز یا گذشتهٔ دانشجو را باز کنید.",
            "برای آن جلسه «غیبت غیرموجه» ثبت کنید (فرایند ۶).",
            "دوباره با student1 وارد شوید. تب «پروفایل» → دکمه «بروزرسانی».",
            "بررسی کنید: «مصرف‌شده» یک واحد زیاد شده؛ "
            "در «سوابق» یک ردیف جدید با توضیح فارسی دیده می‌شود.",
            "نوع نتیجه (سبز/خاکستری/قرمز/نارنجی) را با وضعیت پرداخت "
            "و باقی‌مانده سهمیه مقایسه کنید (جدول بخش ۵).",
            "در صورت «بازگشت اعتبار»، کارت «مالی درمان» را هم ببینید — "
            "اعتبار باید زیاد شده باشد.",
            "در صورت «ایجاد بدهی»، کارت «مالی درمان» — بدهی باید دیده شود.",
        ])
        self._ok_box(
            "اگر پس از ثبت غیبت، کارت به‌روز شد و توضیح فارسی درست "
            "و با انتظار شما هم‌خوان بود، UI این فرایند برای استفادهٔ "
            "عادی قابل قبول است."
        )

    def part_cancel_scenario(self) -> None:
        self._section_bar("بخش ۵ — آزمایش از مسیر «کنسل جلسه توسط دانشجو»")
        self._numbered_list([
            "با student1 وارد شوید.",
            "از «درخواست‌های سریع» یا فرایند ۱۷، جلسهٔ آینده را کنسل کنید.",
            "به تب «فرایندها» بروید و همان فرایند کنسل را باز کنید.",
            "کارت فشرده «تعیین تکلیف هزینه» را در بالای صفحه ببینید.",
            "دکمه «بروزرسانی» بزنید — ردیف جدید در سوابق باید ظاهر شود.",
            "نتیجه را با قوانین سهمیه (بخش ۱) مقایسه کنید.",
        ])
        self._warn_box(
            "کنسل جلسهٔ پشت‌سرهم بیش از ۳ هفته یا بیش از ۱۲٪ جلسات "
            "ممکن است فرایندهای دیگر (تخلف) را هم فعال کند — "
            "در آزمایش اول فقط یک کنسل ساده انجام دهید."
        )

    def part_scenarios_detail(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۶ — جزئیات هر سناریو (چه ببینید / چه بررسی کنید)")
        for sc in SCENARIOS:
            self._ensure_space(50)
            self._body(sc["name"], bold=True)
            self._body("چه موقع رخ می‌دهد:", bold=True)
            self._body(sc["when"])
            self._body("دانشجو چه می‌بیند:", bold=True)
            self._body(sc["student_sees"])
            self._body("اپراتور چه را بررسی می‌کند:", bold=True)
            self._bullet_list(sc["operator_checks"])
            self.pdf.ln(2)

    def part_quota_table(self) -> None:
        self._section_bar("بخش ۷ — جدول تصمیم (برای مقایسه با صفحه)")
        self._body(
            "بعد از هر غیبت یا کنسل، ردیف سوابق باید با یکی از این "
            "حالت‌ها هم‌خوان باشد:"
        )
        p = self.pdf
        with p.table(
            col_widths=(28, 28, 28, 96),
            width=p.epw,
            text_align=Align.R,
            line_height=5.5,
            borders_layout=TableBordersLayout.ALL,
            cell_fill_color=_COLOR_STRIPE,
            cell_fill_mode=TableCellFillMode.ROWS,
            padding=1.5,
        ) as table:
            hr = table.row()
            for h in [_fa("پرداخت؟"), _fa("در سهمیه؟"), _fa("نتیجه"), _fa("رنگ تقریبی در صفحه")]:
                hr.cell(h, align=Align.C, style=_heading_style())
            for paid, quota, result, color in [
                ("بله", "بله", "بازگشت اعتبار", "سبز"),
                ("خیر", "بله", "بدون اقدام مالی", "خاکستری"),
                ("بله", "خیر", "مصادره هزینه", "قرمز"),
                ("خیر", "خیر", "ایجاد بدهی", "نارنجی"),
            ]:
                row = table.row()
                row.cell(_fa(paid), align=Align.C)
                row.cell(_fa(quota), align=Align.C)
                row.cell(_fa(result))
                row.cell(_fa(color), align=Align.C)
        p.ln(4)
        self._tip_box(
            "اگر «باقی‌مانده» صفر است، هشدار قرمز «سهمیه به پایان رسید» "
            "باید در بالای کارت دیده شود."
        )

    def part_normal_vs_bug(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۸ — چه چیز «طبیعی» است و باگ نیست")
        self._bullet_list([
            "دانشجو دکمهٔ «شروع فرایند ۷» ندارد — همه‌چیز خودکار است.",
            "گاهی چند ثانیه بعد از ثبت غیبت، ردیف جدید در سوابق ظاهر می‌شود — "
            "یک‌بار «بروزرسانی» بزنید.",
            "اگر هنوز غیبتی ثبت نشده، سوابق خالی است — "
            "پیام «هنوز موردی ثبت نشده» طبیعی است.",
            "سهمیه با شروع سال شمسی صفر می‌شود — در آزمایش به سال جاری توجه کنید.",
            "اگر درمانگر جلسه را لغو کرده، ممکن است «خارج از شمول» ببینید — "
            "این درست است، نه خطا.",
            "فرایند ۷ در لیست «مسیر فعلی» دانشجو معمولاً دیده نمی‌شود — "
            "فقط کارت پروفایل/فرایندهای مرتبط.",
        ])
        self._section_bar("بخش ۹ — اگر مشکلی دیدید چه بنویسید؟")
        self._numbered_list([
            "قبل و بعد از غیبت/کنسل، اعداد سهمیه را یادداشت کنید.",
            "آیا جلسه پرداخت شده بود یا نه.",
            "چه رنگ/عنوانی در سوابق دیدید و چه انتظار داشتید.",
            "با چه حسابی (دانشجو/درمانگر) کار کردید.",
            "عکس از کارت «تعیین تکلیف» و در صورت نیاز کارت «مالی درمان» بگیرید.",
        ])

    def part_checklist(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۱۰ — چک‌لیست نهایی اپراتور")
        checks = [
            "کارت «تعیین تکلیف هزینه جلسات» در تب پروفایل دیده می‌شود",
            "سهمیه سالانه، مصرف‌شده و باقی‌مانده عدد درست دارند",
            "توضیح «۳ × جلسات هفتگی» در بالای کارت قابل فهم است",
            "پس از ثبت غیبت توسط درمانگر، «مصرف‌شده» به‌روز می‌شود",
            "ردیف جدید در «سوابق تعیین تکلیف» با تاریخ و متن فارسی ظاهر می‌شود",
            "رنگ و عنوان ردیف با جدول بخش ۷ هم‌خوان است",
            "در صورت اتمام سهمیه، هشدار قرمز نمایش داده می‌شود",
            "شمارنده «بازگشت اعتبار / مصادره / بدهی» درست است",
            "کارت «مالی درمان» با نتیجه (اعتبار/بدهی) هم‌خوان است",
            "پس از کنسل جلسه (فرایند ۱۷)، کارت فشرده در صفحه فرایند دیده می‌شود",
            "دکمه «بروزرسانی» کار می‌کند",
            "متن‌ها فارسی و بدون اصطلاح فنی گیج‌کننده هستند",
            "هیچ پیام خطای نامفهوم یا صفحهٔ سفید نبود",
        ]
        self._check_table(checks)
        self._blank_lines("مشکلات مهم (شماره ۱، ۲، ۳):", 3)
        self._blank_lines("پیشنهاد برای بهتر شدن:", 2)
        self._body("امتیاز کلی (۱ = ضعیف — ۵ = عالی):  [ ] ۱  [ ] ۲  [ ] ۳  [ ] ۴  [ ] ۵")

    def summary(self) -> None:
        self.pdf.add_page()
        self._section_bar("پایان — ارسال گزارش")
        self._body(
            "این PDF را پر کنید و همراه عکس‌های صفحه برای مدیر پروژه "
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
    builder.part_operator_scenario()
    builder.part_cancel_scenario()
    builder.part_scenarios_detail()
    builder.part_quota_table()
    builder.part_normal_vs_bug()
    builder.part_checklist()
    builder.summary()
    builder.save(OUT_PDF)
    print(f"PDF written: {OUT_PDF}")
    print(f"Size: {OUT_PDF.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
