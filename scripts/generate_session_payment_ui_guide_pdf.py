#!/usr/bin/env python3
"""
راهنمای آزمایش UI فرایند ۵ — پرداخت برای جلسات آتی درمان آموزشی (session_payment).

اجرا از ریشهٔ ریپو:
  python scripts/generate_session_payment_ui_guide_pdf.py

خروجی:
  docs/راهنمای_تست_فرایند_۵_پرداخت_جلسات_درمان.pdf
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
OUT_PDF = ROOT / "docs" / "راهنمای_تست_فرایند_۵_پرداخت_جلسات_درمان.pdf"

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
                f"راهنمای تست فرایند ۵ — پرداخت جلسات درمان — {self._footer_ts} — صفحه {self.page_no()}"
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


STAGES = [
    {
        "name": "مبلغ قابل پرداخت",
        "student_sees": (
            "در کارت «مسیر فعلی» یا تب «فرایندها»، بلوک «وضعیت مالی جلسات درمان» "
            "و دکمهٔ «ادامه به انتخاب جلسات و تسویه»."
        ),
        "student_does": "روی دکمهٔ «ادامه به انتخاب جلسات و تسویه» بزند.",
        "operator_checks": [
            "تعداد «جلسات بدون پرداخت» درست نمایش داده می‌شود.",
            "متن راهنما فارسی و قابل فهم است.",
            "دکمهٔ ادامه کار می‌کند و مرحله عوض می‌شود.",
        ],
    },
    {
        "name": "انتخاب جلسات و تسویه بدهی",
        "student_sees": (
            "فرم «تعداد جلسات برای پیش‌پرداخت»، در صورت بدهی گزینهٔ "
            "«تسویه بدهی جلسات قبلی»، و «تخمین مبلغ این پرداخت»."
        ),
        "student_does": (
            "تعداد جلسه (مثلاً ۱ یا ۴) را بنویسد؛ اگر بدهی دارد، "
            "گزینهٔ تسویه را فعال کند؛ فرم را ثبت کند؛ "
            "سپس «رفتن به درگاه پرداخت» را بزند."
        ),
        "operator_checks": [
            "اگر بدهی وجود دارد و تسویه فعال نیست، هشدار زرد دیده می‌شود.",
            "با فعال کردن تسویه، تخمین مبلغ به‌روز می‌شود.",
            "بدون پر کردن فرم، دکمهٔ ادامه ظاهر نمی‌شود یا پیام می‌دهد.",
        ],
    },
    {
        "name": "در انتظار پرداخت (درگاه)",
        "student_sees": (
            "مبلغ فاکتور (ریال و تومان) در بلوک مالی و بخش «پرداخت آنلاین» "
            "با دکمهٔ ورود به درگاه."
        ),
        "student_does": (
            "دکمهٔ پرداخت را بزند؛ در محیط آزمایشی مسیر درگاه را طی کند "
            "یا پس از بازگشت از بانک صفحه را یک‌بار تازه (F5) کند."
        ),
        "operator_checks": [
            "مبلغ فاکتور با انتخاب قبلی هم‌خوان است.",
            "پس از پرداخت موفق، وضعیت به «پرداخت تأیید شد» می‌رود.",
            "پیامک تأیید (در صورت فعال بودن) ارسال می‌شود.",
        ],
    },
    {
        "name": "پرداخت تأیید شد",
        "student_sees": (
            "فرایند بسته شده؛ در «مالی درمان آموزشی» جلسات پیش‌رو "
            "وضعیت «پرداخت‌شده» و «آماده برگزاری» (در صورت فعال شدن لینک)."
        ),
        "student_does": "نیازی به اقدام نیست؛ وضعیت را در پروفایل و تب «جلسات آنلاین» ببیند.",
        "operator_checks": [
            "تعداد جلسات بدون پرداخت کم شده یا صفر شده.",
            "لینک جلسهٔ پرداخت‌شده در تب «جلسات آنلاین» قابل مشاهده است.",
            "درمانگر می‌تواند برای همان جلسه حضور ثبت کند.",
        ],
    },
    {
        "name": "پرداخت ناموفق (در صورت تست)",
        "student_sees": "پیام «پرداخت ناموفق» و امکان «تلاش مجدد».",
        "student_does": "دوباره به درگاه برود یا با پشتیبانی تماس بگیرد.",
        "operator_checks": [
            "پس از شکست، فرایند در حالت ناموفق می‌ماند نه «تأیید شده».",
            "دکمهٔ تلاش مجدد کار می‌کند.",
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
        p.set_font("Vazir", "B", 12)
        p.cell(
            0,
            10,
            _fa("فرایند ۵ — پرداخت برای جلسات آتی درمان آموزشی"),
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
                "این کتابچه به شما کمک می‌کند صفحهٔ «پرداخت جلسات درمان» را "
                "در پورتال دانشجو امتحان کنید و مطمئن شوید همهٔ مراحل "
                "درست کار می‌کند. نیازی به دانش فنی ندارید؛ فقط باید "
                "بتوانید وارد سایت شوید، روی دکمه‌ها بزنید و آنچه "
                "می‌بینید را با این راهنما مقایسه کنید."
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
            "قبل از شروع، مسئول فنی باید سامانه را روشن کرده باشد. "
            "اگر صفحه باز نمی‌شود، با او تماس بگیرید."
        )

    def part_what_is_process(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۱ — این فرایند چیست؟")
        self._body(
            "وقتی دانشجو درمان آموزشی را شروع کرده، باید قبل از هر جلسهٔ "
            "بعدی هزینهٔ جلسات پیشِ رو را بپردازد. جلسهٔ اول در «آغاز درمان» "
            "پرداخت می‌شود؛ از جلسهٔ دوم به بعد این فرایند (شمارهٔ ۵) "
            "فعال می‌شود."
        )
        self._body("هدف برای دانشجو:", bold=True)
        self._bullet_list([
            "ببیند چند جلسه بدهکار است و چند جلسه پیش‌پرداخت شده.",
            "تعداد جلسات آینده را انتخاب کند و پرداخت کند.",
            "بعد از پرداخت، لینک جلسه و امکان ثبت حضور برای درمانگر باز شود.",
        ])
        self._body("چه کسی این فرایند را انجام می‌دهد؟", bold=True)
        self._body(
            "عمدتاً خود دانشجو. کارمند یا اپراتور معمولاً فقط برای "
            "آزمایش وارد حساب دانشجو می‌شود یا از پنل مالی وضعیت را "
            "بررسی می‌کند."
        )

    def part_before_start(self) -> None:
        self._section_bar("بخش ۲ — قبل از آزمایش چه چیزهایی باید آماده باشد؟")
        self._numbered_list([
            "دانشجو «آغاز درمان آموزشی» را تکمیل کرده باشد "
            "(درمانگر انتخاب شده، جلسهٔ اول پرداخت شده، درمان فعال است).",
            "حداقل یک جلسهٔ درمان در تقویم ثبت شده باشد "
            "(برای دیدن جدول «جلسات پیشِ رو»).",
            "فرایند «پرداخت جلسات آتی» برای همان دانشجو باز باشد "
            "(خودکار پس از آغاز درمان یا از دکمهٔ «پرداخت جلسات» در داشبورد).",
        ])
        self._tip_box(
            "اگر کارت «پرداخت جلسات» را نمی‌بینید، اول بررسی کنید "
            "آیا «آغاز درمان» کامل شده یا نه."
        )
        self._section_bar("حساب‌های پیشنهادی برای آزمایش")
        self._body(
            "در محیط آزمایشی معمولاً از این حساب‌ها استفاده می‌شود "
            "(رمزها را از مسئول پروژه بگیرید):"
        )
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
            for role, user, pw in [
                ("دانشجو — آزمایش درمان", "student1", "demo123"),
                ("درمانگر آموزشی", "therapist1", "demo123"),
                ("کارمند / پذیرش (در صورت نیاز)", "demo_admissions", "demo123"),
            ]:
                row = table.row()
                row.cell(_fa(role))
                row.cell(user, align=Align.C)
                row.cell(pw, align=Align.C)
        p.ln(4)

    def part_where_ui(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۳ — صفحهٔ پرداخت جلسات کجاست؟")
        self._body(
            "بعد از ورود با حساب دانشجو، این بخش‌ها را ببینید:"
        )
        places = [
            (
                "داشبورد — کارت «مسیر فعلی»",
                "اگر فرایند پرداخت جلسات فعال باشد، بلوک سبز "
                "«وضعیت مالی جلسات درمان»، فرم مرحله و دکمهٔ ادامه "
                "همین‌جا دیده می‌شود."
            ),
            (
                "تب «فرایندها»",
                "از لیست فرایندهای فعال، «پرداخت برای جلسات آتی درمان آموزشی» "
                "را باز کنید. بلوک «مالی درمان آموزشی»، جدول جلسات و "
                "در مرحلهٔ درگاه، دکمهٔ پرداخت اینجاست."
            ),
            (
                "تب «پروفایل»",
                "اگر درمان شروع شده باشد، کارت «مالی درمان آموزشی» "
                "خلاصهٔ بدهی، پیش‌پرداخت و جلسات آینده را نشان می‌دهد "
                "(حتی وقتی روی کارت مسیر کار نمی‌کنید)."
            ),
            (
                "دکمهٔ سریع «پرداخت جلسات»",
                "در داشبورد، میان «درخواست‌های سریع»، گزینهٔ "
                "«پرداخت جلسات» (آیکن کارت) برای شروع فرایند (در صورت مجاز بودن)."
            ),
            (
                "تب «جلسات آنلاین»",
                "بعد از پرداخت موفق، لینk ورود به جلسه باید "
                "برای جلسات پرداخت‌شده دیده شود."
            ),
        ]
        for title, desc in places:
            self._body(title, bold=True)
            self._body(desc)

    def part_operator_scenario(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۴ — سناریوی کامل آزمایش (قدم‌به‌قدم برای اپراتور)")
        self._numbered_list([
            "با حساب student1 (یا دانشجویی که درمان فعال دارد) وارد شوید.",
            "به داشبورد بروید. اگر بنر «مرحله بعد پس از آغاز درمان» دیدید، "
            "یعنی مسیر پرداخت جلسات برای شما باز است.",
            "بلوک «وضعیت مالی جلسات درمان» را بخوانید: "
            "تعداد بدهی، جلسات پرداخت‌شده، تعرفه هر جلسه.",
            "دکمهٔ «ادامه به انتخاب جلسات و تسویه» را بزنید.",
            "در فرم، تعداد جلسه (مثلاً ۲) بنویسید. "
            "اگر بدهی دارید، گزینهٔ تسویه را هم فعال کنید.",
            "فرم را ثبت کنید؛ «تخمین مبلغ» را با انتخاب خود مقایسه کنید.",
            "دکمهٔ «رفتن به درگاه پرداخت» را بزنید.",
            "در مرحلهٔ درگاه، مبلغ فاکتور را ببینید و پرداخت آزمایشی را انجام دهید.",
            "پس از بازگشت از بانک، صفحه را یک‌بار تازه کنید (F5).",
            "بررسی کنید وضعیت «پرداخت تأیید شد» شده باشد.",
            "به تب «پروفایل» بروید — کارت مالی باید به‌روز باشد.",
            "به تب «جلسات آنلاین» بروید — جلسهٔ پرداخت‌شده "
            "باید «آماده برگزاری» یا لینk داشته باشد.",
            "خارج شوید. با therapist1 وارد شوید و ببینید "
            "آیا برای همان جلسه می‌تواند حضور ثبت کند.",
        ])
        self._ok_box(
            "اگر همهٔ مراحل بالا بدون خطای قرمز و بدون توقف بیش از چند دقیقه "
            "انجام شد، پیاده‌سازی UI این فرایند برای استفادهٔ عادی قابل قبول است."
        )

    def part_stages_detail(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۵ — جزئیات هر مرحله (چه ببینید / چه بررسی کنید)")
        for st in STAGES:
            self._ensure_space(45)
            self._body(f"مرحله: {st['name']}", bold=True)
            self._body("دانشجو چه می‌بیند:", bold=True)
            self._body(st["student_sees"])
            self._body("دانشجو چه کار می‌کند:", bold=True)
            self._body(st["student_does"])
            self._body("اپراتور چه را بررسی می‌کند:", bold=True)
            self._bullet_list(st["operator_checks"])
            p = self.pdf
            p.ln(2)

    def part_debt_rule(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۶ — قانون مهم: بدهی جلسهٔ قبلی")
        self._body(
            "اگر دانشجو برای جلسه‌ای که گذشته هنوز پرداخت نکرده، "
            "نمی‌تواند فقط جلسات آینده را بپردازد. باید در همان "
            "پرداخت، گزینهٔ «تسویه بدهی» را هم فعال کند."
        )
        self._numbered_list([
            "آزمایش بدون بدهی: تعداد جلسه را انتخاب کنید، تسویه خاموش — باید جلو برود.",
            "آزمایش با بدهی (اگر در پرونده هست): بدون تسویه نباید بتوان "
            "فقط جلسات آینده را پرداخت کرد؛ هشدار زرد باید دیده شود.",
            "با فعال کردن تسویه، تخمین مبلغ باید شامل بدهی هم باشد.",
        ])
        self._tip_box(
            "اگر در محیط آزمایشی بدهی ندارید، از مسئول فنی بخواهید "
            "یک جلسهٔ بدون پرداخت در پروندهٔ نمونه بگذارد تا این قانون "
            "هم امتحان شود."
        )

    def part_normal_vs_bug(self) -> None:
        self._section_bar("بخش ۷ — چه چیز «طبیعی» است و باگ نیست")
        self._bullet_list([
            "پرداخت در محیط آزمایشی واقعی نیست — فقط مسیر درگاه طی می‌شود.",
            "گاهی لینk جلسه چند ثانیه بعد از پرداخت آماده می‌شود — یک‌بار صفحه را تازه کنید.",
            "اگر جلسه‌ای در تقویم نیست، جدول «جلسات پیشِ رو» خالی است — "
            "اول باید برنامهٔ درمان تنظیم شده باشد.",
            "پیامک ممکن است در آزمایش به موبایل واقعی نرسد — "
            "فقط ثبت در «تاریخچه پیامک» در همان کارت را ببینید.",
            "فرم و دکمهٔ ادامه گاهی در یک «کارت رنگی» است، نه صفحهٔ جدا.",
        ])
        self._section_bar("بخش ۸ — اگر مشکلی دیدید چه بنویسید؟")
        self._numbered_list([
            "در کدام مرحله بودید (مثلاً «انتخاب جلسات — تخمین مبلغ»).",
            "با چه حسابی وارد بودید.",
            "چه انتظار داشتید و چه دیدید.",
            "عکس از صفحه بگیرید (Win+Shift+S در ویندوز).",
        ])

    def part_checklist(self) -> None:
        self.pdf.add_page()
        self._section_bar("بخش ۹ — چک‌لیست نهایی اپراتور")
        checks = [
            "بلوک «مالی درمان آموزشی» در داشبورد / فرایندها / پروفایل دیده می‌شود",
            "تعداد جلسات بدون پرداخت و پرداخت‌شده درست است",
            "جدول «جلسات پیشِ رو» تاریخ و وضعیت را نشان می‌دهد",
            "دکمه «ادامه به انتخاب جلسات و تسویه» کار می‌کند",
            "فرم تعداد جلسه و تسویه بدهی نمایش داده می‌شود",
            "تخمین مبلغ با انتخاب هم‌خوان است",
            "هشدار بدهی (در صورت وجود) دیده می‌شود",
            "مبلغ فاکتور در مرحله درگاه نمایش داده می‌شود",
            "پرداخت آزمایشی موفق — وضعیت «تأیید شد»",
            "پس از پرداخت، جلسات در تب «جلسات آنلاین» به‌روز می‌شوند",
            "درمانگر می‌تواند حضور ثبت کند (در صورت تست)",
            "متن‌ها فارسی و قابل فهم هستند",
            "هیچ پیام خطای نامفهوم یا توقف طولانی نبود",
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
    builder.part_stages_detail()
    builder.part_debt_rule()
    builder.part_normal_vs_bug()
    builder.part_checklist()
    builder.summary()
    builder.save(OUT_PDF)
    print(f"PDF written: {OUT_PDF}")
    print(f"Size: {OUT_PDF.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
