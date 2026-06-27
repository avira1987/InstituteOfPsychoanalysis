"""users.profile_meta — رسته و نقش آموزشی مدرسین/کمک‌مدرسین."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

from app.models.compat import JSONType as JSONB


revision = "032_users_profile_meta"
down_revision = "031_daily_overdue_check"
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
    if _has_column(insp, "users", "profile_meta"):
        return
    op.add_column("users", sa.Column("profile_meta", JSONB, nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not _has_column(insp, "users", "profile_meta"):
        return
    op.drop_column("users", "profile_meta")
