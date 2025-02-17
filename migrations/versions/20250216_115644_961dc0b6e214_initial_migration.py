"""Initial migration

Revision ID: 961dc0b6e214
Revises: 
Create Date: 2025-02-16 11:56:44.961214

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = '961dc0b6e214'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Create ENUM types if they don't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'userstatus') THEN
                CREATE TYPE userstatus AS ENUM ('active', 'inactive', 'suspended', 'deleted');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'notificationstatus') THEN
                CREATE TYPE notificationstatus AS ENUM ('pending', 'sent', 'delivered', 'failed', 'read');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'notificationtype') THEN
                CREATE TYPE notificationtype AS ENUM ('deal_match', 'goal_completed', 'goal_expired', 'price_drop', 'token_low', 'system', 'custom');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'notificationpriority') THEN
                CREATE TYPE notificationpriority AS ENUM ('low', 'medium', 'high', 'urgent');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'goalstatus') THEN
                CREATE TYPE goalstatus AS ENUM ('active', 'completed', 'expired', 'paused', 'cancelled');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'goalpriority') THEN
                CREATE TYPE goalpriority AS ENUM ('low', 'medium', 'high');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'dealstatus') THEN
                CREATE TYPE dealstatus AS ENUM ('active', 'expired', 'purchased', 'unavailable');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'tokentransactiontype') THEN
                CREATE TYPE tokentransactiontype AS ENUM ('deposit', 'withdrawal', 'reward', 'fee', 'refund');
            END IF;
        END $$;
    """)

    # Create users table
    op.execute("""
        CREATE TABLE users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email VARCHAR(255) NOT NULL UNIQUE,
            name VARCHAR(255),
            password TEXT NOT NULL,
            sol_address VARCHAR(44) UNIQUE,
            referral_code VARCHAR(10) UNIQUE,
            referred_by UUID REFERENCES users(id) ON DELETE SET NULL,
            token_balance NUMERIC(18,8) NOT NULL DEFAULT 0,
            preferences JSONB NOT NULL DEFAULT '{}',
            status userstatus NOT NULL DEFAULT 'active',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT ch_positive_balance CHECK (token_balance >= 0),
            CONSTRAINT uq_user_email UNIQUE (email),
            CONSTRAINT uq_user_wallet UNIQUE (sol_address),
            CONSTRAINT uq_user_referral UNIQUE (referral_code)
        );
        CREATE INDEX ix_users_email_status ON users(email, status);
        CREATE INDEX ix_users_wallet ON users(sol_address);
        CREATE INDEX ix_users_referral ON users(referral_code);
    """)

    # Create goals table
    op.execute("""
        CREATE TABLE goals (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            item_category VARCHAR(50) NOT NULL,
            title VARCHAR(255) NOT NULL,
            constraints JSONB NOT NULL,
            deadline TIMESTAMP WITH TIME ZONE,
            status goalstatus NOT NULL DEFAULT 'active',
            priority goalpriority NOT NULL DEFAULT 'medium',
            max_matches INTEGER,
            max_tokens NUMERIC(18,8),
            notification_threshold NUMERIC(3,2),
            auto_buy_threshold NUMERIC(3,2),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            last_checked_at TIMESTAMP WITH TIME ZONE,
            CONSTRAINT ch_positive_tokens CHECK (max_tokens >= 0)
        );
        CREATE INDEX ix_goals_user_status ON goals(user_id, status);
        CREATE INDEX ix_goals_priority_deadline ON goals(priority, deadline);
    """)

    # Create deals table
    op.execute("""
        CREATE TABLE deals (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            goal_id UUID REFERENCES goals(id) ON DELETE CASCADE,
            title VARCHAR(255) NOT NULL,
            description TEXT,
            url TEXT NOT NULL,
            price DECIMAL(10,2) NOT NULL,
            original_price DECIMAL(10,2),
            currency VARCHAR(3) DEFAULT 'USD',
            source VARCHAR(50) NOT NULL,
            image_url TEXT,
            category VARCHAR(50),
            status dealstatus NOT NULL DEFAULT 'active',
            seller_info JSONB,
            found_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT ch_positive_price CHECK (price > 0),
            CONSTRAINT ch_original_price_gt_price CHECK (original_price IS NULL OR original_price > price),
            CONSTRAINT uq_deal_url_goal UNIQUE (url, goal_id)
        );
        CREATE INDEX ix_deals_status_found ON deals(status, found_at);
        CREATE INDEX ix_deals_goal_status ON deals(goal_id, status);
    """)

    # Create notifications table
    op.execute("""
        CREATE TABLE notifications (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            goal_id UUID REFERENCES goals(id) ON DELETE SET NULL,
            deal_id UUID REFERENCES deals(id) ON DELETE SET NULL,
            title VARCHAR(255) NOT NULL,
            message TEXT NOT NULL,
            type notificationtype NOT NULL,
            priority notificationpriority DEFAULT 'medium',
            status notificationstatus DEFAULT 'pending',
            channels JSONB NOT NULL DEFAULT '["in_app"]',
            notification_metadata JSONB,
            action_url VARCHAR(2048),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            sent_at TIMESTAMP WITH TIME ZONE,
            delivered_at TIMESTAMP WITH TIME ZONE,
            read_at TIMESTAMP WITH TIME ZONE,
            CONSTRAINT ch_sent_after_created CHECK (sent_at IS NULL OR sent_at >= created_at),
            CONSTRAINT ch_delivered_after_sent CHECK (delivered_at IS NULL OR delivered_at >= sent_at),
            CONSTRAINT ch_read_after_delivered CHECK (read_at IS NULL OR read_at >= delivered_at)
        );
        CREATE INDEX ix_notifications_user_status ON notifications(user_id, status);
        CREATE INDEX ix_notifications_goal ON notifications(goal_id);
        CREATE INDEX ix_notifications_deal ON notifications(deal_id);
    """)

    # Create token_transactions table
    op.execute("""
        CREATE TABLE token_transactions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            type tokentransactiontype NOT NULL,
            amount NUMERIC(18,8) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            tx_hash VARCHAR(66),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX ix_token_transactions_user ON token_transactions(user_id, created_at);
        CREATE INDEX ix_token_transactions_hash ON token_transactions(tx_hash);
    """)

def downgrade() -> None:
    # Drop tables in reverse order
    op.execute("DROP TABLE IF EXISTS token_transactions CASCADE;")
    op.execute("DROP TABLE IF EXISTS notifications CASCADE;")
    op.execute("DROP TABLE IF EXISTS deals CASCADE;")
    op.execute("DROP TABLE IF EXISTS goals CASCADE;")
    op.execute("DROP TABLE IF EXISTS users CASCADE;")

    # Drop ENUM types
    op.execute("""
        DROP TYPE IF EXISTS tokentransactiontype;
        DROP TYPE IF EXISTS dealstatus;
        DROP TYPE IF EXISTS goalpriority;
        DROP TYPE IF EXISTS goalstatus;
        DROP TYPE IF EXISTS notificationpriority;
        DROP TYPE IF EXISTS notificationtype;
        DROP TYPE IF EXISTS notificationstatus;
        DROP TYPE IF EXISTS userstatus;
    """) 