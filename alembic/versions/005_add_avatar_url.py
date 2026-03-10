"""Add avatar_url to users.

Revision ID: 005_avatar_url
Revises: 004_login_challenge
Create Date: 2026-03-10

"""
from alembic import op
import sqlalchemy as sa


revision = "005_avatar_url"
down_revision = "004_login_challenge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_url", sa.String(512), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar_url")
