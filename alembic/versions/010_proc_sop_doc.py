"""متن خام SOP و تصویر فلوچارت برای هر فرایند (پنل مدیریت).

شناسهٔ revision حداکثر ۳۲ کاراکتر (محدودیت ستون alembic_version.version_num).
"""

from alembic import op
import sqlalchemy as sa

revision = "010_proc_sop_doc"
down_revision = "009_site_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("process_definitions", sa.Column("source_text", sa.Text(), nullable=True))
    op.add_column("process_definitions", sa.Column("flowchart_image", sa.LargeBinary(), nullable=True))
    op.add_column(
        "process_definitions",
        sa.Column("flowchart_content_type", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("process_definitions", "flowchart_content_type")
    op.drop_column("process_definitions", "flowchart_image")
    op.drop_column("process_definitions", "source_text")
