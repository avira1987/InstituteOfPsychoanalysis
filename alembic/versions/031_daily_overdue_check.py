"""panel_task_reminders + daily_overdue_run_logs — موتور چک روزانه."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "031_daily_overdue_check"
down_revision = "030_institute_calendar"
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
    if _has_table(insp, "panel_task_reminders"):
        return

    op.create_table(
        "panel_task_reminders",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("title_fa", sa.String(length=500), nullable=False),
        sa.Column("summary_fa", sa.Text(), nullable=True),
        sa.Column("action_path", sa.String(length=1024), nullable=False),
        sa.Column("instance_id", sa.String(length=36), nullable=True),
        sa.Column("student_id", sa.String(length=36), nullable=True),
        sa.Column("process_code", sa.String(length=100), nullable=True),
        sa.Column("state_code", sa.String(length=100), nullable=True),
        sa.Column("responsible_role_code", sa.String(length=50), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("run_date_tehran", sa.Date(), nullable=False),
        sa.Column("sms_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fingerprint", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["instance_id"], ["process_instances.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fingerprint", name="uq_panel_task_reminders_fingerprint"),
    )
    op.create_index("ix_panel_task_reminders_user", "panel_task_reminders", ["user_id"])
    op.create_index("ix_panel_task_reminders_run_date", "panel_task_reminders", ["run_date_tehran"])

    op.create_table(
        "daily_overdue_run_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_date_tehran", sa.Date(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tasks_found", sa.Integer(), nullable=False),
        sa.Column("sms_sent", sa.Integer(), nullable=False),
        sa.Column("notifications_created", sa.Integer(), nullable=False),
        sa.Column("skipped_dedup", sa.Integer(), nullable=False),
        sa.Column("errors_json", sa.JSON(), nullable=True),
        sa.Column("triggered_by", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_daily_overdue_run_logs_date", "daily_overdue_run_logs", ["run_date_tehran"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not _has_table(insp, "panel_task_reminders"):
        return
    op.drop_index("ix_daily_overdue_run_logs_date", table_name="daily_overdue_run_logs")
    op.drop_table("daily_overdue_run_logs")
    op.drop_index("ix_panel_task_reminders_run_date", table_name="panel_task_reminders")
    op.drop_index("ix_panel_task_reminders_user", table_name="panel_task_reminders")
    op.drop_table("panel_task_reminders")
