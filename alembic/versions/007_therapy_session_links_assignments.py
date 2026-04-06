"""Therapy session meeting links, instructor fields; assignments MVP."""

from alembic import op
import sqlalchemy as sa


revision = "007_therapy_assignments"
down_revision = "006_payment_pending"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("therapy_sessions", sa.Column("meeting_url", sa.Text(), nullable=True))
    op.add_column("therapy_sessions", sa.Column("meeting_provider", sa.String(50), nullable=True))
    op.add_column("therapy_sessions", sa.Column("links_unlocked", sa.Boolean(), server_default="0", nullable=False))
    op.add_column("therapy_sessions", sa.Column("instructor_score", sa.Float(), nullable=True))
    op.add_column("therapy_sessions", sa.Column("instructor_comment", sa.Text(), nullable=True))

    op.create_table(
        "assignments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title_fa", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_assignments_student", "assignments", ["student_id"])

    op.create_table(
        "assignment_submissions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("assignment_id", sa.String(36), sa.ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("feedback_fa", sa.Text(), nullable=True),
    )
    op.create_index("ix_submission_assignment", "assignment_submissions", ["assignment_id"])


def downgrade() -> None:
    op.drop_table("assignment_submissions")
    op.drop_table("assignments")
    op.drop_column("therapy_sessions", "instructor_comment")
    op.drop_column("therapy_sessions", "instructor_score")
    op.drop_column("therapy_sessions", "links_unlocked")
    op.drop_column("therapy_sessions", "meeting_provider")
    op.drop_column("therapy_sessions", "meeting_url")
