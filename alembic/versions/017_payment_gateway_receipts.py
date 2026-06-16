"""تک‌مصرف درگاه: payment_gateway_receipts (refNumber زیبال و …)."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "017_payment_gateway_receipts"
down_revision = "016_payment_pending_gateway_provider"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "payment_gateway_receipts" in (insp.get_table_names() or ()):
        return
    op.create_table(
        "payment_gateway_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("gateway_ref", sa.String(128), nullable=False),
        sa.Column("authority", sa.String(255), nullable=True),
        sa.Column("amount_rial", sa.BigInteger(), nullable=False),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("process_instance_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["process_instance_id"], ["process_instances.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("provider", "gateway_ref", name="uq_pgr_provider_ref"),
    )
    op.create_index("ix_pgr_student_id", "payment_gateway_receipts", ["student_id"])


def downgrade() -> None:
    op.drop_index("ix_pgr_student_id", table_name="payment_gateway_receipts")
    op.drop_table("payment_gateway_receipts")
