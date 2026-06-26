#!/usr/bin/env python3
"""
تولید PDF راهنمای تست پذیرش UI برای کاربر غیرفنی + چک‌لیست بازخورد.

اجرا از ریشهٔ ریپو:
  python scripts/generate_ui_tester_guide_pdf.py

خروجی:
  docs/راهنمای_تست_پذیرش_UI_برای_کاربر.pdf
"""
from __future__ import annotations

import os
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
OUT_PDF = ROOT / "docs" / "راهنمای_تست_پذیرش_UI_برای_کاربر.pdf"

_MARGIN = 14
_BODY = 9
_SECTION = 11
_TITLE = 14
_SMALL = 8

_COLOR_SECTION_BG = (243, 244, 246)
_COLOR_SECTION_TEXT = (55, 65, 81)
_COLOR_BORDER = (209, 213, 219)
_COLOR_STRIPE = (249, 250, 251)


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
        self.set_font("Vazir", "", 7)
        self.set_text_color(120, 120, 120)
        self.cell(0, 5, _fa(f"راهنمای تست UI — {self._footer_ts} — صفحه {self.page_no()}"), align="C")


PHASES: list[dict] = [
    {
        "num": 1,
        "title": "آماده‌سازی ترم پاییز",
        "what": "قبل از ثبت‌نام دانشجویان، تقویم، شهریه، دروس و وقت مصاحبه آماده می‌شود.",
        "accounts": "admin یا deputy_education1؛ برای اسلات: site_manager1",
        "where": "/panel/semester-prep و workbench پاییز",
        "steps": [
            "شروع فرایند پاییز در صورت نیاز",
            "پر کردن فرم‌های workbench تا مرحله انتشار",
            "با site_manager1 زمان‌بندی اسلات مصاحبه",
        ],
        "expect": "وضعیت انتشار؛ تقویم در پورتال دانشجو؛ بدون آن ثبت‌نام قفل است",
        "checks": [
            "توانستم مرحله را در workbench انجام دهم",
            "به مرحله انتشار رسیدم یا دیدم",
            "متن یا دکمه گیج‌کننده بود",
        ],
    },
    {
        "num": 2,
        "title": "ثبت‌نام دوره آشنایی",
        "what": "متقاضی مصاحبه، مدارک، انتخاب درس و پرداخت شهریه.",
        "accounts": "دانشجو؛ demo_interviewer؛ demo_admissions",
        "where": "/panel/portal/student؛ /panel/portal/interviewer؛ staff/admissions",
        "steps": [
            "فرم پذیرش و انتخاب وقت مصاحبه + پرداخت",
            "مصاحبه‌گر: ثبت برگزاری و نتیجه",
            "پذیرش: تأیید مدارک",
            "دانشجو: مدارک، درس، پرداخت شهریه",
        ],
        "expect": "ثبت‌نام نهایی بدون گیر غیرمنطقی",
        "checks": [
            "مسیر ثبت‌نام را طی کردم",
            "مصاحبه‌گر نتیجه ثبت کرد",
            "پذیرش مدارک را تأیید کرد",
            "متن یا دکمه گیج‌کننده بود",
        ],
    },
    {
        "num": 3,
        "title": "ترم آشنایی — کلاس و کارنامه",
        "what": "حضور و نمره توسط مدرس؛ کارنامه پایان ترم برای دانشجو.",
        "accounts": "student1؛ staff/instruction",
        "where": "پروفایل دانشجو؛ پنل مدرس",
        "steps": [
            "وضعیت دروس و غیبت در پروفایل",
            "مدرس: حضور یا نمره در صندوق",
            "مشاهده کارنامه در بخش کارنامه‌ها",
        ],
        "expect": "جدول دروس؛ کارنامه متنی قابل مشاهده",
        "checks": [
            "وضعیت دروس را دیدم",
            "کارنامه را دیدم",
            "متن یا دکمه گیج‌کننده بود",
        ],
    },
    {
        "num": 4,
        "title": "ترم ۲ و خاتمه دوره آشنایی",
        "what": "ثبت‌نام ترم دوم و گواهی پایان ۱۰ درس.",
        "accounts": "دانشجو؛ supervision_committee1",
        "where": "داشبورد دانشجو؛ committee/supervision",
        "steps": [
            "ثبت‌نام ترم ۲ در صورت نمایش کارت",
            "گواهی در پروفایل — کارنامه‌ها",
        ],
        "expect": "گواهی پایان آشنایی",
        "checks": [
            "گواهی را دیدم",
            "متن یا دکمه گیج‌کننده بود",
        ],
    },
    {
        "num": 5,
        "title": "ثبت‌نام دوره جامع",
        "what": "ورود به جامع پس از آشنایی؛ مصاحبه و کمیته.",
        "accounts": "regdemo_comp_*؛ کمیته نظارت؛ مصاحبه‌گر",
        "where": "همان مسیر ثبت‌نام + committee/supervision",
        "steps": [
            "درخواست و گزارش تجربه",
            "بررسی کمیته و مصاحبه",
            "انتخاب دروس و پرداخت",
        ],
        "expect": "ثبت‌نام جامع کامل",
        "checks": [
            "مسیر جامع را طی کردم",
            "متن یا دکمه گیج‌کننده بود",
        ],
    },
    {
        "num": 6,
        "title": "چرخه ترم جامع و ارزیابی استاد",
        "what": "ثبت‌نام هر ترم؛ فرم ارزیابی مدرس؛ کارنامه.",
        "accounts": "student2",
        "where": "داشبورد و فرایندها — student portal",
        "steps": [
            "ثبت‌نام ترم و پرداخت",
            "فرم ارزیابی ۱ تا ۵ و ارسال",
            "کارنامه در پروفایل",
        ],
        "expect": "ارزیابی ارسال شد؛ کارنامه دیده شد",
        "checks": [
            "فرم ارزیابی را ارسال کردم",
            "کارنامه را دیدم",
            "متن یا دکمه گیج‌کننده بود",
        ],
    },
    {
        "num": 7,
        "title": "درمان آموزشی",
        "what": "شروع درمان، پرداخت جلسات، ساعات.",
        "accounts": "دانشجو؛ therapist1",
        "where": "داشبورد دانشجو؛ /panel/portal/therapist",
        "steps": [
            "آغاز درمان: درمانگر، زمان، پرداخت",
            "پرداخت جلسات آتی",
            "ساعات در پروفایل",
        ],
        "expect": "درمان شروع و پرداخت‌ها قابل انجام",
        "checks": [
            "آغاز درمان و پرداخت",
            "ساعات قابل مشاهده",
            "متن یا دکمه گیج‌کننده بود",
        ],
    },
    {
        "num": 8,
        "title": "سوپرویژن",
        "what": "بلوک سوپرویژن، افزایش جلسه، تأیید سوپروایزر.",
        "accounts": "دانشجو؛ supervisor1",
        "where": "فرایندها؛ /panel/portal/supervisor",
        "steps": [
            "انتقال بلوک و انتخاب سوپروایزر",
            "درخواست افزایش جلسه در صورت وجود",
        ],
        "expect": "مسیر سوپرویژن قابل پیش‌رفت",
        "checks": [
            "اقدام دانشجو انجام شد",
            "متن یا دکمه گیج‌کننده بود",
        ],
    },
    {
        "num": 9,
        "title": "مرخصی (اختیاری)",
        "what": "مرخصی موقت یا کامل؛ تصمیم کمیته پیشرفت.",
        "accounts": "دانشجو؛ progress_committee1",
        "where": "درخواست‌های دیگر؛ committee/progress",
        "steps": ["فرم مرخصی", "جلسه و تصمیم کمیته"],
        "expect": "درخواست ثبت و پاسخ کمیته",
        "checks": ["در صورت تست: مرخصی را امتحان کردم"],
        "optional": True,
    },
    {
        "num": 10,
        "title": "کارورزی",
        "what": "آمادگی انترن، سفته، سوپروایزر کارورزی.",
        "accounts": "دانشجوی انترن؛ کمیته",
        "where": "فرایندها و پروفایل",
        "steps": ["درخواست کارورزی", "وضعیت سفته در پروفایل"],
        "expect": "فرم‌ها و بنر وضعیت",
        "checks": [
            "درخواست کارورزی",
            "متن یا دکمه گیج‌کننده بود",
        ],
    },
    {
        "num": 11,
        "title": "دروس، مقاله، دفاع",
        "what": "نمره دروس؛ درخواست دفاع پایان‌نامه.",
        "accounts": "دانشجو؛ مدرس؛ کمیته‌ها",
        "where": "پروفایل؛ instruction؛ committee",
        "steps": [
            "وضعیت دروس",
            "درخواست دفاع و آپلود",
            "پیگیری کمیته",
        ],
        "expect": "مسیر دفاع قابل شروع",
        "checks": [
            "وضعیت دروس",
            "درخواست دفاع",
            "متن یا دکمه گیج‌کننده بود",
        ],
    },
]

ACCOUNTS = [
    ("مدیر سیستم", "admin", "admin123"),
    ("معاون آموزش", "deputy_education1", "demo123"),
    ("پذیرش", "demo_admissions", "demo123"),
    ("مصاحبه‌گر", "demo_interviewer", "demo123"),
    ("مسئول سایت", "site_manager1", "demo123"),
    ("دانشجو", "student1", "demo123"),
    ("درمانگر", "therapist1", "demo123"),
    ("سوپروایزر", "supervisor1", "demo123"),
]


def _heading_style() -> FontFace:
    return FontFace(
        family="Vazir",
        emphasis="BOLD",
        size_pt=_SMALL,
        color=(55, 65, 81),
        fill_color=(220, 226, 234),
    )


class PdfBuilder:
    def __init__(self) -> None:
        self.pdf = GuidePDF()
        _register_fonts(self.pdf)
        self.pdf.set_margins(_MARGIN, _MARGIN, _MARGIN)
        self.pdf.set_auto_page_break(auto=True, margin=16)
        self.pdf.add_page()

    def _section_bar(self, text: str) -> None:
        p = self.pdf
        p.set_fill_color(*_COLOR_SECTION_BG)
        p.set_text_color(*_COLOR_SECTION_TEXT)
        p.set_font("Vazir", "B", _SECTION)
        p.cell(0, 8, _fa(text), fill=True, align="R", new_x="LMARGIN", new_y="NEXT")
        p.set_text_color(30, 30, 30)
        p.ln(2)

    def _body(self, text: str, bold: bool = False) -> None:
        p = self.pdf
        p.set_font("Vazir", "B" if bold else "", _BODY)
        p.multi_cell(0, 5.5, _fa(text), align="R")
        p.ln(1)

    def _label_value(self, label: str, value: str) -> None:
        self._body(f"{label}: {value}")

    def _blank_lines(self, label: str, n: int = 3) -> None:
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
        p = self.pdf
        hs = _heading_style()
        rows = [[_fa("سؤال"), _fa("بله"), _fa("خیر"), _fa("توضیح")]]
        for q in questions:
            rows.append([_fa(q), "", "", ""])
        with p.table(
            col_widths=(90, 12, 12, 66),
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

    def _priority_line(self) -> None:
        self._body("اولویت:  بالا [ ]   متوسط [ ]   پایین [ ]")

    def cover(self) -> None:
        p = self.pdf
        p.set_font("Vazir", "B", 16)
        p.ln(8)
        p.cell(0, 10, _fa("راهنمای تست پذیرش رابط کاربری"), align="C", new_x="LMARGIN", new_y="NEXT")
        p.set_font("Vazir", "", 11)
        p.cell(0, 8, _fa("انستیتو روانکاوی تهران — برای کاربر آزمایشی"), align="C", new_x="LMARGIN", new_y="NEXT")
        p.ln(6)
        p.set_font("Vazir", "", _BODY)
        for label, blank in [
            ("نام تست‌کننده", "________________________"),
            ("تاریخ", "________________________"),
            ("آدرس لوکال", "http://localhost:3000/login"),
            ("آدرس سرور", "________________________"),
        ]:
            p.cell(0, 7, _fa(f"{label}: {blank}"), align="R", new_x="LMARGIN", new_y="NEXT")
        p.ln(4)

    def intro(self) -> None:
        self._section_bar("ورود و حساب‌های آزمایشی")
        self._body(
            "ورود: تب «ورود با رمز عبور» — سؤال ریاضی — نام کاربری و رمز. "
            "برای تعویض نقش: خروج و ورود مجدد."
        )
        p = self.pdf
        with p.table(
            col_widths=(45, 55, 30),
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
        p.ln(3)
        self._section_bar("آماده‌سازی محیط لوکال (از مدیر فنی)")
        self._body(
            "seed_all_roles؛ seed_semester_prep_demo؛ seed_registration_portal_demo --matrix؛ "
            "سپس uvicorn روی پورت ۳۰۰۰."
        )
        self._section_bar("نکات مهم")
        for note in [
            "LMS بیرونی واقعی وصل نیست.",
            "کارنامه و گواهی به صورت متن نمایش داده می‌شود.",
            "برخی مراحل خودکار هستند — در چک‌لیست بنویسید.",
        ]:
            self._body(f"• {note}")

    def phase(self, ph: dict) -> None:
        opt = " (اختیاری)" if ph.get("optional") else ""
        self.pdf.add_page()
        self._section_bar(f"فاز {ph['num']} — {ph['title']}{opt}")
        self._label_value("این مرحله چیست", ph["what"])
        self._label_value("با چه حسابی", ph["accounts"])
        self._label_value("کجا بروم", ph["where"])
        self._body("چه کار کنم:", bold=True)
        for i, step in enumerate(ph["steps"], 1):
            self._body(f"{i}. {step}")
        self._label_value("باید چه ببینم", ph["expect"])
        self._body("چک‌لیست بازخورد:", bold=True)
        self._check_table(ph["checks"])
        self._blank_lines("باگ منطقی (انتظار / واقعیت):", 2)
        self._blank_lines("کمبود (چه چیزی نبود یا ناقص بود):", 2)
        self._priority_line()

    def summary(self) -> None:
        self.pdf.add_page()
        self._section_bar("جمع‌بندی کلی")
        questions = [
            "مسیر از آماده‌سازی ترم تا دفاع قابل فهم بود؟",
            "بدون کمک فنی پیش رفتم؟",
            "گیج‌کننده‌ترین بخش کدام بود؟",
            "مهم‌ترین باگ شماره ۱",
            "مهم‌ترین باگ شماره ۲",
            "مهم‌ترین باگ شماره ۳",
            "سه پیشنهاد بهبود فوری",
        ]
        for q in questions:
            self._blank_lines(q, 2)
        self._body(
            "فرم دیجیتال: docs/فرم_بازخورد_تست_UI.md — پس از پر کردن برای مدیر پروژه ارسال کنید.",
            bold=True,
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.pdf.output(str(path))


def main() -> int:
    builder = PdfBuilder()
    builder.cover()
    builder.intro()
    for ph in PHASES:
        builder.phase(ph)
    builder.summary()
    builder.save(OUT_PDF)
    print(f"PDF written: {OUT_PDF}")
    print(f"Size: {OUT_PDF.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
