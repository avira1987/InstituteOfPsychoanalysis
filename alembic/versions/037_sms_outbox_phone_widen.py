"""Widen sms_simulation_outbox.phone — avoid varchar(15) insert failures."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "037_sms_outbox_phone_widen"
down_revision = "036_educational_therapist_slots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "sms_simulation_outbox" not in insp.get_table_names():
        return
    cols = {c["name"]: c for c in insp.get_columns("sms_simulation_outbox")}
    phone = cols.get("phone")
    if not phone:
        return
    # Keep widen idempotent if already longer than 15
    typ = phone.get("type")
    length = getattr(typ, "length", None)
    if length is not None and length >= 32:
        return
    op.alter_column(
        "sms_simulation_outbox",
        "phone",
        existing_type=sa.String(length=15),
        type_=sa.String(length=32),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "sms_simulation_outbox",
        "phone",
        existing_type=sa.String(length=32),
        type_=sa.String(length=15),
        existing_nullable=False,
    )
