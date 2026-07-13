#!/usr/bin/env python3
"""
تولید PDF تست «ساخت از صفر — بدون seed پرونده».

هدف: کشف کمبود UI برای شروع و طی مسیر بدون دادهٔ ازپیش‌ساخته.

اجرا:
  python scripts/generate_from_scratch_test_pdf.py

خروجی:
  docs/راهنمای_تست_ساخت_از_صفر_بدون_seed.pdf
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
    LIFECYCLE_ORDER,
    OPERATOR_FAILURE_STEPS,
    SCRATCH_SEED_DO_NOT_RUN,
    SCRATCH_SEED_RUN,
    UI_GAP_CHECKLIST,
    ProcessTestSpec,
    StateTestSpec,
    UiStartGuide,
    build_process_specs,
    derive_ui_start,
    state_expected_outcome,
)

OUT_PDF = ROOT / "docs" / "راهنمای_تست_ساخت_از_صفر_بدون_seed.pdf"


class FromScratchGuideBuilder:
    def __init__(self, specs: list[ProcessTestSpec]) -> None:
        self.specs = [s for s in specs if not s.is_stub]
        self.by_code = {s.code: s for s in self.specs}
        self.pdf = GuidePDF(footer_label="تست ساخت از صفر — انستیتو")
        register_fonts(self.pdf)
        self.pdf.set_margins(MARGIN, MARGIN, MARGIN)
        self.pdf.set_auto_page_break(auto=True, margin=16)
        self.sb = PdfSectionBuilder(self.pdf)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.pdf.output(str(path))

    def cover(self) -> None:
        p = self.pdf
        p.add_page()
        p.set_font("Vazir", "B", TITLE)
        p.ln(6)
        p.cell(0, 12, fa("راهنمای تست ساخت از صفر — بدون seed"), align="C", new_x="LMARGIN", new_y="NEXT")
        p.set_font("Vazir", "", 11)
        p.cell(
            0,
            9,
            fa("کشف کمبود UI — همهٔ پرونده‌ها را خودتان از ابتدا بسازید"),
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        p.ln(5)
        p.set_font("Vazir", "", BODY)
        p.multi_cell(
            0,
            6,
            fa(
                f"این سند مکمل راهنمای جامع است و برای {len(self.specs)} فرایند "
                "نقطهٔ شروع UI، پیش‌نیاز ساخت، و چک‌لیست کمبود رابط کاربری دارد. "
                "seed پرونده اجرا نکنید — فقط حساب‌های ورود."
            ),
            align="R",
        )
        for label in ("نام تست‌کننده", "تاریخ", "آدرس سایت"):
            p.cell(0, 8, fa(f"{label}: ________________________"), align="R", new_x="LMARGIN", new_y="NEXT")
        self.sb.warn_box(
            "اگر inbox خالی است طبیعی است — یعنی هنوز نساخته‌اید. "
            "اگر پیش‌نیاز را ساختید ولی شروع/ادامه از UI ممکن نیست → GAP با نوع missing_step یا UI."
        )

    def part_seed_policy(self) -> None:
        self.pdf.add_page()
        self.sb.section_bar("سیاست seed — چه اجرا شود / چه نشود")
        self.sb.body("فقط این را اجرا کنید (مسئول فنی، یک‌بار):", bold=True)
        self.sb.simple_table(
            headers=["دستور", "چرا"],
            rows=[[cmd, why] for cmd, why in SCRATCH_SEED_RUN],
            col_widths=[55, 115],
            fa_cols=[False, True],
        )
        self.sb.body("این‌ها را برای این نوع تست اجرا نکنید:", bold=True)
        self.sb.simple_table(
            headers=["دستور", "چرا نزنید"],
            rows=[[cmd, why] for cmd, why in SCRATCH_SEED_DO_NOT_RUN],
            col_widths=[55, 115],
            fa_cols=[False, True],
        )
        self.sb.tip_box(
            "سامانه باید روشن باشد (مثلاً localhost:3000). "
            "اگر فقط seed_all_roles زده‌اید و پرونده‌ای نیست — درست است؛ "
            "شما باید از UI بسازید."
        )

    def part_methodology(self) -> None:
        self.pdf.add_page()
        self.sb.section_bar("روش تست ساخت از صفر")
        self.sb.numbered_list([
            "فقط seed_all_roles را بزنید (حساب ورود).",
            "ترتیب «مسیر زندگی دانشجو» را دنبال کنید — هر فرایند به قبلی وابسته است.",
            "برای هر فرایند: ابتدا «نقطهٔ شروع UI» را بخوانید و چک‌لیست ۵ سؤالی را پر کنید.",
            "اگر نتوانستید شروع کنید: GAP با missing_step یا UI — نه «seed بزن».",
            "اگر فرایند والد را ساختید ولی فرزند در منو نیامد: GAP با cross_process.",
            "مراحل را یک‌به‌یک در جدول علامت بزنید.",
        ])
        self.sb.section_bar("چک‌لیست کشف کمبود UI (هر فرایند)")
        self.sb.simple_table(
            headers=["سؤال", "اگر خیر — یعنی چه"],
            rows=[[q, f"کمبود UI/راهنما: {hint}"] for q, hint in UI_GAP_CHECKLIST],
            col_widths=[55, 115],
        )
        self.sb.section_bar("ثبت GAP")
        self.sb.numbered_list(OPERATOR_FAILURE_STEPS[:5])

    def part_accounts_compact(self) -> None:
        self.pdf.add_page()
        self.sb.section_bar("حساب‌های ورود (فقط برای لاگین)")
        self.sb.simple_table(
            headers=["نقش", "کاربری", "رمز", "منوی شروع"],
            rows=[
                [g.role_fa, g.username, g.password, g.sidebar_menu[:40]]
                for g in DEMO_ACCOUNT_GUIDES
            ],
            col_widths=[22, 24, 14, 108],
            fa_cols=[True, False, False, True],
            font_size=SMALL,
            line_height=5.0,
        )

    def part_build_order(self) -> None:
        self.pdf.add_page()
        self.sb.section_bar("ترتیب ساخت — مسیر زندگی دانشجو")
        self.sb.body(
            "هر ردیف را فقط پس از ساخت موفق ردیف‌های بالاتر شروع کنید. "
            "ستون «شروع از UI» را بعد از تست علامت بزنید."
        )
        rows = []
        for i, code in enumerate(LIFECYCLE_ORDER, 1):
            spec = self.by_code.get(code)
            if not spec:
                continue
            ui = derive_ui_start(spec)
            rows.append([
                str(i),
                spec.name_fa[:22],
                ui.mode_fa[:18],
                ui.account[:14],
                "[ ]",
                "",
            ])
        chunk = 18
        for start in range(0, len(rows), chunk):
            if start > 0:
                self.pdf.add_page()
                self.sb.section_bar("ترتیب ساخت (ادامه)")
            self.sb.simple_table(
                headers=["#", "فرایند", "نوع شروع", "حساب", "شدم", "یادداشت"],
                rows=rows[start : start + chunk],
                col_widths=[8, 38, 28, 22, 10, 30],
                font_size=SMALL,
            )

    def part_all_processes(self) -> None:
        self.pdf.add_page()
        self.sb.section_bar(f"راهنمای ساخت از صفر — {len(self.specs)} فرایند")
        for spec in self.specs:
            self._process_page(spec)

    def _render_ui_start_box(self, ui: UiStartGuide) -> None:
        self.sb.ok_box(
            f"نقطهٔ شروع UI | نوع: {ui.mode_fa}\n"
            f"حساب: {ui.account} ({ui.role_fa})\n"
            f"مسیر: {ui.menu_nav}\n"
            f"اولین کلیک: {ui.first_click}\n"
            f"نشانهٔ موفقیت: {ui.success_signal}\n"
            f"inbox خالی: {ui.empty_inbox_means}"
        )

    def _render_ui_gap_table(self) -> None:
        rows = [[q, "[ ]", "[ ]", ""] for q, _ in UI_GAP_CHECKLIST]
        self.sb.simple_table(
            headers=["سؤال کمبود UI", "بله", "خیر", "یادداشت"],
            rows=rows,
            col_widths=[88, 10, 10, 68],
            line_height=5.5,
        )

    def _build_scratch_state_row(self, st: StateTestSpec) -> list[str]:
        exp = state_expected_outcome(st.name_fa, st.is_automatic, st.role_fa)
        if len(exp) > 32:
            exp = exp[:32] + "…"
        task = st.operator_task_fa
        if len(task) > 50:
            task = task[:50] + "…"
        return [
            str(st.index),
            st.name_fa[:14],
            st.role_fa[:10],
            "[ ]",
            "[ ]",
            task,
            exp,
            st.gap_id[-16:] if len(st.gap_id) > 16 else st.gap_id,
            "",
        ]

    def _process_page(self, spec: ProcessTestSpec) -> None:
        self.pdf.add_page()
        self.sb.section_bar(f"#{spec.number} {spec.name_fa}")
        ui = derive_ui_start(spec)

        if spec.restart_blocked:
            self.sb.warn_box("غیرقابل ریست — یک‌بار از صفر تست کنید؛ گیرکرد = فقط GAP.")

        if ui.build_first:
            self.sb.body("ابتدا خودتان بسازید:", bold=True)
            for item in ui.build_first:
                self.sb.body(f"• {item}")

        self.sb.body("نقطهٔ شروع از UI", bold=True)
        self._render_ui_start_box(ui)

        self.sb.body("چک‌لیست کمبود UI (قبل از جدول مراحل):", bold=True)
        self._render_ui_gap_table()

        if spec.scheduler_note:
            self.sb.tip_box(spec.scheduler_note.replace("seed دمو", "ساخت دستی والد"))

        self.sb.body("جدول مراحل — ساخت گام‌به‌گام:", bold=True)
        self.sb.body(
            "ستون‌های UI: آیا منو/فرم این مرحله را دیدید؟ | آیا بدون راهنمای بیرونی فهمیدید چه کنید؟"
        )
        state_rows = [self._build_scratch_state_row(st) for st in spec.states]
        chunk = 8
        for i in range(0, len(state_rows), chunk):
            if i > 0:
                self.pdf.add_page()
                self.sb.section_bar(f"#{spec.number} {spec.name_fa} — مراحل (ادامه)")
            self.sb.simple_table(
                headers=[
                    "#",
                    "مرحله",
                    "نقش",
                    "UI؟",
                    "فهمیدم؟",
                    "اقدام",
                    "انتظار",
                    "GAP",
                    "یادداشت",
                ],
                rows=state_rows[i : i + chunk],
                col_widths=[6, 16, 12, 8, 10, 42, 28, 16, 20],
                fa_cols=[False, True, True, False, False, True, True, False, True],
                line_height=5.2,
                font_size=SMALL,
            )

        self.sb.blank_lines(
            "GAP این فرایند (شناسه / missing_step|UI|cross_process / انتظار / دیدم):",
            2,
        )

    def part_summary(self) -> None:
        self.pdf.add_page()
        self.sb.section_bar("خلاصه — آیا از UI قابل ساخت بود؟")
        rows = []
        for spec in self.specs:
            ui = derive_ui_start(spec)
            rows.append([
                str(spec.number),
                spec.name_fa[:20],
                ui.mode_fa[:16],
                "[ ]",
                "[ ]",
                "",
            ])
        chunk = 22
        for start in range(0, len(rows), chunk):
            if start > 0:
                self.pdf.add_page()
            self.sb.simple_table(
                headers=["#", "فرایند", "نوع شروع", "شروع UI", "تمام شد", "GAP"],
                rows=rows[start : start + chunk],
                col_widths=[10, 42, 28, 14, 14, 28],
                font_size=SMALL,
            )


def main() -> int:
    specs = build_process_specs()
    builder = FromScratchGuideBuilder(specs)
    builder.cover()
    builder.part_seed_policy()
    builder.part_methodology()
    builder.part_accounts_compact()
    builder.part_build_order()
    builder.part_all_processes()
    builder.part_summary()
    builder.save(OUT_PDF)
    print(f"PDF written: {OUT_PDF}")
    print(f"Pages: {builder.pdf.page_no()}")
    print(f"Size: {OUT_PDF.stat().st_size:,} bytes")
    print(f"Processes: {len(builder.specs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
