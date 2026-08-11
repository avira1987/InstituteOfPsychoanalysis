"""users.roles — آرایهٔ چندنقشه در کنار role اصلی."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text
from sqlalchemy.dialects.postgresql import JSONB


revision = "039_users_roles"
down_revision = "038_et_slot_week_interval"
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
    if not _has_column(insp, "users", "roles"):
        # باید JSONB باشد تا jsonb_typeof / contains کار کند (JSONType=JSON شکست می‌خورد)
        op.add_column("users", sa.Column("roles", JSONB, nullable=True))
    # Backfill: هر کاربر بدون roles → [role]
    bind.execute(
        text(
            """
            UPDATE users
            SET roles = jsonb_build_array(COALESCE(NULLIF(TRIM(role), ''), 'student'))
            WHERE roles IS NULL
               OR jsonb_typeof(roles) <> 'array'
               OR jsonb_array_length(roles) = 0
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not _has_column(insp, "users", "roles"):
        return
    op.drop_column("users", "roles")
