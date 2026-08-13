"""panel_flash_messages.category — جداسازی پاپ‌آپ و پیام سیستم."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "040_panel_flash_message_category"
down_revision = "039_users_roles"
branch_labels = None
depends_on = None


def _has_column(insp, table: str, column: str) -> bool:
    try:
        return column in {c["name"] for c in insp.get_columns(table)}
    except Exception:
        return False


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not _has_column(insp, "panel_flash_messages", "category"):
        op.add_column(
            "panel_flash_messages",
            sa.Column("category", sa.String(length=20), nullable=False, server_default="popup"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if _has_column(insp, "panel_flash_messages", "category"):
        op.drop_column("panel_flash_messages", "category")
