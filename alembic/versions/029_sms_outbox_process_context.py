"""sms_simulation_outbox: optional process context for popup deep-links."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "029_sms_outbox_process_context"
down_revision = "028_interview_slot_student_join_open"
branch_labels = None
depends_on = None


def _has_col(insp, table, col) -> bool:
    try:
        return col in {c["name"] for c in insp.get_columns(table)}
    except Exception:
        return False


def _has_index(insp, table, name) -> bool:
    try:
        return name in {i["name"] for i in insp.get_indexes(table)}
    except Exception:
        return False


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    if not _has_col(insp, "sms_simulation_outbox", "process_instance_id"):
        op.add_column(
            "sms_simulation_outbox",
            sa.Column("process_instance_id", sa.String(length=36), nullable=True),
        )
    if not _has_col(insp, "sms_simulation_outbox", "process_state_code"):
        op.add_column(
            "sms_simulation_outbox",
            sa.Column("process_state_code", sa.String(length=120), nullable=True),
        )
    if not _has_col(insp, "sms_simulation_outbox", "process_code"):
        op.add_column(
            "sms_simulation_outbox",
            sa.Column("process_code", sa.String(length=120), nullable=True),
        )
    if not _has_index(insp, "sms_simulation_outbox", "ix_sms_sim_outbox_process_instance"):
        op.create_index(
            "ix_sms_sim_outbox_process_instance",
            "sms_simulation_outbox",
            ["process_instance_id"],
        )


def downgrade() -> None:
    op.drop_index("ix_sms_sim_outbox_process_instance", table_name="sms_simulation_outbox")
    op.drop_column("sms_simulation_outbox", "process_code")
    op.drop_column("sms_simulation_outbox", "process_state_code")
    op.drop_column("sms_simulation_outbox", "process_instance_id")
