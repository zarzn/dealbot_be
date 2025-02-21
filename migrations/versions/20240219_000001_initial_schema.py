"""Initial database schema

Revision ID: 20240219_000001
Revises: 
Create Date: 2024-02-19 00:00:01.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import text
import logging
from datetime import datetime

# Configure logging
logger = logging.getLogger('alembic.revision')

# revision identifiers, used by Alembic.
revision: str = '20240219_000001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade database schema."""
    try:
        logger.info("Starting initial schema migration")
        conn = op.get_bind()
        
        # Drop all tables first to ensure clean state
        logger.info("Dropping existing tables...")
        conn.execute(text("""
            DROP TABLE IF EXISTS agents CASCADE;
            DROP TABLE IF EXISTS price_tracking CASCADE;
            DROP TABLE IF EXISTS user_preferences CASCADE;
            DROP TABLE IF EXISTS chat_messages CASCADE;
            DROP TABLE IF EXISTS model_metrics CASCADE;
            DROP TABLE IF EXISTS token_pricing CASCADE;
            DROP TABLE IF EXISTS token_balance_history CASCADE;
            DROP TABLE IF EXISTS token_transactions CASCADE;
            DROP TABLE IF EXISTS notifications CASCADE;
            DROP TABLE IF EXISTS price_predictions CASCADE;
            DROP TABLE IF EXISTS price_points CASCADE;
            DROP TABLE IF EXISTS deals CASCADE;
            DROP TABLE IF EXISTS goals CASCADE;
            DROP TABLE IF EXISTS markets CASCADE;
            DROP TABLE IF EXISTS auth_tokens CASCADE;
            DROP TABLE IF EXISTS users CASCADE;
        """))
        logger.info("Existing tables dropped")
        
        # Drop existing enum types
        logger.info("Dropping existing enum types...")
        conn.execute(text("""
            DROP TYPE IF EXISTS userstatus CASCADE;
            DROP TYPE IF EXISTS goal_status CASCADE;
            DROP TYPE IF EXISTS item_category CASCADE;
            DROP TYPE IF EXISTS markettype CASCADE;
            DROP TYPE IF EXISTS market_status CASCADE;
            DROP TYPE IF EXISTS notification_priority CASCADE;
            DROP TYPE IF EXISTS notification_status CASCADE;
            DROP TYPE IF EXISTS message_role CASCADE;
            DROP TYPE IF EXISTS message_status CASCADE;
            DROP TYPE IF EXISTS deal_status CASCADE;
            DROP TYPE IF EXISTS notification_type CASCADE;
            DROP TYPE IF EXISTS notification_channel CASCADE;
            DROP TYPE IF EXISTS task_status CASCADE;
            DROP TYPE IF EXISTS goal_priority CASCADE;
            DROP TYPE IF EXISTS currency CASCADE;
            DROP TYPE IF EXISTS token_operation CASCADE;
        """))
        logger.info("Existing enum types dropped")

        # Create enum types one by one
        logger.info("Creating enum types...")
        conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE userstatus AS ENUM ('active', 'inactive', 'suspended', 'deleted');
                CREATE TYPE goal_status AS ENUM ('active', 'paused', 'completed', 'cancelled', 'failed');
                CREATE TYPE item_category AS ENUM ('electronics', 'fashion', 'home', 'books', 'toys', 'sports', 'automotive', 'health', 'beauty', 'grocery', 'other');
                CREATE TYPE markettype AS ENUM ('amazon', 'walmart', 'ebay', 'target', 'bestbuy');
                CREATE TYPE market_status AS ENUM ('active', 'inactive', 'maintenance', 'rate_limited', 'error');
                CREATE TYPE notification_priority AS ENUM ('low', 'medium', 'high', 'critical');
                CREATE TYPE notification_status AS ENUM ('pending', 'sent', 'delivered', 'read', 'failed');
                CREATE TYPE message_role AS ENUM ('user', 'assistant', 'system');
                CREATE TYPE message_status AS ENUM ('pending', 'processing', 'completed', 'failed');
                CREATE TYPE deal_status AS ENUM ('active', 'expired', 'sold_out', 'invalid', 'deleted');
                CREATE TYPE notification_type AS ENUM ('system', 'deal', 'goal', 'price', 'email', 'push', 'sms');
                CREATE TYPE notification_channel AS ENUM ('in_app', 'email', 'push', 'sms', 'websocket');
                CREATE TYPE task_status AS ENUM ('pending', 'processing', 'completed', 'failed', 'cancelled', 'unknown', 'error');
                CREATE TYPE goal_priority AS ENUM ('high', 'medium', 'low');
                CREATE TYPE currency AS ENUM ('USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY');
                CREATE TYPE token_operation AS ENUM ('deduction', 'reward', 'refund', 'transfer', 'purchase');
            END $$;
        """))
        logger.info("Enum types created")
    
        # Create users table
        logger.info("Creating users table...")
        conn.execute(text("""
            CREATE TABLE users (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                email VARCHAR(255) NOT NULL UNIQUE,
                password TEXT NOT NULL,
                name VARCHAR(255),
                sol_address VARCHAR(44) UNIQUE,
                referral_code VARCHAR(10) UNIQUE,
                referred_by UUID REFERENCES users(id) ON DELETE SET NULL,
                token_balance NUMERIC(18, 8) NOT NULL DEFAULT 0,
                preferences JSONB NOT NULL DEFAULT '{}',
                status VARCHAR(20) NOT NULL DEFAULT 'active',
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT ch_positive_balance CHECK (token_balance >= 0)
            );
            CREATE INDEX ix_users_email_status ON users(email, status);
            CREATE INDEX ix_users_wallet ON users(sol_address);
            CREATE INDEX ix_users_referral ON users(referral_code);
        """))
        logger.info("Users table created")

        # Create auth_tokens table
        logger.info("Creating auth_tokens table...")
        conn.execute(text("""
            CREATE TABLE auth_tokens (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token VARCHAR(255) NOT NULL UNIQUE,
                token_type VARCHAR(20) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'active',
                scope VARCHAR(20) NOT NULL DEFAULT 'full',
                expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                meta_data JSONB,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX ix_auth_tokens_user ON auth_tokens(user_id);
            CREATE INDEX ix_auth_tokens_token ON auth_tokens(token);
            CREATE INDEX ix_auth_tokens_status ON auth_tokens(status);
        """))
        logger.info("Auth_tokens table created")

        # Create markets table
        logger.info("Creating markets table...")
        conn.execute(text("""
            CREATE TABLE markets (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(100) NOT NULL,
                type VARCHAR(20) NOT NULL,
                description TEXT,
                api_endpoint VARCHAR(255),
                api_key VARCHAR(255),
                status VARCHAR(20) NOT NULL DEFAULT 'active',
                config JSONB,
                rate_limit INTEGER NOT NULL DEFAULT 100,
                is_active BOOLEAN NOT NULL DEFAULT true,
                error_count INTEGER NOT NULL DEFAULT 0,
                requests_today INTEGER NOT NULL DEFAULT 0,
                total_requests INTEGER NOT NULL DEFAULT 0,
                success_rate FLOAT NOT NULL DEFAULT 1.0,
                avg_response_time FLOAT NOT NULL DEFAULT 0.0,
                last_error TEXT,
                last_error_at TIMESTAMP WITH TIME ZONE,
                last_successful_request TIMESTAMP WITH TIME ZONE,
                last_reset_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """))
        logger.info("Markets table created")

        # Create goals table
        logger.info("Creating goals table...")
        conn.execute(text("""
            CREATE TABLE goals (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                item_category VARCHAR(20) NOT NULL,
                title VARCHAR(255) NOT NULL,
                constraints JSONB NOT NULL,
                deadline TIMESTAMP WITH TIME ZONE,
                status VARCHAR(20) NOT NULL DEFAULT 'active',
                priority INTEGER NOT NULL DEFAULT 1,
                max_matches INTEGER,
                max_tokens NUMERIC(18, 8),
                notification_threshold NUMERIC(3, 2),
                auto_buy_threshold NUMERIC(3, 2),
                last_checked_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT ch_positive_max_tokens CHECK (max_tokens >= 0)
            );
            CREATE INDEX ix_goals_user_status ON goals(user_id, status);
            CREATE INDEX ix_goals_priority_deadline ON goals(priority, deadline);
        """))
        logger.info("Goals table created")

        # Create deals table
        logger.info("Creating deals table...")
        conn.execute(text("""
            CREATE TABLE deals (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                goal_id UUID REFERENCES goals(id) ON DELETE CASCADE,
                market_id UUID NOT NULL REFERENCES markets(id) ON DELETE CASCADE,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                url TEXT NOT NULL,
                price NUMERIC(10, 2) NOT NULL,
                original_price NUMERIC(10, 2),
                currency VARCHAR(3) DEFAULT 'USD',
                source VARCHAR(50) NOT NULL,
                image_url TEXT,
                category VARCHAR(50),
                found_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP WITH TIME ZONE,
                status VARCHAR(20) DEFAULT 'active',
                seller_info JSONB,
                availability JSONB,
                deal_metadata JSONB,
                price_metadata JSONB,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT true,
                CONSTRAINT ch_positive_price CHECK (price > 0),
                CONSTRAINT ch_original_price_gt_price CHECK (original_price IS NULL OR original_price > price),
                CONSTRAINT uq_deal_url_goal UNIQUE (url, goal_id)
            );
            CREATE INDEX ix_deals_status_found ON deals(status, found_at);
            CREATE INDEX ix_deals_goal_status ON deals(goal_id, status);
            CREATE INDEX ix_deals_market_status ON deals(market_id, status);
        """))
        logger.info("Deals table created")

        # Create notifications table
        logger.info("Creating notifications table...")
        conn.execute(text("""
            CREATE TABLE notifications (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                goal_id UUID REFERENCES goals(id) ON DELETE SET NULL,
                deal_id UUID REFERENCES deals(id) ON DELETE SET NULL,
                title VARCHAR(255) NOT NULL,
                message TEXT NOT NULL,
                type VARCHAR(20) NOT NULL,
                priority VARCHAR(20) NOT NULL DEFAULT 'medium',
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                channels JSONB NOT NULL DEFAULT '["in_app"]',
                action_url VARCHAR(2048),
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                sent_at TIMESTAMP WITH TIME ZONE,
                delivered_at TIMESTAMP WITH TIME ZONE,
                read_at TIMESTAMP WITH TIME ZONE,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT ch_sent_after_created CHECK (sent_at IS NULL OR sent_at >= created_at),
                CONSTRAINT ch_delivered_after_sent CHECK (delivered_at IS NULL OR delivered_at >= sent_at),
                CONSTRAINT ch_read_after_delivered CHECK (read_at IS NULL OR read_at >= delivered_at)
            );
            CREATE INDEX ix_notifications_user_status ON notifications(user_id, status);
            CREATE INDEX ix_notifications_goal ON notifications(goal_id);
            CREATE INDEX ix_notifications_deal ON notifications(deal_id);
        """))
        logger.info("Notifications table created")

        # Create token_balances table
        logger.info("Creating token_balances table...")
        conn.execute(text("""
            CREATE TABLE token_balances (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                balance NUMERIC(18, 8) NOT NULL DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT ch_positive_balance CHECK (balance >= 0)
            );
            CREATE INDEX ix_token_balances_user_id ON token_balances(user_id);
        """))
        logger.info("Token_balances table created")

        # Create token_transactions table
        logger.info("Creating token_transactions table...")
        conn.execute(text("""
            CREATE TABLE token_transactions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                type VARCHAR(20) NOT NULL,
                amount NUMERIC(18, 8) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                tx_hash VARCHAR(66),
                block_number INTEGER,
                gas_used NUMERIC(18, 8),
                gas_price NUMERIC(18, 8),
                network_fee NUMERIC(18, 8),
                meta_data JSONB,
                error TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                max_retries INTEGER NOT NULL DEFAULT 3,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP WITH TIME ZONE,
                CONSTRAINT ch_positive_amount CHECK (amount > 0),
                CONSTRAINT ch_positive_network_fee CHECK (network_fee >= 0)
            );
            CREATE INDEX ix_token_transactions_user ON token_transactions(user_id, created_at);
            CREATE INDEX ix_token_transactions_hash ON token_transactions(tx_hash);
            CREATE INDEX ix_token_transactions_status ON token_transactions(status);
            CREATE INDEX ix_token_transactions_type ON token_transactions(type);
        """))
        logger.info("Token_transactions table created")

        # Create token_balance_history table
        logger.info("Creating token_balance_history table...")
        conn.execute(text("""
            CREATE TABLE token_balance_history (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_balance_id UUID NOT NULL REFERENCES token_balances(id) ON DELETE CASCADE,
                balance_before NUMERIC(18, 8) NOT NULL,
                balance_after NUMERIC(18, 8) NOT NULL,
                change_amount NUMERIC(18, 8) NOT NULL,
                change_type VARCHAR(20) NOT NULL,
                reason TEXT NOT NULL,
                transaction_data JSONB,
                transaction_id UUID REFERENCES token_transactions(id) ON DELETE CASCADE,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT ch_nonzero_change CHECK (change_amount != 0),
                CONSTRAINT ch_balance_change_match CHECK (
                    (change_type = 'deduction' AND balance_after = balance_before - change_amount) OR
                    (change_type IN ('reward', 'refund') AND balance_after = balance_before + change_amount)
                )
            );
            CREATE INDEX ix_token_balance_history_user ON token_balance_history(user_id);
            CREATE INDEX ix_token_balance_history_type ON token_balance_history(change_type);
        """))
        logger.info("Token_balance_history table created")

        # Create token_pricing table
        logger.info("Creating token_pricing table...")
        conn.execute(text("""
            CREATE TABLE token_pricing (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                service_type VARCHAR(50) NOT NULL,
                token_cost NUMERIC(18, 8) NOT NULL,
                valid_from TIMESTAMP WITH TIME ZONE NOT NULL,
                valid_to TIMESTAMP WITH TIME ZONE,
                is_active BOOLEAN NOT NULL DEFAULT true
            );
            CREATE INDEX ix_token_pricing_active ON token_pricing(is_active, valid_from);
        """))
        logger.info("Token_pricing table created")

        # Create price_histories table
        logger.info("Creating price_histories table...")
        conn.execute(text("""
            CREATE TABLE price_histories (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                deal_id UUID NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
                market_id UUID NOT NULL REFERENCES markets(id) ON DELETE CASCADE,
                price NUMERIC(10, 2) NOT NULL,
                currency VARCHAR(3) NOT NULL DEFAULT 'USD',
                source VARCHAR(50) NOT NULL,
                timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                meta_data JSONB,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT ch_positive_price CHECK (price > 0),
                CONSTRAINT uq_price_history_deal_time UNIQUE (deal_id, timestamp)
            );
            CREATE INDEX ix_price_histories_deal_time ON price_histories(deal_id, timestamp);
            CREATE INDEX ix_price_histories_market ON price_histories(market_id);
        """))
        logger.info("Price_histories table created")

        logger.info("Initial schema migration completed successfully")
        
    except Exception as e:
        logger.error(f"Error during migration: {str(e)}")
        raise

def downgrade() -> None:
    """Downgrade database schema."""
    try:
        logger.info("Starting schema downgrade")
        conn = op.get_bind()
        
        # Drop tables in reverse order
        logger.info("Dropping tables...")
        tables = [
            'agents', 'price_tracking', 'user_preferences', 'chat_messages',
            'model_metrics', 'token_pricing', 'token_balance_history',
            'token_transactions', 'notifications', 'price_predictions',
            'price_points', 'deals', 'goals', 'markets', 'auth_tokens', 'users',
            'token_balances', 'price_histories'
        ]
        for table in tables:
            logger.info(f"Dropping table {table}")
            conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
        
        # Drop enum types
        logger.info("Dropping enum types...")
        conn.execute(text("""
            DROP TYPE IF EXISTS userstatus CASCADE;
            DROP TYPE IF EXISTS goal_status CASCADE;
            DROP TYPE IF EXISTS item_category CASCADE;
            DROP TYPE IF EXISTS markettype CASCADE;
            DROP TYPE IF EXISTS market_status CASCADE;
            DROP TYPE IF EXISTS notification_priority CASCADE;
            DROP TYPE IF EXISTS notification_status CASCADE;
            DROP TYPE IF EXISTS message_role CASCADE;
            DROP TYPE IF EXISTS message_status CASCADE;
            DROP TYPE IF EXISTS deal_status CASCADE;
            DROP TYPE IF EXISTS notification_type CASCADE;
            DROP TYPE IF EXISTS notification_channel CASCADE;
            DROP TYPE IF EXISTS task_status CASCADE;
            DROP TYPE IF EXISTS goal_priority CASCADE;
            DROP TYPE IF EXISTS currency CASCADE;
            DROP TYPE IF EXISTS token_operation CASCADE;
        """))
        logger.info("Schema downgrade completed successfully")
        
    except Exception as e:
        logger.error(f"Error during downgrade: {str(e)}")
        raise 