"""term_course_offerings — دروس منتشرشده از آماده‌سازی ترم."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "035_term_course_offerings"
down_revision = "034_panel_action_notification_dismissals"
branch_labels = None
depends_on = None


def _has_table(insp, name) -> bool:
    try:
        return name in insp.get_table_names()
    except Exception:
        return False


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if _has_table(insp, "term_course_offerings"):
        return

    op.create_table(
        "term_course_offerings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("term_code", sa.String(length=50), nullable=False),
        sa.Column("course_code", sa.String(length=100), nullable=False),
        sa.Column("course_name_fa", sa.String(length=255), nullable=False),
        sa.Column("track", sa.String(length=100), nullable=True),
        sa.Column("program_kind", sa.String(length=50), nullable=False),
        sa.Column("term_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("day", sa.String(length=50), nullable=True),
        sa.Column("time_text", sa.String(length=50), nullable=True),
        sa.Column("classroom_location", sa.String(length=255), nullable=True),
        sa.Column("instructor_name", sa.String(length=255), nullable=True),
        sa.Column("teaching_assistant_name", sa.String(length=255), nullable=True),
        sa.Column("units", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("per_unit_cost_rial", sa.BigInteger(), nullable=True),
        sa.Column("prerequisite_codes", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_process_instance_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_process_instance_id"], ["process_instances.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "term_code",
            "course_code",
            "program_kind",
            "term_number",
            name="uq_term_course_offerings_term_prog_code",
        ),
    )
    op.create_index(
        "ix_term_course_offerings_term_prog",
        "term_course_offerings",
        ["term_code", "program_kind", "term_number"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not _has_table(insp, "term_course_offerings"):
        return
    op.drop_index("ix_term_course_offerings_term_prog", table_name="term_course_offerings")
    op.drop_table("term_course_offerings")
