"""interview_slots: مالک مصاحبه‌گر اختیاری برای اسلات."""

from alembic import op
import sqlalchemy as sa


revision = "015_interview_slot_interviewer_user"
down_revision = "014_dynamic_forms"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # users.id در اسکیمای اولیه String(36) است — نه UUID بومی PostgreSQL
    op.add_column(
        "interview_slots",
        sa.Column("interviewer_user_id", sa.String(36), nullable=True),
    )
    op.create_foreign_key(
        "fk_interview_slots_interviewer_user_id_users",
        "interview_slots",
        "users",
        ["interviewer_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_interview_slots_interviewer_user_id",
        "interview_slots",
        ["interviewer_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_interview_slots_interviewer_user_id", table_name="interview_slots")
    op.drop_constraint("fk_interview_slots_interviewer_user_id_users", "interview_slots", type_="foreignkey")
    op.drop_column("interview_slots", "interviewer_user_id")
