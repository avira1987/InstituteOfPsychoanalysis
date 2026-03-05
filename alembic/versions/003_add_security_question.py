"""Add security question for password login.

Revision ID: 003_security_question
Revises: 002_add_otp_blog
Create Date: 2026-02-24

"""
from alembic import op
import sqlalchemy as sa

revision = '003_security_question'
down_revision = '002_add_otp_blog'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('security_question', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('security_answer_hash', sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'security_answer_hash')
    op.drop_column('users', 'security_question')
