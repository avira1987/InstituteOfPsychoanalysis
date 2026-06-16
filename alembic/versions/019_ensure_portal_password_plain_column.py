"""تضمین وجود ستون portal_password_plain (ترمیم اگر 018 بدون ستون ثبت شده باشد)."""

from alembic import op
import sqlalchemy as sa


revision = "019_ensure_portal_password_plain"
down_revision = "018_users_portal_password_plain"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS portal_password_plain VARCHAR(128)"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("ALTER TABLE users DROP COLUMN IF EXISTS portal_password_plain"))
