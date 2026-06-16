"""interview_slots: host_meeting_link for admin/interviewer Alocom join."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "027_interview_slot_host_meeting_link"
down_revision = "026_production_hardening"
branch_labels = None
depends_on = None


def _has_col(insp, table, col) -> bool:
    try:
        return col in {c["name"] for c in insp.get_columns(table)}
    except Exception:
        return False


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    if not _has_col(insp, "interview_slots", "host_meeting_link"):
        op.add_column(
            "interview_slots",
            sa.Column("host_meeting_link", sa.Text(), nullable=True),
        )
    if not _has_col(insp, "interview_slots", "interviewer_meeting_link"):
        op.add_column(
            "interview_slots",
            sa.Column("interviewer_meeting_link", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("interview_slots", "interviewer_meeting_link")
    op.drop_column("interview_slots", "host_meeting_link")
