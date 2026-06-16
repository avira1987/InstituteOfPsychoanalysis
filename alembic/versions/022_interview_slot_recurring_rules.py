"""interview_slot_recurring_rules + interview_slots.generated_from_rule_id."""

from alembic import op
import sqlalchemy as sa


revision = "022_interview_slot_recurring_rules"
down_revision = "021_interview_slot_alocom_event"
branch_labels = None
depends_on = None


def _table_exists(conn, name: str) -> bool:
    return bool(
        conn.execute(
            sa.text(
                """
                SELECT EXISTS (
                  SELECT FROM information_schema.tables
                  WHERE table_schema = 'public' AND table_name = :name
                )
                """
            ),
            {"name": name},
        ).scalar()
    )


def _column_exists(conn, table: str, column: str) -> bool:
    return bool(
        conn.execute(
            sa.text(
                """
                SELECT EXISTS (
                  SELECT FROM information_schema.columns
                  WHERE table_schema = 'public'
                    AND table_name = :t AND column_name = :c
                )
                """
            ),
            {"t": table, "c": column},
        ).scalar()
    )


def _index_exists(conn, index_name: str) -> bool:
    return bool(
        conn.execute(
            sa.text("SELECT EXISTS (SELECT FROM pg_indexes WHERE indexname = :n)"),
            {"n": index_name},
        ).scalar()
    )


def upgrade() -> None:
    conn = op.get_bind()

    if not _table_exists(conn, "interview_slot_recurring_rules"):
        op.create_table(
            "interview_slot_recurring_rules",
            # هم‌قرار با app.models.compat.GUID (= VARCHAR36) مانند interview_slots و users
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column(
                "interviewer_user_id",
                sa.String(length=36),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("days_of_week", sa.JSON(), nullable=False),
            sa.Column("start_local_time", sa.Time(), nullable=False),
            sa.Column("end_local_time", sa.Time(), nullable=False),
            sa.Column("course_type", sa.String(length=50), nullable=True),
            sa.Column("mode", sa.String(length=20), nullable=False, server_default="online"),
            sa.Column("location_fa", sa.String(length=500), nullable=True),
            sa.Column("meeting_link", sa.Text(), nullable=True),
            sa.Column("label_fa", sa.String(length=255), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("horizon_days", sa.Integer(), nullable=False, server_default=sa.text("21")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )

    # ایندکس‌ها — در صورت اجرای نیمه‌کارهٔ قبلی ممکن است جداول باشد ولی ایندکس نباشد
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_interview_slot_rr_interviewer "
            "ON interview_slot_recurring_rules (interviewer_user_id)"
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_interview_slot_rr_active "
            "ON interview_slot_recurring_rules (is_active)"
        )
    )

    if not _column_exists(conn, "interview_slots", "generated_from_rule_id"):
        op.add_column(
            "interview_slots",
            sa.Column(
                "generated_from_rule_id",
                sa.String(length=36),
                sa.ForeignKey("interview_slot_recurring_rules.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )

    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_interview_slots_generated_rule "
            "ON interview_slots (generated_from_rule_id)"
        )
    )

    if not _index_exists(conn, "uq_interview_slot_rule_generated_start"):
        op.execute(
            """
            CREATE UNIQUE INDEX uq_interview_slot_rule_generated_start
            ON interview_slots (generated_from_rule_id, starts_at)
            WHERE generated_from_rule_id IS NOT NULL
            """
        )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_interview_slot_rule_generated_start")
    conn = op.get_bind()
    if _index_exists(conn, "ix_interview_slots_generated_rule"):
        op.drop_index("ix_interview_slots_generated_rule", table_name="interview_slots")
    if _column_exists(conn, "interview_slots", "generated_from_rule_id"):
        op.drop_column("interview_slots", "generated_from_rule_id")

    op.execute("DROP INDEX IF EXISTS ix_interview_slot_rr_active")
    op.execute("DROP INDEX IF EXISTS ix_interview_slot_rr_interviewer")

    if _table_exists(conn, "interview_slot_recurring_rules"):
        op.drop_table("interview_slot_recurring_rules")
