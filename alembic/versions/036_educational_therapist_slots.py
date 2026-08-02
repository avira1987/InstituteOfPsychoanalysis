"""educational_therapist_slots — شیت وقت‌های آزاد درمانگران آموزشی."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "036_educational_therapist_slots"
down_revision = "035_term_course_offerings"
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
    if _has_table(insp, "educational_therapist_slots"):
        return

    op.create_table(
        "educational_therapist_slots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("therapist_user_id", sa.String(length=36), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("start_local_time", sa.Time(), nullable=False),
        sa.Column("end_local_time", sa.Time(), nullable=False),
        sa.Column("course_type", sa.String(length=50), nullable=True),
        sa.Column("label_fa", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="free", nullable=False),
        sa.Column("assigned_student_id", sa.String(length=36), nullable=True),
        sa.Column("assigned_instance_id", sa.String(length=36), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["therapist_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_student_id"], ["students.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_instance_id"], ["process_instances.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_et_slots_therapist", "educational_therapist_slots", ["therapist_user_id"])
    op.create_index("ix_et_slots_status", "educational_therapist_slots", ["status"])
    op.create_index("ix_et_slots_assigned_student", "educational_therapist_slots", ["assigned_student_id"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not _has_table(insp, "educational_therapist_slots"):
        return
    op.drop_index("ix_et_slots_assigned_student", table_name="educational_therapist_slots")
    op.drop_index("ix_et_slots_status", table_name="educational_therapist_slots")
    op.drop_index("ix_et_slots_therapist", table_name="educational_therapist_slots")
    op.drop_table("educational_therapist_slots")
