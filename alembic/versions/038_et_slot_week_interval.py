"""educational_therapist_slots.week_interval — هفتگی / هفته‌درمیان."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "038_et_slot_week_interval"
down_revision = "037_sms_outbox_phone_widen"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "educational_therapist_slots" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("educational_therapist_slots")}
    if "week_interval" in cols:
        return
    op.add_column(
        "educational_therapist_slots",
        sa.Column("week_interval", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "educational_therapist_slots" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("educational_therapist_slots")}
    if "week_interval" not in cols:
        return
    op.drop_column("educational_therapist_slots", "week_interval")
