"""Add missing tables and fields

Revision ID: 2025021620500
Revises: 2025021620450
Create Date: 2025-02-16 20:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = '2025021620500'
down_revision: Union[str, None] = '2025021620450'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Create new ENUM types
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'marketcategory') THEN
                CREATE TYPE marketcategory AS ENUM (
                    'electronics', 'fashion', 'home', 'beauty', 'sports',
                    'toys', 'books', 'automotive', 'garden', 'pets',
                    'food', 'health', 'other'
                );
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'dealsource') THEN
                CREATE TYPE dealsource AS ENUM (
                    'manual', 'api', 'scraper', 'user', 'agent'
                );
            END IF;
        END $$;
    """)

    # Create markets table
    op.execute("""
        CREATE TABLE markets (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(255) NOT NULL,
            url TEXT NOT NULL,
            api_key TEXT,
            api_secret TEXT,
            category marketcategory NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            config JSONB NOT NULL DEFAULT '{}',
            metadata JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_market_name UNIQUE (name),
            CONSTRAINT uq_market_url UNIQUE (url)
        );
        CREATE INDEX ix_markets_category ON markets(category);
        CREATE INDEX ix_markets_active ON markets(is_active);
    """)

    # Add missing fields to deals table
    op.execute("""
        ALTER TABLE deals
        ADD COLUMN market_id UUID REFERENCES markets(id) ON DELETE CASCADE,
        ADD COLUMN deal_metadata JSONB,
        ADD COLUMN price_metadata JSONB,
        ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE,
        ALTER COLUMN source TYPE dealsource USING source::dealsource;
    """)

    # Create price_histories table
    op.execute("""
        CREATE TABLE price_histories (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            deal_id UUID NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
            market_id UUID NOT NULL REFERENCES markets(id) ON DELETE CASCADE,
            price DECIMAL(10,2) NOT NULL,
            currency VARCHAR(3) DEFAULT 'USD',
            timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            source VARCHAR(50) NOT NULL,
            price_metadata JSONB,
            CONSTRAINT uq_price_history_deal_time UNIQUE (deal_id, timestamp),
            CONSTRAINT ch_positive_historical_price CHECK (price > 0)
        );
        CREATE INDEX ix_price_histories_deal_time ON price_histories(deal_id, timestamp);
    """)

    # Create price_points table
    op.execute("""
        CREATE TABLE price_points (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            deal_id UUID NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
            price DECIMAL(10,2) NOT NULL,
            currency VARCHAR(3) DEFAULT 'USD',
            source VARCHAR(50) NOT NULL,
            timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            metadata JSONB,
            CONSTRAINT ch_positive_price_point CHECK (price > 0)
        );
        CREATE INDEX ix_price_points_deal ON price_points(deal_id);
    """)

    # Create price_trackers table
    op.execute("""
        CREATE TABLE price_trackers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            deal_id UUID NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
            target_price DECIMAL(10,2) NOT NULL,
            currency VARCHAR(3) DEFAULT 'USD',
            alert_threshold DECIMAL(10,2),
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            config JSONB NOT NULL DEFAULT '{}',
            last_check TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT ch_positive_target_price CHECK (target_price > 0),
            CONSTRAINT ch_positive_alert_threshold CHECK (alert_threshold > 0)
        );
        CREATE INDEX ix_price_trackers_deal ON price_trackers(deal_id);
        CREATE INDEX ix_price_trackers_active ON price_trackers(is_active);
    """)

    # Create price_predictions table
    op.execute("""
        CREATE TABLE price_predictions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            deal_id UUID NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
            model_name VARCHAR(50) NOT NULL,
            prediction_days INTEGER NOT NULL DEFAULT 7,
            predictions JSONB NOT NULL,
            confidence DECIMAL(5,4) NOT NULL,
            metadata JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT ch_valid_confidence CHECK (confidence >= 0 AND confidence <= 1)
        );
        CREATE INDEX ix_price_predictions_deal ON price_predictions(deal_id);
    """)

    # Create deal_scores table
    op.execute("""
        CREATE TABLE deal_scores (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            deal_id UUID NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
            score DECIMAL(5,2) NOT NULL,
            components JSONB NOT NULL,
            metadata JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT ch_valid_score CHECK (score >= 0 AND score <= 100)
        );
        CREATE INDEX ix_deal_scores_deal ON deal_scores(deal_id);
    """)

def downgrade() -> None:
    # Drop tables in reverse order
    op.execute("""
        DROP TABLE IF EXISTS deal_scores CASCADE;
        DROP TABLE IF EXISTS price_predictions CASCADE;
        DROP TABLE IF EXISTS price_trackers CASCADE;
        DROP TABLE IF EXISTS price_points CASCADE;
        DROP TABLE IF EXISTS price_histories CASCADE;
    """)

    # Remove added columns from deals table
    op.execute("""
        ALTER TABLE deals
        DROP COLUMN IF EXISTS market_id,
        DROP COLUMN IF EXISTS deal_metadata,
        DROP COLUMN IF EXISTS price_metadata,
        DROP COLUMN IF EXISTS is_active;
    """)

    # Drop markets table
    op.execute("DROP TABLE IF EXISTS markets CASCADE;")

    # Drop ENUM types
    op.execute("""
        DROP TYPE IF EXISTS dealsource;
        DROP TYPE IF EXISTS marketcategory;
    """) 