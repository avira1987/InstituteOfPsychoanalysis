"""Add OTP codes and blog posts tables.

Revision ID: 002_add_otp_blog
Revises: 001_initial_schema
Create Date: 2026-02-24
"""
from alembic import op
import sqlalchemy as sa

revision = '002_add_otp_blog'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'otp_codes',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('phone', sa.String(15), nullable=False),
        sa.Column('code', sa.String(6), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_used', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
    )
    op.create_index('ix_otp_phone', 'otp_codes', ['phone'])

    op.create_table(
        'blog_posts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('slug', sa.String(500), nullable=False, unique=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('author_id', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('tags', sa.String(500), nullable=True),
        sa.Column('featured_image', sa.String(500), nullable=True),
        sa.Column('is_published', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('views', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_blog_slug', 'blog_posts', ['slug'])


def downgrade() -> None:
    op.drop_index('ix_blog_slug', table_name='blog_posts')
    op.drop_table('blog_posts')
    op.drop_index('ix_otp_phone', table_name='otp_codes')
    op.drop_table('otp_codes')
