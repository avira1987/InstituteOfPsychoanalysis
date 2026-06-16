"""sms_simulation_outbox + sms_simulation_dismissals for dev SMS popups."""

from alembic import op
import sqlalchemy as sa

revision = "023_sms_simulation_outbox"
down_revision = "022_interview_slot_recurring_rules"
branch_labels = None
depends_on = None


def _guid():
    # هم‌قرار با app.models.compat.GUID (= VARCHAR36) و users.id در اسکیمای اولیه
    return sa.String(36)


def upgrade() -> None:
    op.create_table(
        "sms_simulation_outbox",
        sa.Column("id", _guid(), nullable=False),
        sa.Column("phone", sa.String(length=15), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("template_key", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sms_sim_outbox_phone", "sms_simulation_outbox", ["phone"])
    op.create_index("ix_sms_sim_outbox_created", "sms_simulation_outbox", ["created_at"])

    op.create_table(
        "sms_simulation_dismissals",
        sa.Column("sms_id", _guid(), nullable=False),
        sa.Column("user_id", _guid(), nullable=False),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["sms_id"], ["sms_simulation_outbox.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("sms_id", "user_id"),
    )
    op.create_index("ix_sms_sim_dismiss_user", "sms_simulation_dismissals", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_sms_sim_dismiss_user", table_name="sms_simulation_dismissals")
    op.drop_table("sms_simulation_dismissals")
    op.drop_index("ix_sms_sim_outbox_created", table_name="sms_simulation_outbox")
    op.drop_index("ix_sms_sim_outbox_phone", table_name="sms_simulation_outbox")
    op.drop_table("sms_simulation_outbox")
