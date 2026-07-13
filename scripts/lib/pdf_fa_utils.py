"""Shared FPDF + Persian RTL utilities for operator test guide PDFs."""
from __future__ import annotations

from pathlib import Path

import arabic_reshaper
import jdatetime
from bidi.algorithm import get_display
from fpdf import FPDF
from fpdf.enums import Align, TableBordersLayout, TableCellFillMode, VAlign
from fpdf.fonts import FontFace

ROOT = Path(__file__).resolve().parent.parent.parent
ASSETS = ROOT / "app" / "assets" / "fonts"
FONT_REG = ASSETS / "Vazirmatn-Regular.ttf"
FONT_BOLD = ASSETS / "Vazirmatn-Bold.ttf"

MARGIN = 14
BODY = 9.5
SECTION = 11.5
TITLE = 15
SMALL = 8
TINY = 7.5

COLOR_SECTION_BG = (235, 241, 250)
COLOR_SECTION_TEXT = (30, 58, 95)
COLOR_BORDER = (209, 213, 219)
COLOR_STRIPE = (249, 250, 251)
COLOR_TIP_BG = (255, 251, 235)
COLOR_WARN_BG = (254, 242, 242)
COLOR_OK_BG = (240, 253, 244)


def fa(text: str) -> str:
    if not text:
        return ""
    t = str(text).replace("\r", " ").replace("\n", " ")
    t = t.replace("\u2192", " به ").replace("\u2610", "[ ]")
    try:
        return get_display(arabic_reshaper.reshape(t))
    except Exception:
        return t


def register_fonts(pdf: FPDF) -> None:
    if not FONT_REG.is_file():
        raise FileNotFoundError(f"فونت یافت نشد: {FONT_REG}")
    pdf.add_font("Vazir", "", str(FONT_REG))
    if FONT_BOLD.is_file():
        pdf.add_font("Vazir", "B", str(FONT_BOLD))


def heading_style() -> FontFace:
    return FontFace(
        family="Vazir",
        emphasis="BOLD",
        size_pt=SMALL,
        color=(30, 58, 95),
        fill_color=(220, 230, 245),
    )


class GuidePDF(FPDF):
    def __init__(self, footer_label: str = "راهنمای جامع تست فرایندها") -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self._footer_label = footer_label
        self._footer_ts = jdatetime.datetime.now().strftime("%Y/%m/%d")

    def footer(self) -> None:
        self.set_y(-10)
        self.set_font("Vazir", "", TINY)
        self.set_text_color(120, 120, 120)
        self.cell(
            0,
            5,
            fa(f"{self._footer_label} — {self._footer_ts} — صفحه {self.page_no()}"),
            align="C",
        )


class PdfSectionBuilder:
    """Reusable section helpers for Persian RTL guide PDFs."""

    def __init__(self, pdf: GuidePDF) -> None:
        self.pdf = pdf

    def ensure_space(self, h: float = 20) -> None:
        p = self.pdf
        if p.get_y() + h > p.h - 18:
            p.add_page()

    def section_bar(self, text: str) -> None:
        self.ensure_space(12)
        p = self.pdf
        p.set_fill_color(*COLOR_SECTION_BG)
        p.set_text_color(*COLOR_SECTION_TEXT)
        p.set_font("Vazir", "B", SECTION)
        p.cell(0, 9, fa(text), fill=True, align="R", new_x="LMARGIN", new_y="NEXT")
        p.set_text_color(30, 30, 30)
        p.ln(2)

    def body(self, text: str, bold: bool = False, size: float | None = None) -> None:
        p = self.pdf
        p.set_font("Vazir", "B" if bold else "", size or BODY)
        p.multi_cell(0, 5.8, fa(text), align="R")
        p.ln(1)

    def bullet_list(self, items: list[str]) -> None:
        for item in items:
            self.body(f"• {item}")

    def numbered_list(self, items: list[str]) -> None:
        for i, item in enumerate(items, 1):
            self.body(f"{i}. {item}")

    def tip_box(self, text: str) -> None:
        self.ensure_space(16)
        p = self.pdf
        p.set_fill_color(*COLOR_TIP_BG)
        p.set_font("Vazir", "B", BODY)
        p.multi_cell(0, 5.8, fa(f"نکته: {text}"), align="R", fill=True)
        p.ln(2)

    def warn_box(self, text: str) -> None:
        self.ensure_space(16)
        p = self.pdf
        p.set_fill_color(*COLOR_WARN_BG)
        p.set_font("Vazir", "B", BODY)
        p.multi_cell(0, 5.8, fa(f"توجه: {text}"), align="R", fill=True)
        p.ln(2)

    def ok_box(self, text: str) -> None:
        self.ensure_space(16)
        p = self.pdf
        p.set_fill_color(*COLOR_OK_BG)
        p.set_font("Vazir", "B", BODY)
        p.multi_cell(0, 5.8, fa(text), align="R", fill=True)
        p.ln(2)

    def blank_lines(self, label: str, n: int = 3) -> None:
        self.ensure_space(8 + n * 7)
        p = self.pdf
        p.set_font("Vazir", "B", BODY)
        p.cell(0, 6, fa(label), new_x="LMARGIN", new_y="NEXT")
        p.set_font("Vazir", "", BODY)
        p.set_draw_color(*COLOR_BORDER)
        for _ in range(n):
            y = p.get_y()
            p.line(MARGIN, y + 4, p.w - MARGIN, y + 4)
            p.ln(7)

    def simple_table(
        self,
        headers: list[str],
        rows: list[list[str]],
        col_widths: list[float] | None = None,
        fa_cols: list[bool] | None = None,
        line_height: float = 5.0,
        font_size: float | None = None,
    ) -> None:
        self.ensure_space(12 + len(rows) * 6)
        p = self.pdf
        if font_size:
            p.set_font("Vazir", "", font_size)
        hs = heading_style()
        n_cols = len(headers)
        if col_widths is None:
            col_widths = [p.epw / n_cols] * n_cols
        if fa_cols is None:
            fa_cols = [True] * n_cols
        with p.table(
            col_widths=col_widths,
            width=p.epw,
            first_row_as_headings=False,
            text_align=Align.R,
            v_align=VAlign.M,
            line_height=line_height,
            borders_layout=TableBordersLayout.ALL,
            cell_fill_color=COLOR_STRIPE,
            cell_fill_mode=TableCellFillMode.ROWS,
            padding=1.2,
        ) as table:
            hr = table.row()
            for h in headers:
                hr.cell(fa(h), align=Align.C, style=hs)
            for row in rows:
                r = table.row()
                for j, cell in enumerate(row):
                    use_fa = fa_cols[j] if j < len(fa_cols) else True
                    text = fa(cell) if use_fa and cell else (cell or "")
                    align = Align.C if j > 0 and len(cell) < 14 and not use_fa else Align.R
                    r.cell(text, align=align)
        p.ln(2)
        if font_size:
            p.set_font("Vazir", "", BODY)

    def check_table(self, questions: list[str]) -> None:
        self.ensure_space(12 + len(questions) * 6)
        p = self.pdf
        hs = heading_style()
        rows = [[fa("سؤال"), fa("بله"), fa("خیر"), fa("توضیح کوتاه")]]
        for q in questions:
            rows.append([fa(q), "", "", ""])
        with p.table(
            col_widths=(88, 11, 11, 70),
            width=p.epw,
            first_row_as_headings=False,
            text_align=Align.R,
            v_align=VAlign.M,
            line_height=5.5,
            borders_layout=TableBordersLayout.ALL,
            cell_fill_color=COLOR_STRIPE,
            cell_fill_mode=TableCellFillMode.ROWS,
            padding=1.5,
        ) as table:
            for i, row in enumerate(rows):
                r = table.row()
                for j, cell in enumerate(row):
                    style = hs if i == 0 and j == 0 else None
                    r.cell(cell, align=Align.R if j == 0 else Align.C, style=style)
        p.ln(2)
