"""institute_calendars — تقویم آموزشی فعال برای تریگرهای زمان‌محور."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "030_institute_calendar"
down_revision = "029_sms_outbox_process_context"
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
    if _has_table(insp, "institute_calendars"):
        return

    op.create_table(
        "institute_calendars",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("term_code", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("term_start_date", sa.Date(), nullable=True),
        sa.Column("term_end_date", sa.Date(), nullable=True),
        sa.Column("registration_open_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("registration_deadline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evaluation_open_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evaluation_close_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by", sa.String(length=36), nullable=True),
        sa.Column("source_process_instance_id", sa.String(length=36), nullable=True),
        sa.Column("extra_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["published_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["source_process_instance_id"], ["process_instances.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("term_code"),
    )
    op.create_index("ix_institute_calendars_active", "institute_calendars", ["is_active"])
    op.create_index("ix_institute_calendars_term_code", "institute_calendars", ["term_code"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not _has_table(insp, "institute_calendars"):
        return
    op.drop_index("ix_institute_calendars_term_code", table_name="institute_calendars")
    op.drop_index("ix_institute_calendars_active", table_name="institute_calendars")
    op.drop_table("institute_calendars")
