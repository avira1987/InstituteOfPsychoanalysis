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
    TITLE,
    GuidePDF,
    PdfSectionBuilder,
    fa,
    register_fonts,
)
from scripts.lib.process_test_guide_data import (
    DEMO_ACCOUNTS,
    LIFECYCLE_ORDER,
    LINK_TYPE_FA,
    ROLE_FA,
    CrossProcessLink,
    ProcessTestSpec,
    build_process_specs,
    collect_cross_process_links,
    processes_missing_operator_tasks,
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

    # ── Section 1: Methodology ───────────────────────────────────────

    def part_methodology(self) -> None:
        self.pdf.add_page()
        self.sb.section_bar("بخش ۱ — روش تست مسیر و رابط کاربری")
        self.sb.body(
            "برای هر فرایند این پنج گام را تکرار کنید:"
        )
        self.sb.numbered_list([
            "با نقش درست (جدول حساب‌ها) وارد شوید: /login?staff=1",
            "به پورتال و تب مشخص‌شده در راهنمای همان فرایند بروید.",
            "پرونده را در «کارهای منتظر» یا «بررسی‌ها» باز کنید.",
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
        rows = [[user, pw] for _, user, pw in DEMO_ACCOUNTS]
        self.sb.simple_table(
            headers=["نقش", "نام کاربری", "رمز"],
            rows=[[fa(role), user, pw] for role, user, pw in DEMO_ACCOUNTS],
            col_widths=[70, 58, 28],
        )

    def part_limits(self) -> None:
        self.sb.section_bar("محدودیت‌های شفاف (باگ نیستند)")
        self.sb.bullet_list([
            "پرداخت واقعی نیست — فقط مسیر UI را طی کنید.",
            "LMS بیرونی شبیه‌سازی شده است.",
            "کارنامه و گواهی ممکن است متن روی صفحه باشد نه PDF چاپی.",
            "فرایندهای زمان‌بند: از /panel/automation-scheduler یا seed دمو.",
            "فرایندهای غیرقابل ریست: fee_determination، session_payment، آماده‌سازی ترم.",
        ])

    def part_gap_howto(self) -> None:
        self.pdf.add_page()
        self.sb.section_bar("روش ثبت کمبود (GAP) برای Cursor")
        self.sb.body(
            "هر کمبود یک شناسه دارد: GAP-{شماره فرایند}-{کد مرحله} "
            "مثال: GAP-06-therapist_recording"
        )
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
            "پس از هر رویداد، پرونده فرایند مقصد را در inbox نقش مربوط بررسی کنید."
        )

        chunk_size = 18
        for start in range(0, len(self.links), chunk_size):
            if start > 0:
                self.pdf.add_page()
                self.sb.section_bar("مپ بین‌فرایندی (ادامه)")
            chunk = self.links[start : start + chunk_size]
            rows = []
            for link in chunk:
                rows.append([
                    link.source_name_fa[:28],
                    link.from_state[:18],
                    link.target_name_fa[:28],
                    ROLE_FA.get(link.verifier_role, link.verifier_role)[:16],
                    "",
                ])
            self.sb.simple_table(
                headers=[
                    "فرایند مبدأ",
                    "مرحله/رویداد",
                    "فرایند مقصد",
                    "نقش بررسی",
                    "نتیجه [ ]",
                ],
                rows=rows,
                col_widths=[38, 32, 38, 28, 18],
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
            self.sb.body(f"بررسی با: {link.verifier_role} در {link.verify_portal}")
            self.sb.body(link.test_scenario)
            self.sb.body("نتیجه تست: [ ] موفق  [ ] ناموفق  |  GAP-ID: _______________")
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

        enrich = spec.enrichment or {}
        self.sb.body("چه کسی شروع می‌کند؟", bold=True)
        who = enrich.get("who") or (
            f"{ROLE_FA.get(spec.initial_role, spec.initial_role)} "
            f"(حساب: {spec.demo_username})"
        )
        self.sb.body(who)

        self.sb.body("کجا بروم؟", bold=True)
        where = enrich.get("where") or spec.portal_path or "پورتال نقش مربوط"
        self.sb.body(where)

        if enrich.get("steps"):
            self.sb.body("قدم‌به‌قدم:", bold=True)
            self.sb.numbered_list(enrich["steps"])
        if enrich.get("expect"):
            self.sb.body("باید چه ببینم؟", bold=True)
            self.sb.body(enrich["expect"])
        for tip in enrich.get("tips") or []:
            self.sb.tip_box(tip)

        self.sb.body("جدول مراحل — نتیجه را علامت بزنید:", bold=True)
        state_rows = []
        for st in spec.states:
            kind = "خودکار" if st.is_automatic else "انسانی"
            task_short = st.operator_task_fa[:55] + ("…" if len(st.operator_task_fa) > 55 else "")
            state_rows.append([
                str(st.index),
                st.name_fa[:22],
                st.role_fa[:14],
                kind,
                task_short,
                "[ ]",
                "[ ]",
            ])
        chunk_size = 14
        for i in range(0, len(state_rows), chunk_size):
            if i > 0:
                self.pdf.add_page()
                self.sb.section_bar(f"فرایند #{spec.number}: {spec.name_fa} (ادامه مراحل)")
            self.sb.simple_table(
                headers=["#", "مرحله", "نقش", "نوع", "چه کار کنم", "بله", "خیر"],
                rows=state_rows[i : i + chunk_size],
                col_widths=[8, 30, 22, 14, 58, 10, 10],
            )

        if spec.outbound_links:
            self.sb.body("اگر فرایند فرزند ایجاد شد — کجا بررسی کنم:", bold=True)
            for link in spec.outbound_links[:4]:
                self.sb.body(
                    f"• {link.target_name_fa}: {link.verify_portal} "
                    f"({link.verifier_role})"
                )

        self.sb.blank_lines("ثبت GAP (شناسه / نوع / اولویت / توضیح):", 2)

    # ── Section 4: Summary matrix ─────────────────────────────────────

    def part_summary_matrix(self) -> None:
        self.pdf.add_page()
        self.sb.section_bar("بخش ۴ — ماتریس خلاصه همه فرایندها")
        chunk_size = 35
        for start in range(0, len(self.specs), chunk_size):
            if start > 0:
                self.pdf.add_page()
                self.sb.section_bar("ماتریس خلاصه (ادامه)")
            chunk = self.specs[start : start + chunk_size]
            rows = []
            for spec in chunk:
                portal_short = (spec.portal_path or "—")[:30]
                rows.append([
                    str(spec.number),
                    spec.name_fa[:24],
                    spec.code[:22],
                    portal_short,
                    str(spec.human_state_count),
                    "[ ]",
                    "",
                ])
            self.sb.simple_table(
                headers=[
                    "شماره",
                    "نام",
                    "کد",
                    "پورتال",
                    "مراحل انسانی",
                    "تست شد",
                    "تعداد GAP",
                ],
                rows=rows,
                col_widths=[12, 38, 32, 38, 18, 14, 14],
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
