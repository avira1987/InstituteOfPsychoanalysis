"""ذخیرهٔ رمز پورتال دانشجو (متن) برای نمایش در پنل ادمین پس از اولین ورود با پیامک."""

from alembic import op
import sqlalchemy as sa


revision = "018_users_portal_password_plain"
down_revision = "017_payment_gateway_receipts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # IF NOT EXISTS: با اتصال sync/async یا race در inspect، ستون حتماً ساخته می‌شود
    op.execute(
        sa.text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS portal_password_plain VARCHAR(128)"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS portal_password_plain"))
