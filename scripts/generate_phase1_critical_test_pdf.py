#!/usr/bin/env python3
"""
تولید PDF فاز ۱ — فرایندهای حیاتی (تست سریع ساخت از صفر).

اجرا:
  python scripts/generate_phase1_critical_test_pdf.py

خروجی:
  docs/راهنمای_تست_فاز۱_فرایندهای_حیاتی.pdf
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

from scripts.generate_from_scratch_test_pdf import FromScratchGuideBuilder
from scripts.lib.pdf_fa_utils import BODY, SMALL, TITLE, fa
from scripts.lib.process_test_guide_data import (
    PHASE_1_CRITICAL,
    build_process_specs,
    derive_ui_start,
    filter_phase1_specs,
)

OUT_PDF = ROOT / "docs" / "راهنمای_تست_فاز۱_فرایندهای_حیاتی.pdf"


class Phase1GuideBuilder(FromScratchGuideBuilder):
    def __init__(self, specs, phase_meta: list[tuple[str, str]]) -> None:
        super().__init__(specs)
        self.phase_meta = phase_meta
        self.pdf._footer_label = "فاز ۱ — فرایندهای حیاتی — انستیتو"

    def cover(self) -> None:
        p = self.pdf
        p.add_page()
        p.set_font("Vazir", "B", TITLE)
        p.ln(6)
        p.cell(
            0,
            12,
            fa("فاز ۱ — تست فرایندهای حیاتی (ساخت از صفر)"),
            align="C",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        p.set_font("Vazir", "", 11)
        p.cell(
            0,
            9,
            fa(f"{len(self.specs)} فرایند حیاتی — برای تست سریع با اپراتور غیرفنی"),
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
                "این سند فقط قلب مجموعه را پوشش می‌دهد. "
                "فرایندهای فرعی و جزئی در فاز ۲ و ۳ می‌آیند. "
                "فقط seed_all_roles بزنید — seed پرونده نزنید. "
                "هر فرایند را خودتان از UI بسازید."
            ),
            align="R",
        )
        for label in ("نام تست‌کننده", "تاریخ", "آدرس سایت", "هدف زمانی (مثلاً ۵–۱۰ روز)"):
            p.cell(0, 8, fa(f"{label}: ________________________"), align="R", new_x="LMARGIN", new_y="NEXT")
        self.sb.warn_box(
            "فاز ۱ تمام شد؟ جمع‌بندی GAPها را بفرستید. "
            "بعد از رفع مشکلات حیاتی به فاز ۲ (فرایندهای مهم وابسته) بروید."
        )

    def part_phase_overview(self) -> None:
        self.pdf.add_page()
        self.sb.section_bar("فاز ۱ — چرا این فرایندها؟")
        self.sb.body(
            "این لیست برای این است که با یک نفر غیرفنی در کمترین زمان بفهمید "
            "آیا مسیرهای اصلی انستیتو از UI قابل ساخت است. "
            "ترتیب زیر را رعایت کنید — هر ردیف به قبلی وابسته است."
        )
        rows = []
        for i, (code, why) in enumerate(self.phase_meta, 1):
            spec = self.by_code.get(code)
            name = spec.name_fa[:24] if spec else code
            ui = derive_ui_start(spec) if spec else None
            rows.append([
                str(i),
                name,
                why[:42] + ("…" if len(why) > 42 else ""),
                (ui.account if ui else "")[:12],
                "[ ]",
            ])
        self.sb.simple_table(
            headers=["#", "فرایند حیاتی", "چرا مهم است", "حساب", "تست شد"],
            rows=rows,
            col_widths=[8, 32, 68, 18, 12],
            font_size=SMALL,
            line_height=5.2,
        )
        self.sb.tip_box(
            f"معیار پایان فاز ۱: هر {len(self.specs)} فرایند یک‌بار از صفر طی شده "
            "یا GAP ثبت شده — حتی اگر «خیر» بود."
        )

    def part_build_order(self) -> None:
        self.pdf.add_page()
        self.sb.section_bar("ترتیب اجرای فاز ۱")
        self.sb.body(
            "فقط این ترتیب. پس از هر فرایند، چک‌لیست ۵ سؤال UI را پر کنید. "
            "اگر نتوانستید شروع کنید → GAP با missing_step یا UI."
        )
        rows = []
        for i, (code, _why) in enumerate(self.phase_meta, 1):
            spec = self.by_code.get(code)
            if not spec:
                continue
            ui = derive_ui_start(spec)
            rows.append([
                str(i),
                spec.name_fa[:22],
                ui.mode_fa[:18],
                ui.menu_nav[:28],
                "[ ]",
                "",
            ])
        self.sb.simple_table(
            headers=["#", "فرایند", "نوع شروع", "منو", "شدم", "یادداشت"],
            rows=rows,
            col_widths=[8, 30, 24, 38, 10, 28],
            font_size=SMALL,
            line_height=5.0,
        )

    def part_accounts_compact(self) -> None:
        super().part_accounts_compact()
        self.sb.body(
            "در فاز ۱ بیشتر با این حساب‌ها کار می‌کنید: "
            "deputy_education1، regdemo_intro_app، demo_admissions، demo_interviewer، "
            "student1، therapist1، supervision_committee1، progress_committee1.",
            bold=True,
        )


def main() -> int:
    all_specs = build_process_specs()
    phase_specs = filter_phase1_specs(all_specs)
    builder = Phase1GuideBuilder(phase_specs, PHASE_1_CRITICAL)
    builder.cover()
    builder.part_phase_overview()
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
    print(f"Phase-1 processes: {len(phase_specs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
