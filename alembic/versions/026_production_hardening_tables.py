"""notification_outbox + failed_actions for production reliability."""



import sqlalchemy as sa

from alembic import op

from sqlalchemy import inspect



revision = "026_production_hardening"

down_revision = "025_unified_forms"

branch_labels = None

depends_on = None





def upgrade() -> None:

    bind = op.get_bind()

    insp = inspect(bind)

    tables = insp.get_table_names() or ()



    if "notification_outbox" not in tables:

        op.create_table(

            "notification_outbox",

            sa.Column("id", sa.String(36), primary_key=True),

            sa.Column("channel", sa.String(20), nullable=False, server_default="sms"),

            sa.Column("recipient", sa.String(32), nullable=False),

            sa.Column("message", sa.Text(), nullable=False),

            sa.Column("template_key", sa.String(120), nullable=True),

            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),

            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),

            sa.Column("max_retries", sa.Integer(), nullable=False, server_default="5"),

            sa.Column("last_error", sa.Text(), nullable=True),

            sa.Column("context_json", sa.JSON(), nullable=True),

            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),

            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),

            sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),

        )

        op.create_index("ix_notif_outbox_status", "notification_outbox", ["status"])

        op.create_index("ix_notif_outbox_next_retry", "notification_outbox", ["next_retry_at"])



    if "failed_actions" not in tables:

        op.create_table(

            "failed_actions",

            sa.Column("id", sa.String(36), primary_key=True),

            sa.Column("instance_id", sa.String(36), sa.ForeignKey("process_instances.id", ondelete="CASCADE"), nullable=False),

            sa.Column("action_type", sa.String(100), nullable=False),

            sa.Column("action_payload", sa.JSON(), nullable=True),

            sa.Column("error_message", sa.Text(), nullable=True),

            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),

            sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.text("false")),

            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),

            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),

        )

        op.create_index("ix_failed_actions_instance", "failed_actions", ["instance_id"])





def downgrade() -> None:

    op.drop_index("ix_failed_actions_instance", table_name="failed_actions")

    op.drop_table("failed_actions")

    op.drop_index("ix_notif_outbox_next_retry", table_name="notification_outbox")

    op.drop_index("ix_notif_outbox_status", table_name="notification_outbox")

    op.drop_table("notification_outbox")


