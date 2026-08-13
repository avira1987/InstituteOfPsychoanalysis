"""Widen otp_codes.code for HMAC hashes; clear portal_password_plain."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "041_security_hardening_otp_hash"
down_revision = "040_panel_flash_message_category"
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
    if _has_column(insp, "otp_codes", "code"):
        op.alter_column(
            "otp_codes",
            "code",
            existing_type=sa.String(length=6),
            type_=sa.String(length=128),
            existing_nullable=False,
        )
    if _has_column(insp, "users", "portal_password_plain"):
        op.execute(sa.text("UPDATE users SET portal_password_plain = NULL"))


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if _has_column(insp, "otp_codes", "code"):
        op.alter_column(
            "otp_codes",
            "code",
            existing_type=sa.String(length=128),
            type_=sa.String(length=6),
            existing_nullable=False,
        )
