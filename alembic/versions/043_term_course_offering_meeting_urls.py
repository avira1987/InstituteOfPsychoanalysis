"""Add online/host meeting URLs to term_course_offerings."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "043_term_course_offering_meeting_urls"
down_revision = "042_financial_ledger_category"
branch_labels = None
depends_on = None


def _has_column(insp, table: str, column: str) -> bool:
    try:
        return column in {c["name"] for c in insp.get_columns(table)}
    except Exception:
        return False


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not _has_column(insp, "term_course_offerings", "online_meeting_url"):
        op.add_column(
            "term_course_offerings",
            sa.Column("online_meeting_url", sa.Text(), nullable=True),
        )
    if not _has_column(insp, "term_course_offerings", "host_meeting_url"):
        op.add_column(
            "term_course_offerings",
            sa.Column("host_meeting_url", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if _has_column(insp, "term_course_offerings", "host_meeting_url"):
        op.drop_column("term_course_offerings", "host_meeting_url")
    if _has_column(insp, "term_course_offerings", "online_meeting_url"):
        op.drop_column("term_course_offerings", "online_meeting_url")
