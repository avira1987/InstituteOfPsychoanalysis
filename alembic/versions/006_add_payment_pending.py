"""Add payment_pending table for gateway callback -> session_payment (BUILD_TODO § و).

Revision ID: 006_payment_pending
Revises: 005_add_avatar_url
Create Date: 2026-03-12

"""
from alembic import op
import sqlalchemy as sa

revision = "006_payment_pending"
down_revision = "005_avatar_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_pending",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("authority", sa.String(255), nullable=False),
        sa.Column("instance_id", sa.String(36), sa.ForeignKey("process_instances.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_payment_pending_authority", "payment_pending", ["authority"])


def downgrade() -> None:
    op.drop_index("ix_payment_pending_authority", table_name="payment_pending")
    op.drop_table("payment_pending")
