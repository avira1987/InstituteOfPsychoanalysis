"""Add ledger_category and accounting_status to financial_records."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "042_financial_ledger_category"
down_revision = "041_security_hardening_otp_hash"
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
    if not _has_column(insp, "financial_records", "ledger_category"):
        op.add_column(
            "financial_records",
            sa.Column("ledger_category", sa.String(length=30), nullable=False, server_default="other"),
        )
    if not _has_column(insp, "financial_records", "accounting_status"):
        op.add_column(
            "financial_records",
            sa.Column("accounting_status", sa.String(length=20), nullable=True),
        )
    # Backfill tuition rows tagged by SOP description prefix
    op.execute(
        sa.text(
            "UPDATE financial_records SET ledger_category = 'tuition' "
            "WHERE description_fa LIKE N'شهریه ترم%' OR description_fa LIKE N'%شهریه ترم%'"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if _has_column(insp, "financial_records", "accounting_status"):
        op.drop_column("financial_records", "accounting_status")
    if _has_column(insp, "financial_records", "ledger_category"):
        op.drop_column("financial_records", "ledger_category")
