"""Add login_challenges table for anti-bot math challenge.

Revision ID: 004_login_challenge
Revises: 003_security_question
Create Date: 2026-03-05
"""
from alembic import op
import sqlalchemy as sa


revision = "004_login_challenge"
down_revision = "003_security_question"
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.create_table(
      "login_challenges",
      sa.Column("id", sa.String(36), primary_key=True),
      sa.Column("question", sa.String(255), nullable=False),
      sa.Column("answer_hash", sa.String(255), nullable=False),
      sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
      sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
      sa.Column("is_used", sa.Boolean(), nullable=False, server_default=sa.text("0")),
  )
  op.create_index("ix_login_challenge_created_at", "login_challenges", ["created_at"])


def downgrade() -> None:
  op.drop_index("ix_login_challenge_created_at", table_name="login_challenges")
  op.drop_table("login_challenges")

