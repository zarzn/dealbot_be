# Database Schema Documentation

## Overview
The database schema is designed to support the AI Agentic Deals System's core functionalities, including user management, goal tracking, deal monitoring, and token operations. The schema uses PostgreSQL with proper indexing, constraints, and relationships.

## Schema Diagram
[Include Entity Relationship Diagram here]

## Enum Types

### User Related
- `userstatus`: 'active', 'inactive', 'suspended', 'deleted'
- `notificationpriority`: 'critical', 'high', 'medium', 'low'
- `notificationstatus`: 'pending', 'sent', 'delivered', 'read', 'failed'
- `notificationtype`: 'system', 'deal', 'goal', 'price_alert', 'token', 'security', 'market'

### Market Related
- `marketcategory`: 'electronics', 'fashion', 'home', 'books', 'toys', 'sports', 'automotive', 'health', 'beauty', 'grocery', 'other'
- `markettype`: 'amazon', 'walmart', 'ebay', 'target', 'bestbuy'
- `marketstatus`: 'active', 'inactive', 'maintenance', 'rate_limited', 'error'

### Goal and Deal Related
- `goalstatus`: 'active', 'paused', 'completed', 'cancelled', 'failed', 'expired', 'error'
- `goalpriority`: 'high', 'medium', 'low'
- `dealstatus`: 'pending', 'active', 'expired', 'sold_out', 'invalid', 'deleted'
- `dealsource`: 'amazon', 'walmart', 'ebay', 'target', 'bestbuy', 'manual', 'api', 'scraper', 'user', 'agent'

### Token Related
- `tokentype`: 'access', 'refresh', 'reset'
- `tokenstatus`: 'active', 'expired', 'revoked'
- `tokenscope`: 'full', 'limited', 'read'
- `transactiontype`: 'deduction', 'reward', 'refund'
- `transactionstatus`: 'pending', 'completed', 'failed', 'cancelled'
- `balancechangetype`: 'deduction', 'reward', 'refund'

### Chat Related
- `messagerole`: 'user', 'assistant', 'system'

## Tables

### Users
```sql
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
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```
**Indexes:**
- `ix_users_email_status` on (email, status)
- `ix_users_wallet` on (sol_address)
- `ix_users_referral` on (referral_code)

**Constraints:**
- `ch_positive_balance`: Ensures token balance is non-negative
- `uq_user_email`: Unique email addresses
- `uq_user_wallet`: Unique wallet addresses
- `uq_user_referral`: Unique referral codes

### Auth Tokens
```sql
CREATE TABLE auth_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token TEXT NOT NULL,
    token_type tokentype NOT NULL,
    status tokenstatus NOT NULL DEFAULT 'active',
    scope tokenscope NOT NULL DEFAULT 'full',
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    meta_data JSONB NOT NULL DEFAULT '{}'
);
```
**Indexes:**
- `ix_auth_tokens_user` on (user_id)
- `ix_auth_tokens_token` on (token)
- `ix_auth_tokens_status` on (status)

### Goals
```sql
CREATE TABLE goals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    category marketcategory NOT NULL,
    constraints JSONB NOT NULL DEFAULT '{}',
    status goalstatus NOT NULL DEFAULT 'active',
    priority goalpriority NOT NULL DEFAULT 'medium',
    start_date TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    end_date TIMESTAMP WITH TIME ZONE,
    max_budget NUMERIC(10,2),
    min_discount_percent NUMERIC(5,2),
    target_price NUMERIC(10,2),
    notification_threshold NUMERIC(5,2),
    auto_buy_threshold NUMERIC(5,2),
    max_matches INTEGER,
    max_tokens NUMERIC(18,8),
    total_tokens_spent NUMERIC(18,8) NOT NULL DEFAULT 0,
    total_matches_found INTEGER NOT NULL DEFAULT 0,
    last_checked_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    meta_data JSONB NOT NULL DEFAULT '{}'
);
```
**Indexes:**
- `ix_goals_user_status` on (user_id, status)
- `ix_goals_category` on (category)
- `ix_goals_priority` on (priority)

### Markets
```sql
CREATE TABLE markets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    type markettype NOT NULL,
    status marketstatus NOT NULL DEFAULT 'active',
    base_url TEXT NOT NULL,
    api_endpoint TEXT,
    api_key TEXT,
    rate_limit INTEGER,
    rate_limit_window INTEGER,
    current_rate INTEGER NOT NULL DEFAULT 0,
    last_rate_reset TIMESTAMP WITH TIME ZONE,
    error_count INTEGER NOT NULL DEFAULT 0,
    last_error_at TIMESTAMP WITH TIME ZONE,
    last_error TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    meta_data JSONB NOT NULL DEFAULT '{}'
);
```
**Indexes:**
- `ix_markets_type_status` on (type, status)
- `ix_markets_name` on (name)

### Deals
```sql
CREATE TABLE deals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    goal_id UUID NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
    market_id UUID NOT NULL REFERENCES markets(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    url TEXT NOT NULL,
    image_url TEXT,
    current_price NUMERIC(10,2) NOT NULL,
    original_price NUMERIC(10,2),
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    discount_percent NUMERIC(5,2),
    category marketcategory NOT NULL,
    source dealsource NOT NULL,
    status dealstatus NOT NULL DEFAULT 'active',
    seller_name VARCHAR(255),
    seller_rating NUMERIC(3,2),
    availability_status VARCHAR(50),
    shipping_info JSONB,
    product_specs JSONB,
    found_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE,
    last_checked_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    meta_data JSONB NOT NULL DEFAULT '{}'
);
```
**Indexes:**
- `ix_deals_goal_status` on (goal_id, status)
- `ix_deals_market_status` on (market_id, status)
- `ix_deals_category` on (category)
- `ix_deals_source` on (source)
- `ix_deals_url` on (url)

### Price Tracking
```sql
CREATE TABLE price_tracking (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deal_id UUID NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
    price NUMERIC(10,2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    source dealsource NOT NULL,
    tracked_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    meta_data JSONB NOT NULL DEFAULT '{}'
);
```
**Indexes:**
- `ix_price_tracking_deal` on (deal_id)
- `ix_price_tracking_source` on (source)

### Chat Messages
```sql
CREATE TABLE chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    goal_id UUID REFERENCES goals(id) ON DELETE SET NULL,
    role messagerole NOT NULL,
    content TEXT NOT NULL,
    tokens_used INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    meta_data JSONB NOT NULL DEFAULT '{}'
);
```
**Indexes:**
- `ix_chat_messages_user` on (user_id)
- `ix_chat_messages_goal` on (goal_id)
- `ix_chat_messages_role` on (role)

### Notifications
```sql
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type notificationtype NOT NULL,
    priority notificationpriority NOT NULL DEFAULT 'medium',
    status notificationstatus NOT NULL DEFAULT 'pending',
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    goal_id UUID REFERENCES goals(id) ON DELETE SET NULL,
    deal_id UUID REFERENCES deals(id) ON DELETE SET NULL,
    action_url TEXT,
    channels JSONB NOT NULL DEFAULT '["in_app"]',
    sent_at TIMESTAMP WITH TIME ZONE,
    delivered_at TIMESTAMP WITH TIME ZONE,
    read_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    meta_data JSONB NOT NULL DEFAULT '{}'
);
```
**Indexes:**
- `ix_notifications_user_status` on (user_id, status)
- `ix_notifications_type` on (type)
- `ix_notifications_priority` on (priority)

### Token Transactions
```sql
CREATE TABLE token_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type transactiontype NOT NULL,
    amount NUMERIC(18,8) NOT NULL,
    status transactionstatus NOT NULL DEFAULT 'pending',
    description TEXT,
    goal_id UUID REFERENCES goals(id) ON DELETE SET NULL,
    tx_hash VARCHAR(66),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    meta_data JSONB NOT NULL DEFAULT '{}'
);
```
**Indexes:**
- `ix_token_transactions_user` on (user_id)
- `ix_token_transactions_type` on (type)
- `ix_token_transactions_status` on (status)
- `ix_token_transactions_hash` on (tx_hash)

### Token Balance History
```sql
CREATE TABLE token_balance_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    balance_before NUMERIC(18,8) NOT NULL,
    balance_after NUMERIC(18,8) NOT NULL,
    change_amount NUMERIC(18,8) NOT NULL,
    change_type balancechangetype NOT NULL,
    transaction_id UUID REFERENCES token_transactions(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    meta_data JSONB NOT NULL DEFAULT '{}'
);
```
**Indexes:**
- `ix_token_balance_history_user` on (user_id)
- `ix_token_balance_history_type` on (change_type)

### Model Metrics
```sql
CREATE TABLE model_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name VARCHAR(50) NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    accuracy NUMERIC(5,4) NOT NULL,
    precision NUMERIC(5,4) NOT NULL,
    recall NUMERIC(5,4) NOT NULL,
    f1_score NUMERIC(5,4) NOT NULL,
    training_duration INTEGER NOT NULL,
    training_samples INTEGER NOT NULL,
    validation_samples INTEGER NOT NULL,
    hyperparameters JSONB NOT NULL DEFAULT '{}',
    feature_importance JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    meta_data JSONB NOT NULL DEFAULT '{}'
);
```
**Indexes:**
- `ix_model_metrics_name_version` on (model_name, model_version)
- `ix_model_metrics_created` on (created_at)

### Token Pricing
```sql
CREATE TABLE token_pricing (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_type VARCHAR(50) NOT NULL,
    token_cost NUMERIC(18,8) NOT NULL,
    min_tokens INTEGER NOT NULL DEFAULT 1,
    max_tokens INTEGER,
    valid_from TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    valid_to TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    meta_data JSONB NOT NULL DEFAULT '{}'
);
```
**Indexes:**
- `ix_token_pricing_service` on (service_type)
- `ix_token_pricing_active` on (is_active)
- `ix_token_pricing_validity` on (valid_from, valid_to)

## Notes
- All tables inherit created_at/updated_at from Base model
- All UUID fields use gen_random_uuid() for generation
- All timestamp fields include timezone information
- JSONB used for flexible schema evolution
- Appropriate indexes on frequently queried fields
- Proper foreign key constraints with ON DELETE actions
- Check constraints for data integrity
- Enum fields implemented as VARCHAR with constraints

## Database Connection Standards
- Connection Pooling:
  - Min connections: 5
  - Max connections: 20
  - Overflow: 5
  - Pool recycle: 3600
- Transaction Management:
  - Max retry attempts: 3
  - Deadlock retry delay: 1s
  - Transaction timeout: 30s

## Performance Guidelines
- Maximum query time: 1 second
- Use efficient indexing
- Implement query monitoring
- Follow cache strategy
- Use connection pooling
- Optimize bulk operations 