"""payment_pending: gateway_track_id for SEP token / Zibal trackId lookup on callback."""

from alembic import op
import sqlalchemy as sa

revision = "013_payment_pending_gateway_track"
down_revision = "012_alocom_therapy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IF NOT EXISTS: روی دیتابیس‌هایی که از create_all یا نسخهٔ قدیمی آمده‌اند بدون شکستن اجرا شود
    op.execute(
        sa.text(
            "ALTER TABLE payment_pending ADD COLUMN IF NOT EXISTS gateway_track_id VARCHAR(255)"
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_payment_pending_gateway_track_id "
            "ON payment_pending (gateway_track_id)"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_payment_pending_gateway_track_id"))
    op.execute(sa.text("ALTER TABLE payment_pending DROP COLUMN IF EXISTS gateway_track_id"))
