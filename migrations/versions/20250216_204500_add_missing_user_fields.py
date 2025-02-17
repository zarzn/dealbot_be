"""Add missing user fields

Revision ID: 2025021620450
Revises: 961dc0b6e214
Create Date: 2025-02-16 20:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = '2025021620450'
down_revision: Union[str, None] = '961dc0b6e214'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Add missing columns to users table
    op.execute("""
        ALTER TABLE users
        ADD COLUMN notification_channels JSONB NOT NULL DEFAULT '["in_app", "email"]',
        ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT FALSE,
        ADD COLUMN social_provider VARCHAR(255),
        ADD COLUMN social_id VARCHAR(255),
        ADD COLUMN last_payment_at TIMESTAMP WITH TIME ZONE,
        ADD COLUMN last_login_at TIMESTAMP WITH TIME ZONE,
        ADD COLUMN active_goals_count INTEGER NOT NULL DEFAULT 0,
        ADD COLUMN total_deals_found INTEGER NOT NULL DEFAULT 0,
        ADD COLUMN success_rate NUMERIC(5,4) NOT NULL DEFAULT 0,
        ADD COLUMN total_tokens_spent NUMERIC(18,8) NOT NULL DEFAULT 0,
        ADD COLUMN total_rewards_earned NUMERIC(18,8) NOT NULL DEFAULT 0;
    """)

def downgrade() -> None:
    # Remove added columns from users table
    op.execute("""
        ALTER TABLE users
        DROP COLUMN notification_channels,
        DROP COLUMN email_verified,
        DROP COLUMN social_provider,
        DROP COLUMN social_id,
        DROP COLUMN last_payment_at,
        DROP COLUMN last_login_at,
        DROP COLUMN active_goals_count,
        DROP COLUMN total_deals_found,
        DROP COLUMN success_rate,
        DROP COLUMN total_tokens_spent,
        DROP COLUMN total_rewards_earned;
    """) 