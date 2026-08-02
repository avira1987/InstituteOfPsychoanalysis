"""On-demand PDF generation for student transcripts, certificates, and related artifacts."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

import arabic_reshaper
import jdatetime
from bidi.algorithm import get_display
from fpdf import FPDF
from fpdf.enums import Align, TableBordersLayout, TableCellFillMode, VAlign
from fpdf.fonts import FontFace

from app.models.operational_models import Student, User

_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_FONT_REG = _ASSETS_DIR / "Vazirmatn-Regular.ttf"
_FONT_BOLD = _ASSETS_DIR / "Vazirmatn-Bold.ttf"

_INSTITUTE_NAME = "انستیتو روانکاوی تهران"

_DOC_TYPE_TITLES = {
    "term_transcript": "کارنامه ترم",
    "cumulative_transcript": "کارنامه کل",
    "certificate": "گواهی پایان دوره",
    "pdf_export": "خروجی رسمی کارنامه",
    "decline_list": "فهرست انصراف / عدم احراز",
    "termination_letter": "نامه خاتمه",
}

_MARGIN = 14
_BODY = 10
_TITLE = 14
_SMALL = 8
_TINY = 7


def _fa(text: Any) -> str:
    if text is None:
        return ""
    t = str(text).replace("\r", " ").replace("\n", " ")
    try:
        return get_display(arabic_reshaper.reshape(t))
    except Exception:
        return t


def _fa_multiline(text: Any) -> str:
    if text is None:
        return ""
    lines = str(text).replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(_fa(line) for line in lines)


def _register_fonts(pdf: FPDF) -> None:
    if not _FONT_REG.is_file():
        raise FileNotFoundError(f"فونت یافت نشد: {_FONT_REG}")
    pdf.add_font("Vazir", "", str(_FONT_REG))
    if _FONT_BOLD.is_file():
        pdf.add_font("Vazir", "B", str(_FONT_BOLD))


def _heading_style() -> FontFace:
    return FontFace(
        family="Vazir",
        emphasis="BOLD",
        size_pt=_SMALL,
        color=(30, 58, 95),
        fill_color=(220, 230, 245),
    )


def _cell_str(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        if v == int(v):
            return str(int(v))
        return str(round(v, 2))
    s = str(v).strip()
    return s if s else "—"


def _student_display_name(student: Student, user: Optional[User] = None) -> str:
    extra = student.extra_data if isinstance(student.extra_data, dict) else {}
    first = (extra.get("first_name_fa") or "").strip()
    last = (extra.get("last_name_fa") or "").strip()
    if first or last:
        return f"{first} {last}".strip()
    if user and (user.full_name_fa or "").strip():
        return str(user.full_name_fa).strip()
    return str(getattr(student, "student_code", "—") or "—")


def _shamsi_today() -> str:
    return jdatetime.datetime.now().strftime("%Y/%m/%d")


def artifact_pdf_filename(doc: dict, student: Student) -> str:
    doc_type = doc.get("type") or "document"
    code = getattr(student, "student_code", None) or "student"
    title = _DOC_TYPE_TITLES.get(doc_type, doc.get("title_fa") or doc_type)
    pdf_ctx = doc.get("pdf_context") if isinstance(doc.get("pdf_context"), dict) else {}
    term = pdf_ctx.get("term_code") or getattr(student, "current_term", None)
    safe_code = re.sub(r"[^\w\-]+", "_", str(code))
    if doc_type == "term_transcript" and term:
        return f"transcript-term-{term}-{safe_code}.pdf"
    if doc_type == "cumulative_transcript":
        return f"transcript-cumulative-{safe_code}.pdf"
    if doc_type == "certificate":
        return f"certificate-{safe_code}.pdf"
    slug = re.sub(r"\s+", "-", title)
    return f"{slug}-{safe_code}.pdf"


class ArtifactPDF(FPDF):
    def __init__(self, *, footer_label: str, student_code: str) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self._footer_label = footer_label
        self._student_code = student_code
        self._footer_ts = _shamsi_today()

    def footer(self) -> None:
        self.set_y(-10)
        self.set_font("Vazir", "", _TINY)
        self.set_text_color(120, 120, 120)
        self.cell(
            0,
            5,
            _fa(
                f"{self._footer_label} — کد دانشجو: {self._student_code} — "
                f"{self._footer_ts} — صفحه {self.page_no()}"
            ),
            align="C",
        )


class _ArtifactPdfBuilder:
    def __init__(self, student: Student, doc: dict, user: Optional[User] = None) -> None:
        self.student = student
        self.doc = doc
        self.user = user
        self.pdf_ctx = doc.get("pdf_context") if isinstance(doc.get("pdf_context"), dict) else {}
        doc_type = doc.get("type") or "document"
        title = doc.get("title_fa") or _DOC_TYPE_TITLES.get(doc_type, doc_type)
        self.pdf = ArtifactPDF(
            footer_label=title,
            student_code=str(getattr(student, "student_code", "—") or "—"),
        )
        _register_fonts(self.pdf)
        self.pdf.set_auto_page_break(auto=True, margin=16)
        self.pdf.set_margins(_MARGIN, _MARGIN, _MARGIN)
        self.pdf.add_page()
        self.pdf.set_font("Vazir", "", _BODY)

    def _ensure_space(self, h: float = 20) -> None:
        if self.pdf.get_y() + h > self.pdf.h - 18:
            self.pdf.add_page()

    def _header_block(self, title: str) -> None:
        p = self.pdf
        p.set_font("Vazir", "B", _TITLE)
        p.set_text_color(30, 58, 95)
        p.cell(0, 10, _fa(_INSTITUTE_NAME), align="C", new_x="LMARGIN", new_y="NEXT")
        p.set_font("Vazir", "B", 12)
        p.cell(0, 8, _fa(title), align="C", new_x="LMARGIN", new_y="NEXT")
        p.ln(3)
        p.set_text_color(30, 30, 30)

    def _meta_lines(self, lines: list[str]) -> None:
        p = self.pdf
        p.set_font("Vazir", "", _BODY)
        for line in lines:
            p.set_x(p.l_margin)
            p.multi_cell(p.epw, 6, _fa(line), align="R")
        p.ln(2)

    def _simple_table(self, headers: list[str], rows: list[list[str]]) -> None:
        self._ensure_space(12 + len(rows) * 6)
        p = self.pdf
        hs = _heading_style()
        n_cols = len(headers)
        col_widths = [p.epw / n_cols] * n_cols
        with p.table(
            col_widths=col_widths,
            width=p.epw,
            first_row_as_headings=False,
            text_align=Align.R,
            v_align=VAlign.M,
            line_height=5.5,
            borders_layout=TableBordersLayout.ALL,
            cell_fill_color=(249, 250, 251),
            cell_fill_mode=TableCellFillMode.ROWS,
            padding=1.2,
        ) as table:
            hr = table.row()
            for h in headers:
                hr.cell(_fa(h), align=Align.C, style=hs)
            for row in rows:
                r = table.row()
                for j, cell in enumerate(row):
                    align = Align.C if j > 0 else Align.R
                    r.cell(_fa(cell), align=align)
        p.ln(2)

    def _body_paragraph(self, text: str, *, bold: bool = False, size: float | None = None) -> None:
        p = self.pdf
        p.set_font("Vazir", "B" if bold else "", size or _BODY)
        p.set_x(p.l_margin)
        p.multi_cell(p.epw, 6.5, _fa_multiline(text), align="R")
        p.ln(1)

    def _signature_block(self, signed_by: str, *, signed: bool) -> None:
        self._ensure_space(28)
        p = self.pdf
        p.ln(4)
        if signed:
            p.set_font("Vazir", "", _SMALL)
            p.multi_cell(0, 5.5, _fa("این سند به‌صورت الکترونیکی امضا و مهر شده است."), align="R")
        p.ln(6)
        p.set_font("Vazir", "B", _BODY)
        p.cell(0, 6, _fa(f"امضا: {signed_by or '—'}"), align="L")

    def build(self) -> bytes:
        doc_type = self.doc.get("type") or ""
        title = self.doc.get("title_fa") or _DOC_TYPE_TITLES.get(doc_type, doc_type)
        if doc_type in ("term_transcript", "cumulative_transcript"):
            self._render_transcript(doc_type, title)
        elif doc_type == "certificate":
            self._render_certificate(title)
        elif doc_type == "pdf_export":
            self._render_pdf_export(title)
        elif doc_type == "decline_list":
            self._render_decline_list(title)
        elif doc_type == "termination_letter":
            self._render_termination_letter(title)
        else:
            self._render_fallback(title)
        raw = self.pdf.output()
        return bytes(raw) if isinstance(raw, bytearray) else raw

    def _student_meta(self) -> list[str]:
        name = _student_display_name(self.student, self.user)
        code = getattr(self.student, "student_code", "—")
        course = getattr(self.student, "course_type", "—")
        term = self.pdf_ctx.get("term_code") or getattr(self.student, "current_term", "—")
        return [
            f"نام و نام خانوادگی: {name}",
            f"کد دانشجو: {code}",
            f"دوره: {course}",
            f"ترم: {term}",
        ]

    def _render_transcript(self, doc_type: str, title: str) -> None:
        self._header_block(title)
        self._meta_lines(self._student_meta())
        rows_data = self.pdf_ctx.get("term_transcript_rows") or []
        table_rows: list[list[str]] = []
        for row in rows_data:
            if not isinstance(row, dict):
                continue
            table_rows.append(
                [
                    _cell_str(row.get("course_name")),
                    _cell_str(row.get("units")),
                    _cell_str(row.get("numeric_grade")),
                    _cell_str(row.get("letter_grade")),
                    _cell_str(row.get("pass_fail_status")),
                ]
            )
        if table_rows:
            self._simple_table(
                ["نام درس", "واحد", "نمره عددی", "نمره حرفی", "وضعیت"],
                table_rows,
            )
        term_gpa = self.pdf_ctx.get("term_gpa")
        cumulative_gpa = self.pdf_ctx.get("cumulative_gpa")
        if term_gpa is not None:
            self._body_paragraph(f"معدل ترم: {_cell_str(term_gpa)}", bold=True)
        if doc_type == "cumulative_transcript" and cumulative_gpa is not None:
            self._body_paragraph(f"معدل کل: {_cell_str(cumulative_gpa)}", bold=True)
        if not table_rows:
            self._body_paragraph(self.doc.get("body_fa") or "—")

    def _render_certificate(self, title: str) -> None:
        self._header_block(title)
        text = (
            self.pdf_ctx.get("certificate_text_resolved")
            or self.doc.get("body_fa")
            or "—"
        )
        self._body_paragraph(text, size=11)
        signed_by = self.pdf_ctx.get("signed_by") or ""
        self._signature_block(signed_by, signed=bool(self.doc.get("signed")))

    def _render_pdf_export(self, title: str) -> None:
        self._header_block(title)
        self._meta_lines(self._student_meta())
        rows_data = self.pdf_ctx.get("term_transcript_rows") or []
        if rows_data:
            self._body_paragraph("خلاصه نمرات ترم جاری", bold=True)
            table_rows = [
                [
                    _cell_str(r.get("course_name")),
                    _cell_str(r.get("units")),
                    _cell_str(r.get("numeric_grade")),
                    _cell_str(r.get("pass_fail_status")),
                ]
                for r in rows_data
                if isinstance(r, dict)
            ]
            self._simple_table(["نام درس", "واحد", "نمره", "وضعیت"], table_rows)
        term_gpa = self.pdf_ctx.get("term_gpa")
        cumulative_gpa = self.pdf_ctx.get("cumulative_gpa")
        summary_lines = []
        if term_gpa is not None:
            summary_lines.append(f"معدل ترم: {_cell_str(term_gpa)}")
        if cumulative_gpa is not None:
            summary_lines.append(f"معدل کل: {_cell_str(cumulative_gpa)}")
        if summary_lines:
            self._meta_lines(summary_lines)
        if not rows_data:
            self._body_paragraph(self.doc.get("body_fa") or "—")

    def _render_decline_list(self, title: str) -> None:
        self._header_block(title)
        self._meta_lines(self._student_meta())
        failed = self.pdf_ctx.get("failed_courses") or []
        if failed:
            self._body_paragraph("دروس مردود / نیازمند پیگیری:", bold=True)
            for name in failed:
                self._body_paragraph(f"• {_cell_str(name)}")
        else:
            self._body_paragraph(self.doc.get("body_fa") or "—")

    def _render_termination_letter(self, title: str) -> None:
        self._header_block(title)
        self._meta_lines(self._student_meta())
        reason = self.pdf_ctx.get("termination_reason_fa") or self.pdf_ctx.get("reason_fa") or "—"
        self._body_paragraph(
            f"به استحضار می‌رساند فرایند تحصیلی دانشجوی فوق به علت «{reason}» خاتمه یافته است.",
            size=11,
        )
        if self.doc.get("body_fa"):
            self._body_paragraph(self.doc.get("body_fa"))

    def _render_fallback(self, title: str) -> None:
        self._header_block(title)
        self._meta_lines(self._student_meta())
        self._body_paragraph(self.doc.get("body_fa") or "—")


def render_student_document_pdf(
    student: Student,
    doc: dict,
    *,
    user: Optional[User] = None,
) -> bytes:
    """Build PDF bytes for a student artifact document record."""
    builder = _ArtifactPdfBuilder(student, doc, user=user)
    return builder.build()


def interpolate_certificate_text(
    template: str,
    *,
    student: Student,
    user: Optional[User] = None,
    ctx: Optional[dict] = None,
    hours_formula: Optional[str] = None,
) -> str:
    """Replace {placeholders} in certificate_text_fa."""
    extra = student.extra_data if isinstance(student.extra_data, dict) else {}
    context = ctx if isinstance(ctx, dict) else {}
    name = _student_display_name(student, user)
    id_number = (extra.get("birth_certificate_number") or context.get("id_number") or "—")
    national_code = (extra.get("national_code") or context.get("national_code") or "—")
    completion_date = (
        context.get("completion_date")
        or context.get("completionDate")
        or _shamsi_today()
    )
    total_units_raw = context.get("total_units") or context.get("totalUnits")
    try:
        total_units = int(float(total_units_raw)) if total_units_raw not in (None, "") else 10
    except (TypeError, ValueError):
        total_units = 10
    total_hours_raw = context.get("total_hours") or context.get("totalHours")
    if total_hours_raw not in (None, ""):
        try:
            total_hours = float(total_hours_raw)
        except (TypeError, ValueError):
            total_hours = total_units * 13.5
    elif hours_formula:
        m = re.match(r"^total_units\s*\*\s*([\d.]+)\s*$", str(hours_formula).strip())
        if m:
            try:
                total_hours = total_units * float(m.group(1))
            except (TypeError, ValueError):
                total_hours = total_units * 13.5
        else:
            total_hours = total_units * 13.5
    else:
        total_hours = total_units * 13.5
    if total_hours == int(total_hours):
        total_hours_str = str(int(total_hours))
    else:
        total_hours_str = str(round(float(total_hours), 1))

    replacements = {
        "student_name": name,
        "id_number": str(id_number),
        "national_code": str(national_code),
        "completion_date": str(completion_date),
        "total_units": str(total_units),
        "total_hours": total_hours_str,
    }
    out = template or ""
    for key, val in replacements.items():
        out = out.replace(f"{{{key}}}", val)
    return out
