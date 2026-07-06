"""panel_flash_messages — ذخیرهٔ پیام‌های پاپ‌آپ UI در پنل اعلان‌ها."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "033_panel_flash_messages"
down_revision = "032_users_profile_meta"
branch_labels = None
depends_on = None


def _has_table(insp, name) -> bool:
    try:
        return name in insp.get_table_names()
    except Exception:
        return False


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if _has_table(insp, "panel_flash_messages"):
        return

    op.create_table(
        "panel_flash_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("source_path", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_panel_flash_messages_user", "panel_flash_messages", ["user_id"])
    op.create_index("ix_panel_flash_messages_created", "panel_flash_messages", ["created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not _has_table(insp, "panel_flash_messages"):
        return
    op.drop_index("ix_panel_flash_messages_created", table_name="panel_flash_messages")
    op.drop_index("ix_panel_flash_messages_user", table_name="panel_flash_messages")
    op.drop_table("panel_flash_messages")
