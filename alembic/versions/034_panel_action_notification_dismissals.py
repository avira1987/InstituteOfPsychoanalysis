"""panel_action_notification_dismissals — بستن دستی اعلان‌های اقدام."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "034_panel_action_notification_dismissals"
down_revision = "033_panel_flash_messages"
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
    if _has_table(insp, "panel_action_notification_dismissals"):
        return

    op.create_table(
        "panel_action_notification_dismissals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("notification_id", sa.String(length=255), nullable=False),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "notification_id", name="uq_panel_notif_dismiss_user_nid"),
    )
    op.create_index(
        "ix_panel_notif_dismiss_user",
        "panel_action_notification_dismissals",
        ["user_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not _has_table(insp, "panel_action_notification_dismissals"):
        return
    op.drop_index("ix_panel_notif_dismiss_user", table_name="panel_action_notification_dismissals")
    op.drop_table("panel_action_notification_dismissals")
