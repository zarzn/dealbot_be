# Database Schema Documentation

## Overview

This document provides a comprehensive overview of the database schema used in the AI Agentic Deals System. The system uses PostgreSQL as its primary relational database, following SQLAlchemy 2.0 style for ORM mapping. The schema is designed to support the core functionality of deal discovery, analysis, user management, and token-based transactions.

## Database Architecture

### Database Technology

- **PostgreSQL 14+**: Primary relational database for structured data
- **SQLAlchemy 2.0**: ORM framework for database interactions
- **Alembic**: Database migration tool

### Database Design Principles

1. **Normalization**: Tables are designed to follow 3NF (Third Normal Form) to minimize redundancy
2. **Referential Integrity**: Foreign key constraints enforce data consistency
3. **Performance Optimization**: Strategic indexing and query optimization
4. **Data Type Precision**: Appropriate data types selected for each column
5. **Soft Deletion**: Logical deletion instead of physical where appropriate

## Core Tables

### Users

Stores user account information and authentication details.

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    verification_token VARCHAR(255),
    role VARCHAR(50) NOT NULL DEFAULT 'user',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
```

### User Preferences

Stores user-specific preferences for deal discovery and notifications.

```sql
CREATE TABLE user_preferences (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    notification_email BOOLEAN NOT NULL DEFAULT TRUE,
    notification_push BOOLEAN NOT NULL DEFAULT TRUE,
    theme VARCHAR(50) DEFAULT 'light',
    deal_categories JSONB,
    preferred_markets JSONB,
    min_discount_percentage INTEGER,
    max_price NUMERIC(10, 2),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

### Deals

Stores deal information scraped from various sources.

```sql
CREATE TABLE deals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    original_price NUMERIC(10, 2) NOT NULL,
    current_price NUMERIC(10, 2) NOT NULL,
    discount_percentage NUMERIC(5, 2) NOT NULL,
    url TEXT NOT NULL,
    image_url TEXT,
    market_id UUID NOT NULL REFERENCES markets(id),
    category_id UUID REFERENCES categories(id),
    source_id UUID NOT NULL REFERENCES sources(id),
    expires_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    ai_analysis JSONB,
    metadata JSONB,
    CONSTRAINT positive_prices CHECK (original_price > 0 AND current_price > 0),
    CONSTRAINT valid_discount CHECK (discount_percentage >= 0 AND discount_percentage <= 100)
);

CREATE INDEX idx_deals_market ON deals(market_id);
CREATE INDEX idx_deals_category ON deals(category_id);
CREATE INDEX idx_deals_source ON deals(source_id);
CREATE INDEX idx_deals_status ON deals(status);
CREATE INDEX idx_deals_created_at ON deals(created_at);
CREATE INDEX idx_deals_expires_at ON deals(expires_at);
CREATE INDEX idx_deals_discount_percentage ON deals(discount_percentage);
CREATE INDEX idx_deals_current_price ON deals(current_price);
```

### Markets

Stores information about e-commerce marketplaces.

```sql
CREATE TABLE markets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    url TEXT,
    logo_url TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_markets_status ON markets(status);
```

### Categories

Stores product categories for deal classification.

```sql
CREATE TABLE categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    parent_id UUID REFERENCES categories(id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT unique_name_per_parent UNIQUE (name, parent_id)
);

CREATE INDEX idx_categories_parent ON categories(parent_id);
```

### Sources

Stores information about deal data sources.

```sql
CREATE TABLE sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    type VARCHAR(50) NOT NULL,
    configuration JSONB,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    reliability_score NUMERIC(3, 2) NOT NULL DEFAULT 1.0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT valid_reliability_score CHECK (reliability_score >= 0 AND reliability_score <= 1)
);

CREATE INDEX idx_sources_type ON sources(type);
CREATE INDEX idx_sources_status ON sources(status);
```

### Saved Deals

Maps users to their saved deals.

```sql
CREATE TABLE saved_deals (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    deal_id UUID NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
    saved_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    notes TEXT,
    PRIMARY KEY (user_id, deal_id)
);

CREATE INDEX idx_saved_deals_user ON saved_deals(user_id);
CREATE INDEX idx_saved_deals_deal ON saved_deals(deal_id);
CREATE INDEX idx_saved_deals_saved_at ON saved_deals(saved_at);
```

### User Goals

Stores user-defined deal search goals.

```sql
CREATE TABLE user_goals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    parameters JSONB NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    progress_metrics JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    target_date TIMESTAMP WITH TIME ZONE,
    completion_date TIMESTAMP WITH TIME ZONE,
    priority INTEGER NOT NULL DEFAULT 5
);

CREATE INDEX idx_user_goals_user ON user_goals(user_id);
CREATE INDEX idx_user_goals_status ON user_goals(status);
CREATE INDEX idx_user_goals_priority ON user_goals(priority);
```

### Goal Deals

Maps user goals to relevant deals.

```sql
CREATE TABLE goal_deals (
    goal_id UUID NOT NULL REFERENCES user_goals(id) ON DELETE CASCADE,
    deal_id UUID NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
    relevance_score NUMERIC(5, 2) NOT NULL,
    matched_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    PRIMARY KEY (goal_id, deal_id)
);

CREATE INDEX idx_goal_deals_goal ON goal_deals(goal_id);
CREATE INDEX idx_goal_deals_deal ON goal_deals(deal_id);
CREATE INDEX idx_goal_deals_relevance ON goal_deals(relevance_score);
```

## Token System Tables

### User Token Balances

Tracks user token balances.

```sql
CREATE TABLE user_token_balances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    balance INTEGER NOT NULL DEFAULT 0,
    lifetime_earned INTEGER NOT NULL DEFAULT 0,
    lifetime_spent INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT positive_balance CHECK (balance >= 0)
);

CREATE UNIQUE INDEX idx_token_balances_user ON user_token_balances(user_id);
```

### Token Transactions

Records all token balance changes.

```sql
CREATE TABLE token_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    transaction_type VARCHAR(50) NOT NULL,
    amount INTEGER NOT NULL,
    balance_after INTEGER NOT NULL,
    description TEXT,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    reference_id UUID,
    CONSTRAINT valid_amount CHECK (amount != 0)
);

CREATE INDEX idx_token_transactions_user ON token_transactions(user_id);
CREATE INDEX idx_token_transactions_type ON token_transactions(transaction_type);
CREATE INDEX idx_token_transactions_created_at ON token_transactions(created_at);
CREATE INDEX idx_token_transactions_reference ON token_transactions(reference_id);
```

### Token Packages

Defines token packages available for purchase.

```sql
CREATE TABLE token_packages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    token_amount INTEGER NOT NULL,
    price_usd NUMERIC(10, 2) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    description TEXT,
    discount_percentage INTEGER DEFAULT 0,
    CONSTRAINT positive_token_amount CHECK (token_amount > 0),
    CONSTRAINT positive_price CHECK (price_usd > 0)
);

CREATE INDEX idx_token_packages_active ON token_packages(is_active);
```

### Token Redemption Codes

Manages one-time token redemption codes.

```sql
CREATE TABLE token_redemption_codes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(50) UNIQUE NOT NULL,
    token_amount INTEGER NOT NULL,
    max_redemptions INTEGER NOT NULL DEFAULT 1,
    redemptions_count INTEGER NOT NULL DEFAULT 0,
    expires_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by UUID REFERENCES users(id),
    CONSTRAINT positive_token_amount CHECK (token_amount > 0),
    CONSTRAINT valid_max_redemptions CHECK (max_redemptions > 0)
);

CREATE INDEX idx_redemption_codes_active ON token_redemption_codes(is_active);
CREATE INDEX idx_redemption_codes_expires ON token_redemption_codes(expires_at);
```

## Social and Sharing Tables

### Shared Deals

Tracks deals shared by users.

```sql
CREATE TABLE shared_deals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    deal_id UUID NOT NULL REFERENCES deals(id),
    share_type VARCHAR(50) NOT NULL,
    recipients JSONB,
    message TEXT,
    public_link_id VARCHAR(100) UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    click_count INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_shared_deals_user ON shared_deals(user_id);
CREATE INDEX idx_shared_deals_deal ON shared_deals(deal_id);
CREATE INDEX idx_shared_deals_public_link ON shared_deals(public_link_id);
CREATE INDEX idx_shared_deals_created_at ON shared_deals(created_at);
```

### Social Interactions

Records user interactions with deals.

```sql
CREATE TABLE social_interactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    deal_id UUID NOT NULL REFERENCES deals(id),
    interaction_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    metadata JSONB
);

CREATE INDEX idx_social_interactions_user ON social_interactions(user_id);
CREATE INDEX idx_social_interactions_deal ON social_interactions(deal_id);
CREATE INDEX idx_social_interactions_type ON social_interactions(interaction_type);
CREATE INDEX idx_social_interactions_created_at ON social_interactions(created_at);
```

## AI Component Tables

### AI Analysis Requests

Tracks AI analysis requests for deals.

```sql
CREATE TABLE ai_analysis_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    deal_id UUID REFERENCES deals(id),
    url TEXT,
    product_name TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    requested_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    tokens_charged INTEGER,
    model_used VARCHAR(100),
    result JSONB,
    error_message TEXT
);

CREATE INDEX idx_ai_requests_user ON ai_analysis_requests(user_id);
CREATE INDEX idx_ai_requests_deal ON ai_analysis_requests(deal_id);
CREATE INDEX idx_ai_requests_status ON ai_analysis_requests(status);
CREATE INDEX idx_ai_requests_requested_at ON ai_analysis_requests(requested_at);
```

### AI Models

Tracks LLM models used in the system.

```sql
CREATE TABLE ai_models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    provider VARCHAR(100) NOT NULL,
    version VARCHAR(100) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_fallback BOOLEAN NOT NULL DEFAULT FALSE,
    token_cost_per_1k NUMERIC(10, 6) NOT NULL,
    max_tokens INTEGER NOT NULL,
    capabilities JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ai_models_active ON ai_models(is_active);
CREATE INDEX idx_ai_models_provider ON ai_models(provider);
```

### AI Prompt Templates

Stores templates for AI prompts.

```sql
CREATE TABLE ai_prompt_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    template_text TEXT NOT NULL,
    description TEXT,
    version VARCHAR(50) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    usage_type VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_prompt_templates_active ON ai_prompt_templates(is_active);
CREATE INDEX idx_prompt_templates_usage_type ON ai_prompt_templates(usage_type);
```

## Notification Tables

### Notifications

Stores user notifications.

```sql
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    read_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB,
    action_url TEXT
);

CREATE INDEX idx_notifications_user ON notifications(user_id);
CREATE INDEX idx_notifications_created_at ON notifications(created_at);
CREATE INDEX idx_notifications_is_read ON notifications(is_read);
CREATE INDEX idx_notifications_type ON notifications(type);
```

### Notification Settings

Controls user notification preferences.

```sql
CREATE TABLE notification_settings (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    email_deal_alerts BOOLEAN NOT NULL DEFAULT TRUE,
    email_price_drops BOOLEAN NOT NULL DEFAULT TRUE,
    email_goal_updates BOOLEAN NOT NULL DEFAULT TRUE,
    push_deal_alerts BOOLEAN NOT NULL DEFAULT TRUE,
    push_price_drops BOOLEAN NOT NULL DEFAULT TRUE,
    push_goal_updates BOOLEAN NOT NULL DEFAULT TRUE,
    quiet_hours_start TIME,
    quiet_hours_end TIME,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

## Enums

The system uses several enums across tables for consistency:

```sql
-- User Roles
CREATE TYPE user_role AS ENUM ('user', 'admin', 'moderator');

-- Deal Status
CREATE TYPE deal_status AS ENUM ('active', 'expired', 'removed');

-- Market Status
CREATE TYPE market_status AS ENUM ('active', 'inactive', 'deprecated');

-- Source Type
CREATE TYPE source_type AS ENUM ('api', 'scraper', 'affiliate', 'user_submitted');

-- Token Transaction Type
CREATE TYPE token_transaction_type AS ENUM (
    'purchase', 
    'ai_usage', 
    'signup_bonus', 
    'referral_bonus', 
    'admin_adjustment', 
    'redemption_code', 
    'refund', 
    'expiration'
);

-- Share Type
CREATE TYPE share_type AS ENUM ('email', 'link', 'social');

-- Interaction Type
CREATE TYPE interaction_type AS ENUM ('view', 'save', 'share', 'click', 'purchase');

-- Analysis Status
CREATE TYPE analysis_status AS ENUM ('pending', 'processing', 'completed', 'failed');

-- Notification Type
CREATE TYPE notification_type AS ENUM (
    'deal_alert', 
    'price_drop', 
    'goal_update', 
    'token_update', 
    'system_message'
);
```

## Relationships Diagram

```
┌─────────────┐       ┌───────────────┐       ┌───────────┐
│   Users     │───┐   │ User Preferences│      │  Markets  │
└─────────────┘   │   └───────────────┘       └─────┬─────┘
      │           │                                 │
      │           │                                 │
┌─────▼───────┐   │   ┌───────────────┐       ┌─────▼─────┐
│   Saved     │   │   │  User Goals    │       │   Deals   │
│   Deals     │   │   └─────┬─────────┘       └─────┬─────┘
└─────────────┘   │         │                       │
      ▲           │         │                       │
      │           │    ┌────▼──────┐                │
┌─────┴───────┐   │    │ Goal Deals │◄───────────────┘
│  Shared     │   │    └────────────┘
│  Deals      │   │
└─────────────┘   │    ┌────────────────────┐
      ▲           │    │ User Token Balances │
      │           └───►└──────────┬─────────┘
┌─────┴───────┐                   │
│   Social    │                   │
│ Interactions│            ┌──────▼─────────┐
└─────────────┘            │Token Transactions│
                          └──────────────────┘
```

## SQLAlchemy Models

The database schema is represented in Python using SQLAlchemy 2.0 style models:

```python
# Example of a SQLAlchemy 2.0 model
from sqlalchemy import Column, ForeignKey, String, Boolean, DateTime, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, mapped_column, Mapped
from sqlalchemy.sql import func
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

from core.models.base import Base
from core.models.enums import UserRole

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verification_token: Mapped[Optional[str]] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(
        String(50), 
        nullable=False, 
        default=UserRole.USER.value.lower()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=False, 
        server_default=func.now(), 
        onupdate=func.now()
    )
    
    # Relationships
    preferences = relationship("UserPreference", back_populates="user", uselist=False)
    token_balance = relationship("UserTokenBalance", back_populates="user", uselist=False)
    saved_deals = relationship("SavedDeal", back_populates="user")
    goals = relationship("UserGoal", back_populates="user")
```

## Database Optimization

### Indexes

The database uses several types of indexes to optimize query performance:

1. **Primary Key Indexes**: Automatically created for all primary keys
2. **Foreign Key Indexes**: Created for all foreign key columns
3. **Composite Indexes**: Used for columns frequently queried together
4. **Expression Indexes**: For complex query conditions
5. **Partial Indexes**: For filtering on specific conditions

### Performance Optimizations

1. **Connection Pooling**:
   - Configured with appropriate pool size based on workload
   - Connection recycling to prevent stale connections
   - Statement caching for repeated queries

2. **Query Optimization**:
   - Use of `EXPLAIN ANALYZE` to identify slow queries
   - Materialized views for complex reporting queries
   - Appropriate JOIN strategies

3. **Database Configuration**:
   - Optimized for available hardware resources
   - Proper WAL configuration
   - Autovacuum settings tuned for workload

### Partitioning Strategy

For high-volume tables, partitioning is implemented:

```sql
-- Example of a time-based partitioning for token_transactions
CREATE TABLE token_transactions_y2023m01 PARTITION OF token_transactions
    FOR VALUES FROM ('2023-01-01') TO ('2023-02-01');
    
CREATE TABLE token_transactions_y2023m02 PARTITION OF token_transactions
    FOR VALUES FROM ('2023-02-01') TO ('2023-03-01');
```

## Data Migration

### Migration Strategy

The database schema is managed through Alembic migrations:

1. **Versioned Migrations**: Every schema change is versioned
2. **Reversible Changes**: Migrations include both upgrade and downgrade paths
3. **Data Migration**: Complex migrations include data transformation steps
4. **Zero-downtime Deployments**: Migrations designed to minimize locking

### Example Migration

```python
# Example Alembic migration
"""Add notification settings table

Revision ID: a1b2c3d4e5f6
Revises: previous_revision_id
Create Date: 2023-06-01 12:34:56

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'a1b2c3d4e5f6'
down_revision = 'previous_revision_id'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'notification_settings',
        sa.Column('user_id', postgresql.UUID(), nullable=False),
        sa.Column('email_deal_alerts', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('email_price_drops', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('email_goal_updates', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('push_deal_alerts', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('push_price_drops', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('push_goal_updates', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('quiet_hours_start', sa.Time(), nullable=True),
        sa.Column('quiet_hours_end', sa.Time(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id')
    )


def downgrade():
    op.drop_table('notification_settings')
```

## Security Considerations

### Data Protection

1. **Sensitive Data Encryption**:
   - Passwords are hashed using bcrypt
   - Sensitive personal information is encrypted at rest

2. **Access Control**:
   - Row-level security policies for multi-tenant data
   - Role-based access control integration

3. **Audit Logging**:
   - Database-level audit logs for sensitive operations
   - Application-level logging of data access and modifications

### Example Security Implementation

```sql
-- Row-level security example
CREATE POLICY user_data_isolation ON user_preferences
    USING (user_id = current_setting('app.current_user_id')::uuid);
    
ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;
```

## Conclusion

The database schema for the AI Agentic Deals System is designed to support the system's key requirements of deal discovery, user personalization, token economics, and AI-powered analysis. The schema follows best practices for performance, security, and data integrity while maintaining flexibility for future growth.

## References

1. [PostgreSQL Documentation](https://www.postgresql.org/docs/)
2. [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/en/20/)
3. [Alembic Documentation](https://alembic.sqlalchemy.org/en/latest/)
4. [Database Schema Best Practices](../development/best_practices.md)
5. [Connection Management](./connection_management.md) 