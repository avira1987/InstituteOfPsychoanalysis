"""مهلت پرداخت برای رزرو اسلات مصاحبه (آزادسازی پس از انقضا)."""

from alembic import op
import sqlalchemy as sa


revision = "020_interview_slot_booking_deadline"
down_revision = "019_ensure_portal_password_plain"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "interview_slots",
        sa.Column("booking_payment_deadline_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_interview_slots_booking_deadline",
        "interview_slots",
        ["booking_payment_deadline_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_interview_slots_booking_deadline", table_name="interview_slots")
    op.drop_column("interview_slots", "booking_payment_deadline_at")
