"""Alocom: therapy_sessions event id + start time; users.alocom_agent_user_id."""

from alembic import op
import sqlalchemy as sa

revision = "012_alocom_therapy"
down_revision = "011_alembic_ver64"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("therapy_sessions", sa.Column("alocom_event_id", sa.String(80), nullable=True))
    op.add_column(
        "therapy_sessions",
        sa.Column("session_starts_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_therapy_sessions_alocom_event_id", "therapy_sessions", ["alocom_event_id"])

    op.add_column("users", sa.Column("alocom_agent_user_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "alocom_agent_user_id")
    op.drop_index("ix_therapy_sessions_alocom_event_id", table_name="therapy_sessions")
    op.drop_column("therapy_sessions", "session_starts_at")
    op.drop_column("therapy_sessions", "alocom_event_id")
