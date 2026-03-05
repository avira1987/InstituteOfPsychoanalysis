"""Initial schema - all tables.

Revision ID: 001_initial
Revises:
Create Date: 2025-02-13
"""
from alembic import op
import sqlalchemy as sa

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def _guid_type():
    """UUID type that works on both PostgreSQL and SQLite."""
    from sqlalchemy.dialects import postgresql
    return sa.String(36)


def _json_type():
    """JSON type that works on both PostgreSQL and SQLite."""
    return sa.Text()


def upgrade() -> None:
    # ─── process_definitions ────────────────────────────────────
    op.create_table(
        "process_definitions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("name_fa", sa.String(255), nullable=False),
        sa.Column("name_en", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), default=1, nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("initial_state_code", sa.String(100), nullable=False),
        sa.Column("config", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(36), nullable=True),
    )

    # ─── state_definitions ──────────────────────────────────────
    op.create_table(
        "state_definitions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("process_id", sa.String(36), sa.ForeignKey("process_definitions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("name_fa", sa.String(255), nullable=False),
        sa.Column("name_en", sa.String(255), nullable=True),
        sa.Column("state_type", sa.String(20), nullable=False),
        sa.Column("meta_info", sa.Text(), nullable=True),
        sa.Column("assigned_role", sa.String(100), nullable=True),
        sa.Column("sla_hours", sa.Integer(), nullable=True),
        sa.Column("on_sla_breach_event", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("process_id", "code", name="uq_state_process_code"),
    )

    # ─── transition_definitions ─────────────────────────────────
    op.create_table(
        "transition_definitions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("process_id", sa.String(36), sa.ForeignKey("process_definitions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_state_code", sa.String(100), nullable=False),
        sa.Column("to_state_code", sa.String(100), nullable=False),
        sa.Column("trigger_event", sa.String(100), nullable=False),
        sa.Column("condition_rules", sa.Text(), nullable=True),
        sa.Column("required_role", sa.String(100), nullable=True),
        sa.Column("actions", sa.Text(), nullable=True),
        sa.Column("priority", sa.Integer(), default=0, nullable=False),
        sa.Column("description_fa", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_transition_lookup", "transition_definitions", ["process_id", "from_state_code", "trigger_event"])

    # ─── rule_definitions ───────────────────────────────────────
    op.create_table(
        "rule_definitions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("name_fa", sa.String(255), nullable=False),
        sa.Column("name_en", sa.String(255), nullable=True),
        sa.Column("rule_type", sa.String(30), nullable=False),
        sa.Column("expression", sa.Text(), nullable=False),
        sa.Column("parameters", sa.Text(), nullable=True),
        sa.Column("error_message_fa", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("version", sa.Integer(), default=1, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ─── users ──────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("username", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("email", sa.String(255), unique=True, nullable=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name_fa", sa.String(255), nullable=True),
        sa.Column("full_name_en", sa.String(255), nullable=True),
        sa.Column("role", sa.String(50), nullable=False, server_default="student"),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ─── students ───────────────────────────────────────────────
    op.create_table(
        "students",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("student_code", sa.String(50), unique=True, nullable=False, index=True),
        sa.Column("course_type", sa.String(50), nullable=False),
        sa.Column("is_intern", sa.Boolean(), default=False, nullable=False),
        sa.Column("term_count", sa.Integer(), default=1, nullable=False),
        sa.Column("current_term", sa.Integer(), default=1, nullable=False),
        sa.Column("therapy_started", sa.Boolean(), default=False, nullable=False),
        sa.Column("weekly_sessions", sa.Integer(), default=1, nullable=False),
        sa.Column("supervisor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("therapist_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("enrollment_date", sa.Date(), nullable=True),
        sa.Column("extra_data", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ─── process_instances ──────────────────────────────────────
    op.create_table(
        "process_instances",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("process_code", sa.String(100), nullable=False),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("current_state_code", sa.String(100), nullable=False),
        sa.Column("is_completed", sa.Boolean(), default=False, nullable=False),
        sa.Column("is_cancelled", sa.Boolean(), default=False, nullable=False),
        sa.Column("context_data", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_transition_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_instance_student", "process_instances", ["student_id"])
    op.create_index("ix_instance_process", "process_instances", ["process_code"])
    op.create_index("ix_instance_state", "process_instances", ["current_state_code"])

    # ─── state_history ──────────────────────────────────────────
    op.create_table(
        "state_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("instance_id", sa.String(36), sa.ForeignKey("process_instances.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_state_code", sa.String(100), nullable=True),
        sa.Column("to_state_code", sa.String(100), nullable=False),
        sa.Column("trigger_event", sa.String(100), nullable=False),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("actor_role", sa.String(50), nullable=True),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("entered_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_history_instance", "state_history", ["instance_id"])

    # ─── therapy_sessions ───────────────────────────────────────
    op.create_table(
        "therapy_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("therapist_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column("session_number", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="scheduled"),
        sa.Column("is_extra", sa.Boolean(), default=False, nullable=False),
        sa.Column("payment_status", sa.String(30), server_default="pending"),
        sa.Column("amount", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ─── financial_records ──────────────────────────────────────
    op.create_table(
        "financial_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("record_type", sa.String(50), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("description_fa", sa.String(500), nullable=True),
        sa.Column("reference_id", sa.String(36), nullable=True),
        sa.Column("shamsi_year", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
    )

    # ─── attendance_records ─────────────────────────────────────
    op.create_table(
        "attendance_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("therapy_sessions.id"), nullable=True),
        sa.Column("record_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("absence_type", sa.String(50), nullable=True),
        sa.Column("shamsi_year", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ─── audit_logs ─────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("instance_id", sa.String(36), nullable=True),
        sa.Column("process_code", sa.String(100), nullable=True),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("from_state", sa.String(100), nullable=True),
        sa.Column("to_state", sa.String(100), nullable=True),
        sa.Column("trigger_event", sa.String(100), nullable=True),
        sa.Column("actor_id", sa.String(36), nullable=True),
        sa.Column("actor_role", sa.String(50), nullable=True),
        sa.Column("actor_name", sa.String(255), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_instance", "audit_logs", ["instance_id"])
    op.create_index("ix_audit_actor", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_timestamp", "audit_logs", ["timestamp"])
    op.create_index("ix_audit_action", "audit_logs", ["action_type"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("attendance_records")
    op.drop_table("financial_records")
    op.drop_table("therapy_sessions")
    op.drop_table("state_history")
    op.drop_table("process_instances")
    op.drop_table("students")
    op.drop_table("users")
    op.drop_table("rule_definitions")
    op.drop_table("transition_definitions")
    op.drop_table("state_definitions")
    op.drop_table("process_definitions")
