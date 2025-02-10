"""Initial database setup.

Revision ID: 20240315_initial
Revises: None
Create Date: 2024-03-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = '20240315_initial'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Create ENUM types
    commands = [
        "DROP TYPE IF EXISTS userstatus CASCADE",
        "DROP TYPE IF EXISTS transaction_type CASCADE",
        "DROP TYPE IF EXISTS transaction_status CASCADE",
        "CREATE TYPE userstatus AS ENUM ('active', 'inactive', 'suspended', 'deleted')",
        "CREATE TYPE transaction_type AS ENUM ('payment', 'refund', 'reward', 'penalty')",
        "CREATE TYPE transaction_status AS ENUM ('pending', 'completed', 'failed', 'cancelled')",
        """
        CREATE TABLE users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email VARCHAR(255) NOT NULL UNIQUE,
            name VARCHAR(255) NOT NULL,
            password VARCHAR(255),
            sol_address VARCHAR(44) UNIQUE,
            referral_code VARCHAR(10) UNIQUE,
            referred_by UUID REFERENCES users(id),
            token_balance NUMERIC(18, 8) NOT NULL DEFAULT 0,
            preferences JSONB NOT NULL DEFAULT '{}',
            status userstatus NOT NULL DEFAULT 'active',
            notification_channels JSONB NOT NULL DEFAULT '["in_app", "email"]',
            email_verified BOOLEAN NOT NULL DEFAULT false,
            social_provider VARCHAR(255),
            social_id VARCHAR(255),
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_payment_at TIMESTAMP WITH TIME ZONE,
            last_login_at TIMESTAMP WITH TIME ZONE,
            active_goals_count INTEGER NOT NULL DEFAULT 0,
            total_deals_found INTEGER NOT NULL DEFAULT 0,
            success_rate NUMERIC(5, 4) NOT NULL DEFAULT 0,
            total_tokens_spent NUMERIC(18, 8) NOT NULL DEFAULT 0,
            total_rewards_earned NUMERIC(18, 8) NOT NULL DEFAULT 0
        )
        """,
        """
        CREATE TABLE token_balances (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            balance NUMERIC(18, 8) NOT NULL DEFAULT 0,
            last_updated TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE token_transactions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            type transaction_type NOT NULL,
            amount NUMERIC(18, 8) NOT NULL,
            status transaction_status NOT NULL DEFAULT 'pending',
            tx_hash VARCHAR(66),
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        "CREATE INDEX ix_users_email ON users(email)",
        "CREATE INDEX ix_users_status ON users(status)",
        "CREATE INDEX ix_users_social_provider ON users(social_provider)",
        "CREATE INDEX ix_token_balances_user_id ON token_balances(user_id)",
        "CREATE INDEX ix_token_transactions_user_id ON token_transactions(user_id)",
        "CREATE INDEX ix_token_transactions_created_at ON token_transactions(created_at)",
        "CREATE INDEX ix_token_transactions_status ON token_transactions(status)"
    ]
    
    for command in commands:
        op.execute(command)

def downgrade() -> None:
    # Drop indexes
    commands = [
        "DROP INDEX IF EXISTS ix_token_transactions_status",
        "DROP INDEX IF EXISTS ix_token_transactions_created_at",
        "DROP INDEX IF EXISTS ix_token_transactions_user_id",
        "DROP INDEX IF EXISTS ix_token_balances_user_id",
        "DROP INDEX IF EXISTS ix_users_social_provider",
        "DROP INDEX IF EXISTS ix_users_status",
        "DROP INDEX IF EXISTS ix_users_email",
        "DROP TABLE IF EXISTS token_transactions",
        "DROP TABLE IF EXISTS token_balances",
        "DROP TABLE IF EXISTS users",
        "DROP TYPE IF EXISTS transaction_status CASCADE",
        "DROP TYPE IF EXISTS transaction_type CASCADE",
        "DROP TYPE IF EXISTS userstatus CASCADE"
    ]
    
    for command in commands:
        op.execute(command) 