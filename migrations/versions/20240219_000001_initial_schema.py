"""Initial schema migration.

Revision ID: 20240219_000001
Revises: None
Create Date: 2024-02-19 00:00:01.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import text
import logging
from uuid import uuid4

# Configure logging
logger = logging.getLogger('alembic.revision')

# revision identifiers, used by Alembic.
revision: str = '20240219_000001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Create initial database schema."""
    try:
        logger.info("Starting initial schema migration")
        conn = op.get_bind()

        # Drop existing tables if they exist
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
            DROP TABLE IF EXISTS token_balances CASCADE;
            DROP TABLE IF EXISTS price_histories CASCADE;
        """))
        logger.info("Existing tables dropped")

        # Drop existing enum types
        logger.info("Dropping existing enum types...")
        conn.execute(text("""
            DROP TYPE IF EXISTS userstatus CASCADE;
            DROP TYPE IF EXISTS goalstatus CASCADE;
            DROP TYPE IF EXISTS marketcategory CASCADE;
            DROP TYPE IF EXISTS markettype CASCADE;
            DROP TYPE IF EXISTS marketstatus CASCADE;
            DROP TYPE IF EXISTS notificationpriority CASCADE;
            DROP TYPE IF EXISTS notificationstatus CASCADE;
            DROP TYPE IF EXISTS messagerole CASCADE;
            DROP TYPE IF EXISTS dealstatus CASCADE;
            DROP TYPE IF EXISTS transactiontype CASCADE;
            DROP TYPE IF EXISTS transactionstatus CASCADE;
            DROP TYPE IF EXISTS dealsource CASCADE;
            DROP TYPE IF EXISTS goalpriority CASCADE;
            DROP TYPE IF EXISTS tokentype CASCADE;
            DROP TYPE IF EXISTS tokenstatus CASCADE;
            DROP TYPE IF EXISTS tokenscope CASCADE;
            DROP TYPE IF EXISTS balancechangetype CASCADE;
        """))
        logger.info("Existing enum types dropped")

        # Create enum types
        logger.info("Creating enum types...")
        
        # Create each enum type with proper error handling
        conn.execute(text("""
            DO $$ 
            BEGIN
                CREATE TYPE userstatus AS ENUM ('active', 'inactive', 'suspended', 'deleted');
            EXCEPTION 
                WHEN duplicate_object THEN NULL;
            END $$;

            DO $$ 
            BEGIN
                CREATE TYPE goalstatus AS ENUM ('active', 'paused', 'completed', 'cancelled', 'failed', 'expired', 'error');
            EXCEPTION 
                WHEN duplicate_object THEN NULL;
            END $$;

            DO $$ 
            BEGIN
                CREATE TYPE marketcategory AS ENUM ('electronics', 'fashion', 'home', 'books', 'toys', 'sports', 'automotive', 'health', 'beauty', 'grocery', 'other');
            EXCEPTION 
                WHEN duplicate_object THEN NULL;
            END $$;

            DO $$ 
            BEGIN
                CREATE TYPE markettype AS ENUM ('amazon', 'walmart', 'ebay', 'target', 'bestbuy', 'test');
            EXCEPTION 
                WHEN duplicate_object THEN NULL;
            END $$;

            DO $$ 
            BEGIN
                CREATE TYPE marketstatus AS ENUM ('active', 'inactive', 'maintenance', 'rate_limited', 'error');
            EXCEPTION 
                WHEN duplicate_object THEN NULL;
            END $$;

            DO $$ 
            BEGIN
                CREATE TYPE notificationpriority AS ENUM ('critical', 'high', 'medium', 'low');
            EXCEPTION 
                WHEN duplicate_object THEN NULL;
            END $$;

            DO $$ 
            BEGIN
                CREATE TYPE goalpriority AS ENUM ('high', 'medium', 'low');
            EXCEPTION 
                WHEN duplicate_object THEN NULL;
            END $$;

            DO $$ 
            BEGIN
                CREATE TYPE notificationstatus AS ENUM ('pending', 'sent', 'delivered', 'read', 'failed');
            EXCEPTION 
                WHEN duplicate_object THEN NULL;
            END $$;

            DO $$ 
            BEGIN
                CREATE TYPE messagerole AS ENUM ('user', 'assistant', 'system');
            EXCEPTION 
                WHEN duplicate_object THEN NULL;
            END $$;

            DO $$ 
            BEGIN
                CREATE TYPE dealstatus AS ENUM ('pending', 'active', 'expired', 'sold_out', 'invalid', 'deleted');
            EXCEPTION 
                WHEN duplicate_object THEN NULL;
            END $$;

            DO $$ 
            BEGIN
                CREATE TYPE transactiontype AS ENUM ('deduction', 'reward', 'refund', 'credit');
            EXCEPTION 
                WHEN duplicate_object THEN NULL;
            END $$;

            DO $$ 
            BEGIN
                CREATE TYPE transactionstatus AS ENUM ('pending', 'completed', 'failed', 'cancelled');
            EXCEPTION 
                WHEN duplicate_object THEN NULL;
            END $$;

            DO $$ 
            BEGIN
                CREATE TYPE dealsource AS ENUM ('amazon', 'walmart', 'ebay', 'target', 'bestbuy', 'manual', 'api', 'scraper', 'user', 'agent');
            EXCEPTION 
                WHEN duplicate_object THEN NULL;
            END $$;

            DO $$ 
            BEGIN
                CREATE TYPE notificationtype AS ENUM ('system', 'deal', 'goal', 'price_alert', 'token', 'security', 'market');
            EXCEPTION 
                WHEN duplicate_object THEN NULL;
            END $$;

            DO $$ 
            BEGIN
                CREATE TYPE tokentype AS ENUM ('access', 'refresh', 'reset');
            EXCEPTION 
                WHEN duplicate_object THEN NULL;
            END $$;

            DO $$ 
            BEGIN
                CREATE TYPE tokenstatus AS ENUM ('active', 'expired', 'revoked');
            EXCEPTION 
                WHEN duplicate_object THEN NULL;
            END $$;

            DO $$ 
            BEGIN
                CREATE TYPE tokenscope AS ENUM ('full', 'limited', 'read');
            EXCEPTION 
                WHEN duplicate_object THEN NULL;
            END $$;

            DO $$ 
            BEGIN
                CREATE TYPE balancechangetype AS ENUM ('deduction', 'reward', 'refund');
            EXCEPTION 
                WHEN duplicate_object THEN NULL;
            END $$;
        """))
        logger.info("Enum types created")

        # Create users table
        logger.info("Creating users table...")
        conn.execute(text("""
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
                notification_channels JSONB NOT NULL DEFAULT '["in_app"]',
                email_verified BOOLEAN NOT NULL DEFAULT false,
                social_provider VARCHAR(50),
                social_id VARCHAR(255),
                last_payment_at TIMESTAMP WITH TIME ZONE,
                last_login_at TIMESTAMP WITH TIME ZONE,
                active_goals_count INTEGER NOT NULL DEFAULT 0,
                total_deals_found INTEGER NOT NULL DEFAULT 0,
                success_rate NUMERIC(5,4) NOT NULL DEFAULT 0,
                total_tokens_spent NUMERIC(18,8) NOT NULL DEFAULT 0,
                total_rewards_earned NUMERIC(18,8) NOT NULL DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT ch_positive_balance CHECK (token_balance >= 0),
                CONSTRAINT uq_user_email UNIQUE (email),
                CONSTRAINT uq_user_wallet UNIQUE (sol_address),
                CONSTRAINT uq_user_referral UNIQUE (referral_code)
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
                status VARCHAR(20) DEFAULT 'active',
                scope VARCHAR(20) DEFAULT 'full',
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

        # Create markets table with unique name constraint
        logger.info("Creating markets table...")
        conn.execute(text("""
            CREATE TABLE markets (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(100) NOT NULL,
                type markettype NOT NULL,
                description TEXT,
                api_endpoint VARCHAR(255),
                api_key VARCHAR(255),
                status marketstatus NOT NULL DEFAULT 'active',
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
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_market_name UNIQUE (name)
            );
            CREATE INDEX ix_markets_type_status ON markets(type, status);
            CREATE INDEX ix_markets_active ON markets(is_active);
        """))
        logger.info("Markets table created")

        # Create goals table
        logger.info("Creating goals table...")
        conn.execute(text("""
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
                matches_found INTEGER NOT NULL DEFAULT 0,
                deals_processed INTEGER NOT NULL DEFAULT 0,
                tokens_spent NUMERIC(18,8) NOT NULL DEFAULT 0,
                rewards_earned NUMERIC(18,8) NOT NULL DEFAULT 0,
                last_processed_at TIMESTAMP WITH TIME ZONE,
                processing_stats JSONB NOT NULL DEFAULT '{}',
                best_match_score NUMERIC(3,2),
                average_match_score NUMERIC(3,2),
                active_deals_count INTEGER NOT NULL DEFAULT 0,
                success_rate NUMERIC(3,2) NOT NULL DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_checked_at TIMESTAMP WITH TIME ZONE,
                CONSTRAINT ch_positive_tokens CHECK (tokens_spent >= 0),
                CONSTRAINT ch_positive_rewards CHECK (rewards_earned >= 0)
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
                price NUMERIC(10,2) NOT NULL,
                original_price NUMERIC(10,2),
                currency VARCHAR(3) DEFAULT 'USD',
                source dealsource NOT NULL DEFAULT 'api',
                image_url TEXT,
                category marketcategory,
                found_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP WITH TIME ZONE,
                status dealstatus DEFAULT 'active',
                seller_info JSONB,
                availability JSONB,
                deal_metadata JSONB,
                price_metadata JSONB,
                is_active BOOLEAN NOT NULL DEFAULT true,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT ch_positive_price CHECK (price > 0),
                CONSTRAINT ch_original_price_gt_price CHECK (original_price IS NULL OR original_price > price),
                CONSTRAINT uq_deal_url_goal UNIQUE (url, goal_id)
            );
            CREATE INDEX ix_deals_status_found ON deals(status, found_at);
            CREATE INDEX ix_deals_goal_status ON deals(goal_id, status);
            CREATE INDEX ix_deals_market_status ON deals(market_id, status);
        """))
        logger.info("Deals table created")

        # Create price_points table
        logger.info("Creating price_points table...")
        conn.execute(text("""
            CREATE TABLE price_points (
                id SERIAL PRIMARY KEY,
                deal_id UUID NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
                price DECIMAL(10,2) NOT NULL,
                currency VARCHAR(3) DEFAULT 'USD',
                source VARCHAR(50) NOT NULL,
                timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                meta_data JSONB,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX ix_price_points_deal_id ON price_points(deal_id);
        """))
        logger.info("Price_points table created")

        # Create deal_matches table
        logger.info("Creating deal_matches table...")
        conn.execute(text("""
            CREATE TABLE deal_matches (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                goal_id UUID NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
                deal_id UUID NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
                match_score FLOAT NOT NULL,
                match_criteria JSONB NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT ch_match_score CHECK (match_score >= 0 AND match_score <= 1),
                CONSTRAINT uq_goal_deal UNIQUE (goal_id, deal_id)
            );
            CREATE INDEX ix_deal_matches_goal ON deal_matches(goal_id);
            CREATE INDEX ix_deal_matches_deal ON deal_matches(deal_id);
            CREATE INDEX ix_deal_matches_score ON deal_matches(match_score);
        """))
        logger.info("Deal_matches table created")

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
                priority notificationpriority DEFAULT 'medium',
                status notificationstatus DEFAULT 'pending',
                channels JSONB NOT NULL DEFAULT '["in_app"]',
                notification_metadata JSONB,
                action_url VARCHAR(2048),
                expires_at TIMESTAMP WITH TIME ZONE,
                schedule_for TIMESTAMP WITH TIME ZONE,
                error TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                max_retries INTEGER NOT NULL DEFAULT 3,
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
            CREATE INDEX ix_notifications_schedule_status ON notifications(schedule_for, status);
        """))
        logger.info("Notifications table created")

        # Create token_balances table
        logger.info("Creating token_balances table...")
        conn.execute(text("""
            CREATE TABLE token_balances (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                balance NUMERIC(18, 8) NOT NULL DEFAULT 0.00000000,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT ch_positive_balance CHECK (balance >= 0),
                CONSTRAINT uq_token_balances_user_id UNIQUE (user_id)
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
                type transactiontype NOT NULL,
                amount NUMERIC(18, 8) NOT NULL,
                status transactionstatus NOT NULL DEFAULT 'pending',
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
                balance_before NUMERIC(18,8) NOT NULL,
                balance_after NUMERIC(18,8) NOT NULL,
                change_amount NUMERIC(18,8) NOT NULL,
                change_type transactiontype NOT NULL,
                reason VARCHAR(255),
                transaction_data JSONB,
                transaction_id UUID REFERENCES token_transactions(id),
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT ch_balance_change_match CHECK (
                    (
                        change_type = 'deduction' AND 
                        balance_after = balance_before - change_amount
                    ) OR (
                        change_type IN ('reward', 'refund', 'credit') AND 
                        balance_after = balance_before + change_amount
                    )
                )
            );
            CREATE INDEX ix_token_balance_history_user ON token_balance_history(user_id);
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
                is_active BOOLEAN NOT NULL DEFAULT true,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX ix_token_pricing_active ON token_pricing(is_active, valid_from);

            -- Insert initial pricing data
            INSERT INTO token_pricing (service_type, token_cost, valid_from, is_active)
            VALUES 
                ('deal_validation', 1.0, CURRENT_TIMESTAMP, true),
                ('deal_comparison', 2.0, CURRENT_TIMESTAMP, true),
                ('deal_predictions', 3.0, CURRENT_TIMESTAMP, true),
                ('deal_analysis', 2.0, CURRENT_TIMESTAMP, true),
                ('get_deals', 1.0, CURRENT_TIMESTAMP, true),
                ('get_similar_deals', 2.0, CURRENT_TIMESTAMP, true);
        """))
        logger.info("Token_pricing table created with initial data")

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

        # Create messagestatus enum
        logger.info("Creating messagestatus enum...")
        conn.execute(text("""
            DO $$ BEGIN
                CREATE TYPE messagestatus AS ENUM ('pending', 'processing', 'completed', 'failed');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """))
        logger.info("Messagestatus enum created")

        # Create chat_messages table
        logger.info("Creating chat_messages table...")
        conn.execute(text("""
            CREATE TABLE chat_messages (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                conversation_id UUID NOT NULL,
                role messagerole NOT NULL,
                content TEXT NOT NULL,
                status messagestatus NOT NULL DEFAULT 'pending',
                tokens_used INTEGER,
                context JSONB,
                chat_metadata JSONB,
                error TEXT,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX ix_chat_messages_user_id ON chat_messages(user_id);
            CREATE INDEX ix_chat_messages_conversation_id ON chat_messages(conversation_id);
            CREATE INDEX ix_chat_messages_created_at ON chat_messages(created_at);
        """))
        logger.info("Chat_messages table created")

        # Create user_preferences table
        logger.info("Creating user_preferences table...")
        conn.execute(text("""
            CREATE TABLE user_preferences (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE UNIQUE,
                theme VARCHAR(255) NOT NULL DEFAULT 'system',
                language VARCHAR(255) NOT NULL DEFAULT 'en',
                timezone VARCHAR(255) NOT NULL DEFAULT 'UTC',
                enabled_channels VARCHAR[] NOT NULL DEFAULT ARRAY['in_app', 'email'],
                notification_frequency JSONB NOT NULL DEFAULT '{
                    "deal_match": "immediate", 
                    "goal_completed": "immediate", 
                    "goal_expired": "daily", 
                    "price_drop": "immediate", 
                    "token_low": "daily", 
                    "system": "immediate", 
                    "custom": "immediate"
                }'::jsonb,
                time_windows JSONB NOT NULL DEFAULT '{
                    "in_app": {"start_time": "09:00", "end_time": "21:00", "timezone": "UTC"},
                    "email": {"start_time": "09:00", "end_time": "21:00", "timezone": "UTC"}
                }'::jsonb,
                muted_until TIMESTAMP WITH TIME ZONE,
                do_not_disturb BOOLEAN NOT NULL DEFAULT false,
                email_digest BOOLEAN NOT NULL DEFAULT true,
                push_enabled BOOLEAN NOT NULL DEFAULT true,
                sms_enabled BOOLEAN NOT NULL DEFAULT false,
                telegram_enabled BOOLEAN NOT NULL DEFAULT false,
                discord_enabled BOOLEAN NOT NULL DEFAULT false,
                minimum_priority VARCHAR(10) NOT NULL DEFAULT 'low',
                deal_alert_settings JSONB NOT NULL DEFAULT '{}'::jsonb,
                price_alert_settings JSONB NOT NULL DEFAULT '{}'::jsonb,
                email_preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX ix_user_preferences_user_id ON user_preferences(user_id);
            CREATE INDEX ix_user_preferences_created_at ON user_preferences(created_at);
        """))
        logger.info("User_preferences table created")

        # Create agents table
        logger.info("Creating agents table...")
        conn.execute(text("""
            CREATE TABLE agents (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                goal_id UUID REFERENCES goals(id) ON DELETE CASCADE,
                name VARCHAR(100) NOT NULL,
                agent_type VARCHAR(20) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'inactive',
                description TEXT,
                config JSONB,
                meta_data JSONB,
                error_count INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                last_active TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT chk_agent_type CHECK (agent_type IN ('goal', 'market', 'price', 'chat')),
                CONSTRAINT chk_agent_status CHECK (status IN ('active', 'inactive', 'busy', 'error'))
            );
            CREATE INDEX ix_agents_type ON agents(agent_type);
            CREATE INDEX ix_agents_status ON agents(status);
            CREATE INDEX ix_agents_user ON agents(user_id);
            CREATE INDEX ix_agents_goal ON agents(goal_id);
        """))
        logger.info("Agents table created")

        # Create token_wallets table
        logger.info("Creating token_wallets table...")
        conn.execute(text("""
            CREATE TABLE token_wallets (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                address VARCHAR(44) NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT true,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP WITH TIME ZONE,
                network VARCHAR(20) NOT NULL DEFAULT 'mainnet-beta',
                data JSONB,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_wallet_address_network UNIQUE (address, network)
            );
            CREATE INDEX ix_token_wallets_user_id ON token_wallets(user_id);
            CREATE INDEX ix_token_wallets_address ON token_wallets(address);
            CREATE INDEX ix_token_wallets_network ON token_wallets(network);
        """))
        logger.info("Token_wallets table created")

        # Create deal_scores table
        logger.info("Creating deal_scores table...")
        conn.execute(text("""
            CREATE TABLE deal_scores (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                deal_id UUID NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                score FLOAT NOT NULL,
                confidence FLOAT NOT NULL,
                factors JSONB NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX ix_deal_scores_deal ON deal_scores(deal_id);
            CREATE INDEX ix_deal_scores_user ON deal_scores(user_id);
        """))
        logger.info("Deal_scores table created")

        # Create chat_contexts table
        logger.info("Creating chat_contexts table...")
        conn.execute(text("""
            CREATE TABLE chat_contexts (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                conversation_id UUID NOT NULL,
                context_type VARCHAR(50) NOT NULL,
                context_data JSONB NOT NULL,
                expires_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX ix_chat_contexts_user ON chat_contexts(user_id);
            CREATE INDEX ix_chat_contexts_conversation ON chat_contexts(conversation_id);
            CREATE INDEX ix_chat_contexts_expires ON chat_contexts(expires_at);
        """))
        logger.info("Chat_contexts table created")

        # Create tracked_deals table
        logger.info("Creating tracked_deals table...")
        conn.execute(text("""
            CREATE TABLE tracked_deals (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                deal_id UUID NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
                status VARCHAR(20) NOT NULL DEFAULT 'active',
                tracking_started TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_checked TIMESTAMP WITH TIME ZONE,
                last_price NUMERIC(10, 2),
                is_favorite BOOLEAN NOT NULL DEFAULT false,
                notify_on_price_drop BOOLEAN NOT NULL DEFAULT true,
                notify_on_availability BOOLEAN NOT NULL DEFAULT true,
                price_threshold NUMERIC(10, 2),
                tracking_metadata JSONB,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX ix_tracked_deals_user ON tracked_deals(user_id);
            CREATE INDEX ix_tracked_deals_deal ON tracked_deals(deal_id);
            CREATE INDEX ix_tracked_deals_status ON tracked_deals(status);
        """))
        logger.info("Tracked_deals table created")

        # Create updated_at trigger function
        logger.info("Creating updated_at trigger function...")
        conn.execute(text("""
            CREATE OR REPLACE FUNCTION update_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = timezone('UTC', CURRENT_TIMESTAMP);
                RETURN NEW;
            END;
            $$ language 'plpgsql';
        """))
        logger.info("Updated_at trigger function created")

        # Create triggers for updated_at columns
        logger.info("Creating updated_at triggers...")
        conn.execute(text("""
            CREATE TRIGGER update_users_updated_at
                BEFORE UPDATE ON users
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();

            CREATE TRIGGER update_auth_tokens_updated_at
                BEFORE UPDATE ON auth_tokens
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();

            CREATE TRIGGER update_markets_updated_at
                BEFORE UPDATE ON markets
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();

            CREATE TRIGGER update_goals_updated_at
                BEFORE UPDATE ON goals
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();

            CREATE TRIGGER update_deals_updated_at
                BEFORE UPDATE ON deals
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();

            CREATE TRIGGER update_notifications_updated_at
                BEFORE UPDATE ON notifications
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();

            CREATE TRIGGER update_token_balances_updated_at
                BEFORE UPDATE ON token_balances
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();

            CREATE TRIGGER update_token_transactions_updated_at
                BEFORE UPDATE ON token_transactions
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();

            CREATE TRIGGER update_token_balance_history_updated_at
                BEFORE UPDATE ON token_balance_history
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();

            CREATE TRIGGER update_token_pricing_updated_at
                BEFORE UPDATE ON token_pricing
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();

            CREATE TRIGGER update_price_histories_updated_at
                BEFORE UPDATE ON price_histories
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();

            CREATE TRIGGER update_user_preferences_updated_at
                BEFORE UPDATE ON user_preferences
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();

            CREATE TRIGGER update_chat_messages_updated_at
                BEFORE UPDATE ON chat_messages
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();

            CREATE TRIGGER update_agents_updated_at
                BEFORE UPDATE ON agents
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();

            CREATE TRIGGER update_token_wallets_updated_at
                BEFORE UPDATE ON token_wallets
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();

            CREATE TRIGGER update_deal_scores_updated_at
                BEFORE UPDATE ON deal_scores
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();

            CREATE TRIGGER update_chat_contexts_updated_at
                BEFORE UPDATE ON chat_contexts
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();

            CREATE TRIGGER update_tracked_deals_updated_at
                BEFORE UPDATE ON tracked_deals
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();
        """))
        logger.info("Updated_at triggers created")

        logger.info("Initial schema migration completed successfully")
        
    except Exception as e:
        logger.error(f"Error during migration: {str(e)}")
        raise

def downgrade() -> None:
    """Downgrade database schema."""
    try:
        logger.info("Starting schema downgrade")
        conn = op.get_bind()
        
        # Drop triggers first
        logger.info("Dropping triggers...")
        conn.execute(text("""
            DROP TRIGGER IF EXISTS update_users_updated_at ON users;
            DROP TRIGGER IF EXISTS update_auth_tokens_updated_at ON auth_tokens;
            DROP TRIGGER IF EXISTS update_markets_updated_at ON markets;
            DROP TRIGGER IF EXISTS update_goals_updated_at ON goals;
            DROP TRIGGER IF EXISTS update_deals_updated_at ON deals;
            DROP TRIGGER IF EXISTS update_notifications_updated_at ON notifications;
            DROP TRIGGER IF EXISTS update_token_balances_updated_at ON token_balances;
            DROP TRIGGER IF EXISTS update_token_transactions_updated_at ON token_transactions;
            DROP TRIGGER IF EXISTS update_token_balance_history_updated_at ON token_balance_history;
            DROP TRIGGER IF EXISTS update_token_pricing_updated_at ON token_pricing;
            DROP TRIGGER IF EXISTS update_price_histories_updated_at ON price_histories;
            DROP TRIGGER IF EXISTS update_user_preferences_updated_at ON user_preferences;
            DROP TRIGGER IF EXISTS update_chat_messages_updated_at ON chat_messages;
            DROP TRIGGER IF EXISTS update_agents_updated_at ON agents;
            DROP TRIGGER IF EXISTS update_token_wallets_updated_at ON token_wallets;
            DROP TRIGGER IF EXISTS update_deal_scores_updated_at ON deal_scores;
            DROP TRIGGER IF EXISTS update_chat_contexts_updated_at ON chat_contexts;
            DROP TRIGGER IF EXISTS update_tracked_deals_updated_at ON tracked_deals;
        """))
        logger.info("Triggers dropped")

        # Drop trigger function
        logger.info("Dropping trigger function...")
        conn.execute(text("DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;"))
        logger.info("Trigger function dropped")
        
        # Drop tables in reverse order
        logger.info("Dropping tables...")
        tables = [
            'agents', 'chat_messages', 'chat_contexts', 'user_preferences', 'price_histories',
            'token_pricing', 'token_balance_history', 'token_transactions',
            'token_balances', 'token_wallets', 'deal_scores', 'tracked_deals', 'notifications', 
            'deals', 'goals', 'markets', 'auth_tokens', 'users'
        ]
        for table in tables:
            logger.info(f"Dropping table {table}")
            conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
        
        # Drop enum types
        logger.info("Dropping enum types...")
        conn.execute(text("""
            DROP TYPE IF EXISTS dealsource CASCADE;
            DROP TYPE IF EXISTS transactiontype CASCADE;
            DROP TYPE IF EXISTS transactionstatus CASCADE;
            DROP TYPE IF EXISTS dealstatus CASCADE;
            DROP TYPE IF EXISTS messagerole CASCADE;
            DROP TYPE IF EXISTS notificationstatus CASCADE;
            DROP TYPE IF EXISTS notificationpriority CASCADE;
            DROP TYPE IF EXISTS marketstatus CASCADE;
            DROP TYPE IF EXISTS markettype CASCADE;
            DROP TYPE IF EXISTS marketcategory CASCADE;
            DROP TYPE IF EXISTS goalstatus CASCADE;
            DROP TYPE IF EXISTS userstatus CASCADE;
        """))
        logger.info("Schema downgrade completed successfully")
        
    except Exception as e:
        logger.error(f"Error during downgrade: {str(e)}")
        raise 