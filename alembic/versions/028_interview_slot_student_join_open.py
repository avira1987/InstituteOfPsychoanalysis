"""interview_slots: student_join_open gate for early student meeting access."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "028_interview_slot_student_join_open"
down_revision = "027_interview_slot_host_meeting_link"
branch_labels = None
depends_on = None


def _has_col(insp, table, col) -> bool:
    try:
        return col in {c["name"] for c in insp.get_columns(table)}
    except Exception:
        return False


def upgrade() -> None:
    conn = op.get_bind()
    insp = inspect(conn)
    if not _has_col(insp, "interview_slots", "student_join_open"):
        op.add_column(
            "interview_slots",
            sa.Column(
                "student_join_open",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade() -> None:
    conn = op.get_bind()
    insp = inspect(conn)
    if _has_col(insp, "interview_slots", "student_join_open"):
        op.drop_column("interview_slots", "student_join_open")
