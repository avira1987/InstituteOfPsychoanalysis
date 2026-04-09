"""گسترش طول ستون alembic_version.version_num (PostgreSQL: پیش‌فرض ۳۲ کاراکتر).

جلوگیری از خطای «value too long for type character varying(32)» اگر شناسهٔ revision
طولانی‌تر از ۳۲ کاراکتر باشد.
"""

from alembic import op

revision = "011_alembic_ver64"
down_revision = "010_proc_sop_doc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)")


def downgrade() -> None:
    op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(32)")
