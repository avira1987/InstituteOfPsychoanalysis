"""فرم‌های داینامیک DB + منوی پورتال."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "014_dynamic_forms"
down_revision = "013_payment_pending_gateway_track"
branch_labels = None
depends_on = None


def _guid():
    return sa.String(36)


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if "form_templates" in insp.get_table_names():
        # قبلاً با create_all یا اجرای جزئی ساخته شده
        return

    op.create_table(
        "form_templates",
        sa.Column("id", _guid(), primary_key=True),
        sa.Column("code", sa.String(80), nullable=False, unique=True),
        sa.Column("name_fa", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("audience", sa.String(20), nullable=False, server_default="both"),
        sa.Column("created_by_id", _guid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "form_template_versions",
        sa.Column("id", _guid(), primary_key=True),
        sa.Column("template_id", _guid(), sa.ForeignKey("form_templates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("schema_json", sa.JSON(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("template_id", "version", name="uq_form_template_version"),
    )
    op.create_index("ix_form_template_versions_template", "form_template_versions", ["template_id"])

    op.create_table(
        "form_assignments",
        sa.Column("id", _guid(), primary_key=True),
        sa.Column("template_id", _guid(), sa.ForeignKey("form_templates.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "template_version_id",
            _guid(),
            sa.ForeignKey("form_template_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("assignment_type", sa.String(32), nullable=False),
        sa.Column("portal_role", sa.String(64), nullable=True),
        sa.Column("portal_section", sa.String(64), nullable=True),
        sa.Column("process_code", sa.String(100), nullable=True),
        sa.Column("state_code", sa.String(100), nullable=True),
        sa.Column("context_key", sa.String(80), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_form_assignments_process_state",
        "form_assignments",
        ["process_code", "state_code"],
    )
    op.create_index("ix_form_assignments_portal_role", "form_assignments", ["portal_role"])

    op.create_table(
        "form_responses",
        sa.Column("id", _guid(), primary_key=True),
        sa.Column(
            "template_version_id",
            _guid(),
            sa.ForeignKey("form_template_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assignment_id",
            _guid(),
            sa.ForeignKey("form_assignments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("user_id", _guid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("student_id", _guid(), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=True),
        sa.Column(
            "instance_id",
            _guid(),
            sa.ForeignKey("process_instances.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("answers_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_form_responses_student", "form_responses", ["student_id"])
    op.create_index("ix_form_responses_instance", "form_responses", ["instance_id"])
    op.create_index("ix_form_responses_version", "form_responses", ["template_version_id"])

    op.create_table(
        "form_approval_steps",
        sa.Column("id", _guid(), primary_key=True),
        sa.Column(
            "response_id",
            _guid(),
            sa.ForeignKey("form_responses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("required_role", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("acted_by_id", _guid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("acted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
    )
    op.create_index("ix_form_approval_steps_response", "form_approval_steps", ["response_id"])

    op.create_table(
        "portal_nav_configs",
        sa.Column("id", _guid(), primary_key=True),
        sa.Column("role", sa.String(64), nullable=False, unique=True),
        sa.Column("items_json", sa.JSON(), nullable=False),
        sa.Column("merge_mode", sa.String(24), nullable=False, server_default="append"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_portal_nav_configs_role", "portal_nav_configs", ["role"], unique=True)


def downgrade() -> None:
    op.drop_table("form_approval_steps")
    op.drop_table("form_responses")
    op.drop_table("form_assignments")
    op.drop_table("form_template_versions")
    op.drop_table("form_templates")
    op.drop_table("portal_nav_configs")
