"""Add missing fields to existing tables

Revision ID: 20240220_000004
Revises: 20240220_000003
Create Date: 2024-02-20 00:00:04.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = '20240220_000004'
down_revision: Union[str, None] = '20240220_000003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Add missing fields to users table
    op.add_column('users', sa.Column('notification_channels', JSONB, nullable=False, server_default=sa.text('\'["in_app"]\'::jsonb')))
    op.add_column('users', sa.Column('email_verified', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('users', sa.Column('social_provider', sa.String(50), nullable=True))
    op.add_column('users', sa.Column('social_id', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('last_payment_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('active_goals_count', sa.Integer(), nullable=False, server_default=sa.text('0')))
    op.add_column('users', sa.Column('total_deals_found', sa.Integer(), nullable=False, server_default=sa.text('0')))
    op.add_column('users', sa.Column('success_rate', sa.Numeric(5, 4), nullable=False, server_default=sa.text('0')))
    op.add_column('users', sa.Column('total_tokens_spent', sa.Numeric(18, 8), nullable=False, server_default=sa.text('0')))
    op.add_column('users', sa.Column('total_rewards_earned', sa.Numeric(18, 8), nullable=False, server_default=sa.text('0')))

    # Add notification_metadata to notifications table
    op.add_column('notifications', sa.Column('notification_metadata', JSONB, nullable=True))

def downgrade() -> None:
    # Drop added columns in reverse order
    op.drop_column('notifications', 'notification_metadata')

    op.drop_column('users', 'total_rewards_earned')
    op.drop_column('users', 'total_tokens_spent')
    op.drop_column('users', 'success_rate')
    op.drop_column('users', 'total_deals_found')
    op.drop_column('users', 'active_goals_count')
    op.drop_column('users', 'last_login_at')
    op.drop_column('users', 'last_payment_at')
    op.drop_column('users', 'social_id')
    op.drop_column('users', 'social_provider')
    op.drop_column('users', 'email_verified')
    op.drop_column('users', 'notification_channels') 