"""Flag sample/seed students so reports can exclude them by default."""

from alembic import op
import sqlalchemy as sa


revision = "008_student_is_sample_data"
down_revision = "007_therapy_assignments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "students",
        sa.Column(
            "is_sample_data",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.execute(
        """
        UPDATE students SET is_sample_data = true
        WHERE student_code LIKE 'AUTO-DEMO-%'
           OR student_code LIKE 'DEMO-SCEN-%'
           OR student_code LIKE 'DEMO-ROLE-%'
        """
    )


def downgrade() -> None:
    op.drop_column("students", "is_sample_data")
