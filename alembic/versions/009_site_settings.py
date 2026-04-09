"""جدول site_settings برای تنظیمات اقساط و مشابه."""

from alembic import op
import sqlalchemy as sa

revision = "009_site_settings"
down_revision = "008_student_is_sample_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "site_settings",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("site_settings")
