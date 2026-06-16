"""interview_slots: add alocom_event_id for online interview provisioning."""

from alembic import op
import sqlalchemy as sa


revision = "021_interview_slot_alocom_event"
down_revision = "020_interview_slot_booking_deadline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "interview_slots",
        sa.Column("alocom_event_id", sa.String(length=80), nullable=True),
    )
    op.create_index(
        "ix_interview_slots_alocom_event_id",
        "interview_slots",
        ["alocom_event_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_interview_slots_alocom_event_id", table_name="interview_slots")
    op.drop_column("interview_slots", "alocom_event_id")
