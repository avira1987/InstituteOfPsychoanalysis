#!/usr/bin/env python3
"""
تولید PDF جامع تست همه فرایندها برای اپراتور غیرفنی.

اجرا از ریشهٔ ریپو:
  python scripts/generate_comprehensive_process_operator_test_pdf.py

خروجی:
  docs/راهنمای_جامع_تست_همه_فرایندها.pdf
  docs/فرم_ثبت_کمبود_فرایندها.md
  docs/gap_report_template.csv
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fpdf.enums import Align

from scripts.lib.pdf_fa_utils import (
    BODY,
    MARGIN,
    SMALL,
    TITLE,
    GuidePDF,
    PdfSectionBuilder,
    fa,
    register_fonts,
)
from scripts.lib.process_test_guide_data import (
    DEMO_ACCOUNT_GUIDES,
    DEMO_ACCOUNTS,
    LIFECYCLE_ORDER,
    LINK_TYPE_FA,
    OPERATOR_FAILURE_STEPS,
    OPERATOR_TEST_INTRO,
    ROLE_FA,
    TABLE_ACCOUNT_COLUMN_GUIDE,
    TABLE_STEP_COLUMN_GUIDE,
    CrossProcessLink,
    ProcessTestSpec,
    StateTestSpec,
    build_process_specs,
    collect_cross_process_links,
    processes_missing_operator_tasks,
    state_expected_outcome,
)

OUT_PDF = ROOT / "docs" / "راهنمای_جامع_تست_همه_فرایندها.pdf"
OUT_GAP_MD = ROOT / "docs" / "فرم_ثبت_کمبود_فرایندها.md"
OUT_GAP_CSV = ROOT / "docs" / "gap_report_template.csv"


class ComprehensiveGuideBuilder:
    def __init__(self, specs: list[ProcessTestSpec], links: list[CrossProcessLink]) -> None:
        self.specs = specs
        self.links = links
        self.by_code = {s.code: s for s in specs}
        self.pdf = GuidePDF(footer_label="راهنمای جامع تست فرایندها — انستیتو")
        register_fonts(self.pdf)
        self.pdf.set_margins(MARGIN, MARGIN, MARGIN)
        self.pdf.set_auto_page_break(auto=True, margin=16)
        self.sb = PdfSectionBuilder(self.pdf)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.pdf.output(str(path))

    # ── Section 0: Cover ──────────────────────────────────────────────

    def cover(self) -> None:
        p = self.pdf
        p.add_page()
        p.set_font("Vazir", "B", TITLE)
        p.ln(8)
        p.cell(0, 12, fa("راهنمای جامع آزمایش همه فرایندها"), align="C", new_x="LMARGIN", new_y="NEXT")
        p.set_font("Vazir", "", 12)
        p.cell(
            0,
            10,
            fa("انستیتو روانکاوی تهران — برای اپراتور اتوماسیون (بدون دانش فنی)"),
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        p.ln(6)
        p.set_font("Vazir", "", BODY)
        p.multi_cell(
            0,
            6,
            fa(
                f"این سند {len(self.specs)} فرایند را از ابتدا تا انتها پوشش می‌دهد. "
                "در حین تست هیچ اصلاح فنی انجام ندهید — فقط نتیجه را ثبت کنید "
                "و کمبودها را با کد GAP گزارش دهید."
            ),
            align="R",
        )
        p.ln(4)
        for label, blank in [
            ("نام تست‌کننده", "________________________"),
            ("تاریخ", "________________________"),
            ("آدرس سایت", "________________________"),
        ]:
            p.cell(0, 8, fa(f"{label}: {blank}"), align="R", new_x="LMARGIN", new_y="NEXT")
        p.ln(3)
        self.sb.warn_box(
            "قانون طلایی: در حین تست هیچ تغییر فنی در سامانه ندهید. "
            "فقط جدول‌ها را پر کنید و GAP ثبت کنید."
        )

    # ── Section 0b: Operator training ─────────────────────────────────

    def part_operator_training(self) -> None:
        self.pdf.add_page()
        self.sb.section_bar("آموزش اپراتور تست — قبل از شروع")
        self.sb.body(OPERATOR_TEST_INTRO)
        self.sb.body("هدف کلی این تست چیست؟", bold=True)
        self.sb.body(
            "مطمئن شویم هر فرایند آموزشی/درمانی از ابتدا تا انتها در سامانه "
            "قابل انجام است، متن‌ها قابل فهم است، دکمه‌ها درست کار می‌کنند، "
            "و وقتی یک فرایند تمام می‌شود فرایند بعدی در جای درست ظاهر می‌شود."
        )
        self.sb.body("شما دقیقاً چه کاری می‌کنید؟", bold=True)
        self.sb.numbered_list([
            "با حساب گفته‌شده وارد سامانه می‌شوید.",
            "مسیر منو را طبق راهنما باز می‌کنید.",
            "هر مرحله را انجام می‌دهید و در جدول «بله» یا «خیر» می‌زنید.",
            "اگر «خیر» بود، در جعبهٔ GAP توضیح می‌دهید چه انتظار داشتید و چه دیدید.",
        ])
        self.sb.body("نتیجهٔ درست یعنی چه؟", bold=True)
        self.sb.bullet_list([
            "صفحهٔ خالی یا خطای قرمز نمی‌بینید.",
            "دکمهٔ «ثبت» یا «ادامه» کار می‌کند و وضعیت عوض می‌شود.",
            "متن وضعیت با راهنما هم‌خوان است (مثلاً «منتظر تأیید درمانگر»).",
            "پس از پایان، فرایند بعدی در پنل نقش مربوط دیده می‌شود.",
        ])
        self.sb.section_bar("اگر نتیجهٔ مورد نظر را نگرفتید")
        self.sb.numbered_list(OPERATOR_FAILURE_STEPS)
        self.sb.ok_box(
            "مثال ثبت GAP: «انتظار داشتم بعد از ثبت، وضعیت به منتظر پذیرش برود؛ "
            "در عوض همان صفحه ماند و پیامی نیامد.» — GAP-01-document_review — UI — high"
        )
        self._part_table_reading_guide()

    def _part_table_reading_guide(self) -> None:
        self.pdf.add_page()
        self.sb.section_bar("راهنمای خواندن جدول‌ها")
        self.sb.body(
            "در این سند سه نوع جدول اصلی دارید. قبل از شروع تست، "
            "یک‌بار این راهنما را بخوانید."
        )
        self.sb.body("۱) جدول حساب‌های آزمایشی", bold=True)
        self.sb.simple_table(
            headers=["ستون", "معنی برای شما"],
            rows=list(TABLE_ACCOUNT_COLUMN_GUIDE),
            col_widths=[35, 135],
        )
        self.sb.body("۲) جدول مراحل هر فرایند (مهم‌ترین جدول تست)", bold=True)
        self.sb.simple_table(
            headers=["ستون", "معنی برای شما"],
            rows=list(TABLE_STEP_COLUMN_GUIDE),
            col_widths=[35, 135],
        )
        self.sb.body("۳) جدول مپ بین‌فرایندی", bold=True)
        self.sb.bullet_list([
            "بعد از پایان یک فرایند، بررسی کنید فرایند مقصد در منوی گفته‌شده ظاهر شده باشد.",
            "ستون «انتظار»: پروندهٔ جدید باید در همان منو دیده شود.",
            "اگر ندیدید: در یادداشت بنویسید و GAP با نوع cross_process ثبت کنید.",
        ])
        self.sb.tip_box(
            "روش پیشنهادی: هر ردیف جدول مراحل را یک‌به‌یک انجام دهید؛ "
            "بلافاصله «بله» یا «خیر» بزنید؛ بعد به ردیف بعد بروید. "
            "یادداشت را همان لحظه بنویسید تا فراموش نکنید."
        )

    # ── Section 1: Methodology ───────────────────────────────────────

    def part_methodology(self) -> None:
        self.pdf.add_page()
        self.sb.section_bar("بخش ۱ — روش تست مسیر و رابط کاربری")
        self.sb.body(
            "برای هر فرایند این پنج گام را تکرار کنید:"
        )
        self.sb.numbered_list([
            "از صفحهٔ ورود با حساب نقش درست (جدول حساب‌ها) وارد شوید.",
            "از منوی کناری، پنل نقش خود را باز کنید و به تب گفته‌شده در راهنمای همان فرایند بروید.",
            "پرونده را در «کارهای من»، «فرایندها» یا «بررسی‌ها» (بسته به نقش) باز کنید.",
            "فرم را پر کنید → «ثبت» → در صورت وجود «ادامه» یا «تأیید».",
            "وضعیت جدید را در همان پرونده یا پورتال نقش بعدی بررسی کنید.",
        ])
        self.sb.section_bar("مراحل خودکار (نقش سامانه)")
        self.sb.body(
            "اگر در جدول مراحل نوشته «خودکار»، دکمه‌ای نمی‌بینید. "
            "فقط بررسی کنید نتیجه (وضعیت، اعلان، پروفایل) درست است "
            "و در ستون توضیح بنویسید «خودکار بود»."
        )
        self.sb.section_bar("آماده‌سازی محیط دمو (یک‌بار — از مسئول فنی)")
        self.sb.body("قبل از شروع تست، مسئول فنی این دستورات را اجرا کند:")
        self.sb.bullet_list([
            "python scripts/seed_all_roles.py",
            "python scripts/seed_semester_prep_demo.py",
            "python scripts/seed_operator_pending_demo.py",
            "سامانه روی http://localhost:3000 در دسترس باشد",
        ])

    def part_accounts(self) -> None:
        self.pdf.add_page()
        self.sb.section_bar("جدول حساب‌های آزمایشی")
        self.sb.body(
            "برای هر مرحلهٔ راهنما، با «نام کاربری» و «رمز» همان نقش وارد شوید. "
            "ستون‌های لاتین را دقیقاً همان‌طور که نوشته شده تایپ کنید. "
            "پس از ورود، مسیر «منوی سایدبار» را باز کنید و ببینید آیا «باید ببینم» "
            "با صفحهٔ واقعی یکی است — اگر نه، در ستون یادداشت بنویسید."
        )
        account_rows = [
            [
                g.role_fa,
                g.username,
                g.password,
                g.sidebar_menu[:32],
                g.when_to_use[:38],
                g.what_to_expect[:38],
                "[ ]",
                "[ ]",
                "",
            ]
            for g in DEMO_ACCOUNT_GUIDES
        ]
        chunk_size = 5
        for start in range(0, len(account_rows), chunk_size):
            if start > 0:
                self.pdf.add_page()
                self.sb.section_bar("جدول حساب‌های آزمایشی (ادامه)")
            self.sb.simple_table(
                headers=[
                    "نقش",
                    "کاربری",
                    "رمز",
                    "منوی سایدبار",
                    "کی استفاده کنم",
                    "باید ببینم",
                    "بله",
                    "خیر",
                    "یادداشت",
                ],
                rows=account_rows[start : start + chunk_size],
                col_widths=[16, 20, 10, 28, 34, 34, 7, 7, 22],
                fa_cols=[True, False, False, True, True, True, False, False, True],
                line_height=5.2,
                font_size=SMALL,
            )
        self.sb.section_bar("توضیح تکمیلی هر حساب (اگر جدول بالا کافی نبود)")
        for i, g in enumerate(DEMO_ACCOUNT_GUIDES, 1):
            self.sb.ensure_space(36)
            self.sb.body(f"{i}. {g.role_fa} — ورود با {g.username} / {g.password}", bold=True)
            self.sb.body(f"مسیر: {g.sidebar_menu}")
            self.sb.body(f"هدف تست با این حساب: {g.when_to_use}")
            self.sb.body(f"نشانهٔ موفقیت: {g.what_to_expect}")
            self.sb.body(
                "چک ورود: [ ] منوی گفته‌شده را می‌بینم  "
                "[ ] پرونده/فرم نمونه وجود دارد  "
                "[ ] مشکل: _________________________"
            )

    def part_limits(self) -> None:
        self.sb.section_bar("محدودیت‌های شفاف (باگ نیستند)")
        self.sb.bullet_list([
            "پرداخت واقعی نیست — فقط مسیر UI را طی کنید.",
            "LMS بیرونی شبیه‌سازی شده است.",
            "کارنامه و گواهی ممکن است متن روی صفحه باشد نه PDF چاپی.",
            "فرایندهای زمان‌بند: از منوی کناری / اتوماسیون زمان‌محور یا seed دمو.",
            "فرایندهای غیرقابل ریست: fee_determination، session_payment، آماده‌سازی ترم.",
        ])

    def part_gap_howto(self) -> None:
        self.pdf.add_page()
        self.sb.section_bar("روش ثبت کمبود (GAP) — زبان ساده")
        self.sb.body(
            "هر کمبود یک شناسه دارد که در جدول مراحل همان فرایند نوشته شده: "
            "GAP-{شماره فرایند}-{کد مرحله} — مثال: GAP-06-therapist_recording"
        )
        self.sb.body("چه زمانی GAP بنویسم؟", bold=True)
        self.sb.bullet_list([
            "دکمه‌ای که راهنما گفته نیست یا کار نمی‌کند.",
            "متن گیج‌کننده یا اشتباه روی صفحه.",
            "وضعیت عوض نمی‌شود بعد از ثبت.",
            "فرایند بعدی در پنل نقش بعدی ظاهر نمی‌شود.",
            "صفحهٔ خطا یا صفحهٔ سفید.",
        ])
        self.sb.simple_table(
            headers=["فیلد", "چه بنویسم (مثال ساده)"],
            rows=[
                ["شناسه GAP", "GAP-06-therapist_recording"],
                ["انتظار داشتم", "بعد از ثبت، وضعیت به «فعال» برود"],
                ["در عوض دیدم", "همان صفحه ماند؛ پیامی نیامد"],
                ["نوع", "UI / logic / text / missing_step / cross_process"],
                ["اولویت", "high = نمی‌توان ادامه داد؛ medium = سخت؛ low = ظاهری"],
            ],
            col_widths=[40, 130],
        )
        self.sb.section_bar("جدول فنی (برای مدیر پروژه)")
        self.sb.simple_table(
            headers=["ستون", "توضیح"],
            rows=[
                ["gap_id", "شناسه یکتا — در Cursor بگویید: رفع GAP-06-..."],
                ["process_code", "کد فنی فرایند"],
                ["state_code", "کد مرحله"],
                ["gap_type", "UI / logic / text / missing_step / cross_process"],
                ["priority", "high / medium / low"],
                ["expected", "چه انتظار داشتید (یک جمله)"],
                ["actual", "چه اتفاق افتاد (یک جمله)"],
            ],
            col_widths=[40, 130],
        )
        self.sb.tip_box(
            "فرم همراه: docs/فرم_ثبت_کمبود_فرایندها.md و "
            "docs/gap_report_template.csv — ردیف‌ها را برای مدیر پروژه بفرستید."
        )

    def part_lifecycle_order(self) -> None:
        self.pdf.add_page()
        self.sb.section_bar("ترتیب پیشنهادی تست (مسیر زندگی دانشجو)")
        self.sb.body(
            "لازم نیست دقیقاً به این ترتیب باشد، اما برای تست مپ بین‌فرایندی "
            "این مسیر منطقی‌تر است:"
        )
        items = []
        for i, code in enumerate(LIFECYCLE_ORDER, 1):
            spec = self.by_code.get(code)
            if spec:
                items.append(f"{spec.number}. {spec.name_fa} ({code})")
            else:
                items.append(f"{code}")
        self.sb.numbered_list(items)

    # ── Section 2: Cross-process map ──────────────────────────────────

    def part_cross_process_map(self) -> None:
        self.pdf.add_page()
        self.sb.section_bar("بخش ۲ — مپ بین‌فرایندی")
        self.sb.body(
            f"تعداد {len(self.links)} ارتباط بین فرایندها. "
            "پس از هر رویداد، پرونده فرایند مقصد را در inbox نقش مربوط بررسی کنید. "
            "برای هر ردیف: ابتدا فرایند مبدأ را تمام کنید، سپس با حساب گفته‌شده "
            "به منوی مقصد بروید و ببینید پروندهٔ جدید هست یا نه."
        )
        self.sb.simple_table(
            headers=["ستون", "چه کار کنید"],
            rows=[
                ["فرایند مبدأ", "فرایندی که الان تست کردید و تمام/نزدیک پایان است."],
                ["مرحله/رویداد", "در کدام نقطه باید فرایند بعدی ساخته شود."],
                ["فرایند مقصد", "فرایندی که باید خودکار ظاهر شود."],
                ["حساب بررسی", "با این نام کاربری وارد شوید."],
                ["کجا بررسی", "از این منو پرونده را پیدا کنید."],
                ["انتظار", "پروندهٔ مقصد باید در لیست باشد."],
                ["بله/خیر", "آیا دیدید؟ اگر خیر → cross_process GAP."],
                ["یادداشت", "چه انتظار داشتید / چه دیدید."],
            ],
            col_widths=[32, 143],
        )

        chunk_size = 10
        for start in range(0, len(self.links), chunk_size):
            if start > 0:
                self.pdf.add_page()
                self.sb.section_bar("مپ بین‌فرایندی (ادامه)")
            chunk = self.links[start : start + chunk_size]
            rows = []
            for link in chunk:
                rows.append([
                    link.source_name_fa[:20],
                    link.from_state[:14],
                    link.target_name_fa[:20],
                    link.verifier_role[:14],
                    link.verify_portal[:24],
                    "پرونده مقصد دیده شود",
                    "[ ]",
                    "[ ]",
                    "",
                ])
            self.sb.simple_table(
                headers=[
                    "مبدأ",
                    "رویداد",
                    "مقصد",
                    "حساب",
                    "منو",
                    "انتظار",
                    "بله",
                    "خیر",
                    "یادداشت",
                ],
                rows=rows,
                col_widths=[18, 16, 18, 16, 26, 22, 7, 7, 20],
                line_height=5.0,
                font_size=SMALL,
            )

        self.pdf.add_page()
        self.sb.section_bar("سناریوهای تست مپ (جزئیات)")
        for link in self.links:
            self.sb.ensure_space(28)
            self.sb.body(
                f"{link.source_name_fa} به {link.target_name_fa} "
                f"({LINK_TYPE_FA.get(link.link_type, link.link_type)})",
                bold=True,
            )
            self.sb.body(f"رویداد: {link.trigger} | مرحله: {link.from_state}")
            self.sb.body(f"۱) با حساب {link.verifier_role} وارد شوید.")
            self.sb.body(f"۲) از {link.verify_portal} پروندهٔ «{link.target_name_fa}» را بجوید.")
            self.sb.body(link.test_scenario)
            self.sb.body("۳) انتظار: پروندهٔ فرایند مقصد در لیست دیده شود.", bold=True)
            self.sb.body(
                "۴) اگر ندیدید: در یادداشت بنویسید «انتظار داشتم پروندهٔ … ظاهر شود؛ "
                "در عوض لیست خالی بود» و GAP با نوع cross_process ثبت کنید."
            )
            self.sb.body("نتیجه: [ ] موفق  [ ] ناموفق  |  GAP-ID: _______________")
            self.sb.body("یادداشت: _________________________________________________")
            self.sb.body("")

    # ── Section 3: All processes ──────────────────────────────────────

    def part_all_processes(self) -> None:
        self.pdf.add_page()
        self.sb.section_bar(f"بخش ۳ — راهنمای کامل {len(self.specs)} فرایند")
        self.sb.body(
            "هر فرایند: توضیح، پیش‌نیاز، مسیر UI، جدول مراحل، و جعبه ثبت GAP."
        )
        for spec in self.specs:
            self._process_page(spec)

    def _process_page(self, spec: ProcessTestSpec) -> None:
        self.pdf.add_page()
        self.sb.section_bar(f"فرایند #{spec.number}: {spec.name_fa}")

        if spec.is_stub:
            self.sb.warn_box("این فرایند ادغام‌شده/غیرفعال است — رد شوید.")
            return

        meta_line = f"کد: {spec.code}  |  GAP پیشوند: {spec.gap_prefix}"
        self.sb.body(meta_line, bold=True)

        if spec.restart_blocked:
            self.sb.warn_box("غیرقابل ریست — در صورت گیرکردن فقط GAP ثبت کنید.")
        if spec.scheduler_note:
            self.sb.tip_box(spec.scheduler_note)

        enrich = spec.enrichment or {}
        self.sb.body("هدف این تست", bold=True)
        goal = enrich.get("expect") or (
            f"فرایند «{spec.name_fa}» از اولین مرحله تا پایان بدون گیر، "
            "خطای گیج‌کننده یا صفحهٔ خالی طی شود."
        )
        self.sb.body(goal)

        self.sb.body("نتیجهٔ درست (موفقیت تست)", bold=True)
        success_items = [
            "همهٔ مراحل انسانی در جدول پایین «بله» خورده باشند.",
            "وضعیت نهایی با توضیح راهنما هم‌خوان باشد.",
        ]
        if spec.outbound_links:
            success_items.append(
                "اگر فرایند بعدی باید ایجاد شود، در پنل نقش مربوط دیده شود."
            )
        self.sb.bullet_list(success_items)

        self.sb.body("این فرایند چیست؟", bold=True)
        desc = spec.description[:600] + ("..." if len(spec.description) > 600 else "")
        self.sb.body(desc or "—")

        if spec.preconditions:
            self.sb.body("پیش‌نیاز:", bold=True)
            for p in spec.preconditions:
                self.sb.body(f"• {p}")

        if spec.inbound_links:
            self.sb.body("فرایندهای مرتبط (ورودی):", bold=True)
            for link in spec.inbound_links[:5]:
                self.sb.body(
                    f"• از {link.source_name_fa} ({LINK_TYPE_FA.get(link.link_type, '')})"
                )

        self.sb.body("چه کسی شروع می‌کند؟", bold=True)
        who = enrich.get("who") or (
            f"{ROLE_FA.get(spec.initial_role, spec.initial_role)} "
            f"(حساب: {spec.demo_username})"
        )
        self.sb.body(who)

        self.sb.body("کجا بروم؟", bold=True)
        where = enrich.get("where") or spec.portal_menu_nav or "پورتال نقش مربوط"
        self.sb.body(where)

        if enrich.get("steps"):
            self.sb.body("قدم‌به‌قدم:", bold=True)
            self.sb.numbered_list(enrich["steps"])
        if enrich.get("expect"):
            self.sb.body("باید چه ببینم؟", bold=True)
            self.sb.body(enrich["expect"])
        for tip in enrich.get("tips") or []:
            self.sb.tip_box(tip)

        self._render_state_tables(spec)

        if spec.outbound_links:
            self.sb.body("اگر فرایند فرزند ایجاد شد — کجا بررسی کنم:", bold=True)
            for link in spec.outbound_links[:4]:
                self.sb.body(
                    f"• {link.target_name_fa}: {link.verify_portal} "
                    f"(حساب: {link.verifier_role})"
                )

        self.sb.section_bar("اگر مرحله‌ای «خیر» شد")
        self.sb.numbered_list(OPERATOR_FAILURE_STEPS[:4])
        self.sb.blank_lines("ثبت GAP (شناسه / نوع / اولویت / انتظار داشتم / در عوض دیدم):", 3)

    def _build_state_row(self, st: StateTestSpec) -> list[str]:
        expected = state_expected_outcome(st.name_fa, st.is_automatic, st.role_fa)
        task = st.operator_task_fa
        if len(task) > 72:
            task = task[:72] + "…"
        menu = st.portal_menu_nav or "—"
        if len(menu) > 30:
            menu = menu[:30] + "…"
        if len(expected) > 36:
            expected = expected[:36] + "…"
        gap_short = st.gap_id
        if len(gap_short) > 18:
            gap_short = "…" + gap_short[-17:]
        return [
            str(st.index),
            st.name_fa[:16],
            st.role_fa[:10],
            menu,
            task,
            expected,
            gap_short,
            "[ ]",
            "[ ]",
            "",
        ]

    def _render_state_tables(self, spec: ProcessTestSpec) -> None:
        self.sb.section_bar("جدول مراحل تست — راهنمای پر کردن")
        self.sb.body(
            "هر ردیف = یک مرحله. ابتدا «اقدام شما» را انجام دهید، "
            "سپس ببینید «نتیجه مورد انتظار» رخ داده یا نه. "
            "اگر نشد: «خیر» بزنید و در «یادداشت» بنویسید + شناسه GAP همان ردیف."
        )
        self.sb.simple_table(
            headers=["ستون", "معنی"],
            rows=list(TABLE_STEP_COLUMN_GUIDE),
            col_widths=[32, 143],
            font_size=SMALL,
        )
        state_rows = [self._build_state_row(st) for st in spec.states]
        chunk_size = 6
        for i in range(0, len(state_rows), chunk_size):
            if i > 0:
                self.pdf.add_page()
                self.sb.section_bar(f"فرایند #{spec.number}: {spec.name_fa} — جدول مراحل (ادامه)")
            self.sb.simple_table(
                headers=[
                    "ردیف",
                    "مرحله",
                    "نقش",
                    "مسیر منو",
                    "اقدام شما",
                    "انتظار",
                    "GAP",
                    "بله",
                    "خیر",
                    "یادداشت",
                ],
                rows=state_rows[i : i + chunk_size],
                col_widths=[7, 15, 12, 24, 38, 28, 17, 6, 6, 18],
                fa_cols=[False, True, True, True, True, True, False, False, False, True],
                line_height=5.4,
                font_size=SMALL,
            )
        self._render_human_step_details(spec)

    def _render_human_step_details(self, spec: ProcessTestSpec) -> None:
        human_states = [st for st in spec.states if not st.is_automatic]
        if not human_states:
            return
        self.pdf.add_page()
        self.sb.section_bar(f"شرح آموزشی مراحل انسانی — فرایند #{spec.number}")
        self.sb.body(
            "این بخش همان جدول بالا را با توضیح کامل‌تر می‌نویسد. "
            "اگر در جدول جا کم بود، اینجا بخوانید و همان‌جا نتیجه را علامت بزنید."
        )
        for st in human_states:
            self.sb.ensure_space(44)
            expected = state_expected_outcome(st.name_fa, st.is_automatic, st.role_fa)
            self.sb.body(f"مرحله {st.index}: {st.name_fa}", bold=True)
            self.sb.body(f"هدف این مرحله: {expected}")
            self.sb.body(f"ورود: حساب {st.demo_username} ({st.role_fa})")
            self.sb.body(f"مسیر: {st.portal_menu_nav}")
            self.sb.body("اقدام گام‌به‌گام:", bold=True)
            self.sb.body(st.operator_task_fa)
            self.sb.body(f"شناسه GAP (در صورت مشکل): {st.gap_id}")
            self.sb.body(
                "چک‌لیست: [ ] وارد شدم  [ ] مسیر درست بود  [ ] فرم/دکمه بود  "
                "[ ] ثبت شد  [ ] نتیجه درست بود"
            )
            self.sb.body("نتیجه: [ ] بله  [ ] خیر  |  یادداشت: ________________________________")
            self.sb.body("")

    # ── Section 4: Summary matrix ─────────────────────────────────────

    def part_summary_matrix(self) -> None:
        self.pdf.add_page()
        self.sb.section_bar("بخش ۴ — ماتریس خلاصه همه فرایندها")
        self.sb.body(
            "پس از تست هر فرایند، این جدول را پر کنید. "
            "ستون «هدف تست» یادآور است که چه چیزی را بررسی می‌کنید. "
            "ستون «یادداشت» برای جمع‌بندی کوتاه یا تعداد GAP."
        )
        self.sb.simple_table(
            headers=["ستون", "معنی"],
            rows=[
                ["شماره / نام", "کدام فرایند را تست کردید."],
                ["هدف تست", "چه انتظاری دارید — خلاصهٔ یک خط."],
                ["مسیر منو", "از کجا شروع می‌شود."],
                ["مراحل انسانی", "تقریباً چند مرحله دستی دارید."],
                ["تست شد", "آیا کل فرایند را یک‌بار طی کردید؟"],
                ["تعداد GAP", "چند مشکل پیدا کردید."],
                ["یادداشت", "جمع‌بندی یا اولویت مشکلات."],
            ],
            col_widths=[30, 145],
            font_size=SMALL,
        )
        chunk_size = 20
        for start in range(0, len(self.specs), chunk_size):
            if start > 0:
                self.pdf.add_page()
                self.sb.section_bar("ماتریس خلاصه (ادامه)")
            chunk = self.specs[start : start + chunk_size]
            rows = []
            for spec in chunk:
                enrich = spec.enrichment or {}
                goal = enrich.get("expect") or f"تکمیل «{spec.name_fa[:20]}»"
                if len(goal) > 28:
                    goal = goal[:28] + "…"
                portal_short = (spec.portal_menu_nav or "—")[:22]
                rows.append([
                    str(spec.number),
                    spec.name_fa[:18],
                    goal,
                    portal_short,
                    str(spec.human_state_count),
                    "[ ]",
                    "",
                    "",
                ])
            self.sb.simple_table(
                headers=[
                    "شماره",
                    "نام",
                    "هدف تست",
                    "مسیر منو",
                    "مراحل",
                    "تست شد",
                    "GAP",
                    "یادداشت",
                ],
                rows=rows,
                col_widths=[10, 22, 30, 26, 12, 12, 10, 28],
                line_height=5.0,
                font_size=SMALL,
            )

    # ── Section 5: GAP appendix ───────────────────────────────────────

    def part_gap_appendix(self) -> None:
        self.pdf.add_page()
        self.sb.section_bar("بخش ۵ — پیوست ثبت کمبود برای Cursor")
        self.sb.body(
            "برای هر GAP یک ردیف پر کنید. در Cursor کافی است بگویید: "
            "«رفع GAP-XX-state_code» و ردیف زیر را paste کنید."
        )
        self.sb.simple_table(
            headers=[
                "gap_id",
                "process_code",
                "state_code",
                "role",
                "gap_type",
                "priority",
                "expected",
                "actual",
            ],
            rows=[["", "", "", "", "", "", "", ""] for _ in range(8)],
            col_widths=[22, 24, 22, 18, 18, 14, 30, 30],
        )
        self.sb.section_bar("دستورالعمل ارسال به مدیر پروژه")
        self.sb.numbered_list([
            "فایل PDF پرشده یا docs/فرم_ثبت_کمبود_فرایندها.md را بفرستید.",
            "در صورت امکان عکس از صفحه (Print Screen) ضمیمه کنید.",
            "برای هر GAP فقط یک جمله expected و یک جمله actual بنویسید.",
            "مدیر پروژه ردیف CSV را در Cursor paste می‌کند.",
        ])


def write_gap_markdown(specs: list[ProcessTestSpec], path: Path) -> None:
    lines = [
        "# فرم ثبت کمبود فرایندها — انستیتو روانکاوی تهران",
        "",
        "**راهنما:** پس از تست، ردیف‌های GAP را پر کنید و برای مدیر پروژه بفرستید.",
        "**PDF کامل:** `docs/راهنمای_جامع_تست_همه_فرایندها.pdf`",
        "",
        "## مشخصات تست",
        "",
        "| فیلد | مقدار |",
        "|------|--------|",
        "| نام تست‌کننده | |",
        "| تاریخ | |",
        "| محیط | |",
        "",
        "## قالب GAP",
        "",
        "| gap_id | process_code | state_code | role | portal_path | gap_type | priority | expected | actual |",
        "|--------|--------------|------------|------|-------------|----------|----------|----------|--------|",
    ]
    for _ in range(20):
        lines.append("| | | | | | | | | |")
    lines.extend([
        "",
        "## فهرست پیشوند GAP به ازای فرایند",
        "",
        "| شماره | نام | کد | پیشوند GAP |",
        "|-------|-----|-----|------------|",
    ])
    for spec in specs:
        if spec.is_stub:
            continue
        lines.append(
            f"| {spec.number} | {spec.name_fa} | `{spec.code}` | `{spec.gap_prefix}-*` |"
        )
    lines.extend([
        "",
        "## انواع gap_type",
        "",
        "- `UI` — دکمه/فرم/چیدمان",
        "- `logic` — رفتار اشتباه سامانه",
        "- `text` — متن گیج‌کننده یا نادرست",
        "- `missing_step` — مرحله یا قابلیت نیست",
        "- `cross_process` — فرایند فرزند ظاهر نشد یا اشتباه",
        "",
        "*پایان فرم*",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def write_gap_csv(path: Path) -> None:
    headers = [
        "gap_id",
        "process_code",
        "state_code",
        "role",
        "portal_path",
        "gap_type",
        "priority",
        "expected",
        "actual",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)


def main() -> int:
    specs = build_process_specs()
    links = collect_cross_process_links(specs)

    builder = ComprehensiveGuideBuilder(specs, links)
    builder.cover()
    builder.part_operator_training()
    builder.part_methodology()
    builder.part_accounts()
    builder.part_limits()
    builder.part_gap_howto()
    builder.part_lifecycle_order()
    builder.part_cross_process_map()
    builder.part_all_processes()
    builder.part_summary_matrix()
    builder.part_gap_appendix()
    builder.save(OUT_PDF)

    write_gap_markdown(specs, OUT_GAP_MD)
    write_gap_csv(OUT_GAP_CSV)

    missing = processes_missing_operator_tasks(specs)
    print(f"PDF written: {OUT_PDF}")
    print(f"Pages: {builder.pdf.page_no()}")
    print(f"Size: {OUT_PDF.stat().st_size:,} bytes")
    print(f"Processes: {len(specs)}")
    print(f"Cross-process links: {len(links)}")
    print(f"Gap form: {OUT_GAP_MD}")
    print(f"Gap CSV: {OUT_GAP_CSV}")
    if missing:
        print(f"States with auto-generated task text: {len(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
