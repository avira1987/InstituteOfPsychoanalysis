"""therapy_sessions: add link_reminder_sent_at for pre-session online link SMS."""

from alembic import op
import sqlalchemy as sa


revision = "024_therapy_session_link_reminder"
down_revision = "023_sms_simulation_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "therapy_sessions",
        sa.Column("link_reminder_sent_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("therapy_sessions", "link_reminder_sent_at")
