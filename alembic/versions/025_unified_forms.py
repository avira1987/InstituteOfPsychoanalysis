"""فرم یکپارچه: ستون‌های منبع/وضعیت فیلد + جداول فایل و منابع پویا."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "025_unified_forms"
down_revision = "024_therapy_session_link_reminder"
branch_labels = None
depends_on = None


def _guid():
    return sa.String(36)


def _has_col(insp, table, col) -> bool:
    try:
        return col in {c["name"] for c in insp.get_columns(table)}
    except Exception:
        return False


def _has_table(insp, table) -> bool:
    return table in insp.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    # form_template_versions: source / process_code / state_code
    if _has_table(insp, "form_template_versions"):
        if not _has_col(insp, "form_template_versions", "source"):
            op.add_column(
                "form_template_versions",
                sa.Column("source", sa.String(16), nullable=False, server_default="manual"),
            )
        if not _has_col(insp, "form_template_versions", "process_code"):
            op.add_column("form_template_versions", sa.Column("process_code", sa.String(100), nullable=True))
        if not _has_col(insp, "form_template_versions", "state_code"):
            op.add_column("form_template_versions", sa.Column("state_code", sa.String(100), nullable=True))

    # form_assignments: submit_label_fa / header_fa
    if _has_table(insp, "form_assignments"):
        if not _has_col(insp, "form_assignments", "submit_label_fa"):
            op.add_column("form_assignments", sa.Column("submit_label_fa", sa.String(255), nullable=True))
        if not _has_col(insp, "form_assignments", "header_fa"):
            op.add_column("form_assignments", sa.Column("header_fa", sa.String(255), nullable=True))

    # form_responses: field_status / edit_unlocked_fields / locked_at
    if _has_table(insp, "form_responses"):
        if not _has_col(insp, "form_responses", "field_status"):
            op.add_column("form_responses", sa.Column("field_status", sa.JSON(), nullable=True))
        if not _has_col(insp, "form_responses", "edit_unlocked_fields"):
            op.add_column("form_responses", sa.Column("edit_unlocked_fields", sa.JSON(), nullable=True))
        if not _has_col(insp, "form_responses", "locked_at"):
            op.add_column("form_responses", sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True))

    # جدول فایل‌های فیلد
    if not _has_table(insp, "form_field_files"):
        op.create_table(
            "form_field_files",
            sa.Column("id", _guid(), primary_key=True),
            sa.Column("response_id", _guid(), sa.ForeignKey("form_responses.id", ondelete="CASCADE"), nullable=False),
            sa.Column("field_name", sa.String(120), nullable=False),
            sa.Column("file_name", sa.String(512), nullable=False),
            sa.Column("url", sa.String(1024), nullable=False),
            sa.Column("mime_type", sa.String(120), nullable=True),
            sa.Column("size", sa.Integer(), nullable=True),
            sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_form_field_files_response", "form_field_files", ["response_id"])

    # رجیستری منابع پویا
    if not _has_table(insp, "form_dynamic_sources"):
        op.create_table(
            "form_dynamic_sources",
            sa.Column("key", sa.String(80), primary_key=True),
            sa.Column("resolver", sa.String(120), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if _has_table(insp, "form_dynamic_sources"):
        op.drop_table("form_dynamic_sources")
    if _has_table(insp, "form_field_files"):
        op.drop_index("ix_form_field_files_response", table_name="form_field_files")
        op.drop_table("form_field_files")
    if _has_table(insp, "form_responses"):
        for col in ("locked_at", "edit_unlocked_fields", "field_status"):
            if _has_col(insp, "form_responses", col):
                op.drop_column("form_responses", col)
    if _has_table(insp, "form_assignments"):
        for col in ("header_fa", "submit_label_fa"):
            if _has_col(insp, "form_assignments", col):
                op.drop_column("form_assignments", col)
    if _has_table(insp, "form_template_versions"):
        for col in ("state_code", "process_code", "source"):
            if _has_col(insp, "form_template_versions", col):
                op.drop_column("form_template_versions", col)
