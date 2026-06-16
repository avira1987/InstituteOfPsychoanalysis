"""payment_pending: gateway_provider برای verify زرین‌پال/زیبال در callback."""

from alembic import op
import sqlalchemy as sa


revision = "016_payment_pending_gateway_provider"
down_revision = "015_interview_slot_interviewer_user"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "payment_pending",
        sa.Column("gateway_provider", sa.String(32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("payment_pending", "gateway_provider")
