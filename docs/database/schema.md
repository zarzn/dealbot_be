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

## Database Engine

The system uses PostgreSQL as the primary database engine. All models are designed to work optimally with PostgreSQL's features.

## Naming Conventions

- Table names: snake_case, plural (e.g., `users`, `deal_scores`)
- Column names: snake_case (e.g., `created_at`, `user_id`)
- Primary keys: `id` (UUID type)
- Foreign keys: `entity_name_id` (e.g., `user_id`, `deal_id`)
- Indexes: `ix_table_column` (e.g., `ix_users_email`)
- Unique constraints: `uq_table_column` (e.g., `uq_users_email`)

## Enum Handling

Enums are stored in the database as lowercase strings for maximum compatibility. The system follows these conventions for enum handling:

1. Enum definitions are kept in `core.models.enums`
2. When defining SQLAlchemy enum columns, values are converted to lowercase:
   ```python
   status = mapped_column(SQLAlchemyEnum(MarketStatus, values_callable=lambda x: [e.value.lower() for e in x]))
   ```
3. When retrieving enum values from the database, they are converted back to enum objects
4. In API responses, enum values (strings) are used instead of enum objects
5. When creating factory defaults, `.value` is used for enum fields
6. In test files, always use `.value` when working with enums (e.g., `MarketType.TEST.value`)

## Data Models

### User

**Table**: `users`

| Column | Type | Constraints | Description |
| --- | --- | --- | --- |
| `id` | UUID | PK, NOT NULL | Unique identifier |
| `email` | String | UNIQUE, NOT NULL | User email address |
| `name` | String | NOT NULL | User full name |
| `password_hash` | String | NOT NULL | Hashed password |
| `status` | String (Enum) | NOT NULL | User status (active, inactive, suspended) |
| `role` | String (Enum) | NOT NULL | User role (admin, user, agent) |
| `created_at` | Timestamp | NOT NULL | Creation timestamp |
| `updated_at` | Timestamp | NOT NULL | Last update timestamp |

**Indexes**:
- `ix_users_email` - For fast lookup by email
- `ix_users_status` - For filtering active users

**Relationships**:
- `deals` (One-to-Many) -> `Deal`
- `tokens` (One-to-Many) -> `TokenBalance`
- `settings` (One-to-One) -> `UserSettings`

### Deal

**Table**: `deals`

| Column | Type | Constraints | Description |
| --- | --- | --- | --- |
| `id` | UUID | PK, NOT NULL | Unique identifier |
| `user_id` | UUID | FK, NOT NULL | Owner user ID |
| `title` | String | NOT NULL | Deal title |
| `description` | Text | | Deal description |
| `status` | String (Enum) | NOT NULL | Deal status (draft, active, completed, cancelled) |
| `market_type` | String (Enum) | NOT NULL | Market type (stock, crypto, forex, commodity) |
| `price` | Numeric | | Current price |
| `target_price` | Numeric | | Target price |
| `quantity` | Numeric | | Quantity |
| `created_at` | Timestamp | NOT NULL | Creation timestamp |
| `updated_at` | Timestamp | NOT NULL | Last update timestamp |
| `metadata` | JSONB | | Additional metadata |

**Indexes**:
- `ix_deals_user_id` - For fast lookup of user's deals
- `ix_deals_status` - For filtering by status
- `ix_deals_market_type` - For filtering by market type
- `ix_deals_created_at` - For sorting by creation date

**Relationships**:
- `user` (Many-to-One) -> `User`
- `scores` (One-to-Many) -> `DealScore`
- `activities` (One-to-Many) -> `DealActivity`
- `goals` (One-to-Many) -> `Goal`

### DealScore

**Table**: `deal_scores`

| Column | Type | Constraints | Description |
| --- | --- | --- | --- |
| `id` | UUID | PK, NOT NULL | Unique identifier |
| `deal_id` | UUID | FK, NOT NULL | Referenced deal ID |
| `score_type` | String (Enum) | NOT NULL | Score type (risk, profit_potential, market_sentiment) |
| `value` | Numeric | NOT NULL | Score value (0-100) |
| `confidence` | Numeric | NOT NULL | Confidence level (0-100) |
| `created_at` | Timestamp | NOT NULL | Creation timestamp |
| `updated_at` | Timestamp | NOT NULL | Last update timestamp |
| `metadata` | JSONB | | Additional metadata |

**Indexes**:
- `ix_deal_scores_deal_id` - For fast lookup of deal's scores
- `ix_deal_scores_score_type` - For filtering by score type
- `ix_deal_scores_created_at` - For sorting by creation date

**Relationships**:
- `deal` (Many-to-One) -> `Deal`

### TokenBalance

**Table**: `token_balances`

| Column | Type | Constraints | Description |
| --- | --- | --- | --- |
| `id` | UUID | PK, NOT NULL | Unique identifier |
| `user_id` | UUID | FK, NOT NULL | User ID |
| `token_type` | String (Enum) | NOT NULL | Token type (usage, api) |
| `balance` | Integer | NOT NULL | Current token balance |
| `created_at` | Timestamp | NOT NULL | Creation timestamp |
| `updated_at` | Timestamp | NOT NULL | Last update timestamp |

**Indexes**:
- `ix_token_balances_user_id` - For fast lookup of user's token balances
- `ix_token_balances_token_type` - For filtering by token type

**Relationships**:
- `user` (Many-to-One) -> `User`
- `transactions` (One-to-Many) -> `TokenTransaction`

### TokenTransaction

**Table**: `token_transactions`

| Column | Type | Constraints | Description |
| --- | --- | --- | --- |
| `id` | UUID | PK, NOT NULL | Unique identifier |
| `balance_id` | UUID | FK, NOT NULL | Token balance ID |
| `amount` | Integer | NOT NULL | Transaction amount |
| `transaction_type` | String (Enum) | NOT NULL | Transaction type (purchase, usage, refund, bonus) |
| `reference_id` | UUID | | Reference to related entity (e.g., deal ID) |
| `reference_type` | String | | Type of related entity (e.g., "deal") |
| `created_at` | Timestamp | NOT NULL | Creation timestamp |
| `metadata` | JSONB | | Additional metadata |

**Indexes**:
- `ix_token_transactions_balance_id` - For fast lookup of balance's transactions
- `ix_token_transactions_transaction_type` - For filtering by transaction type
- `ix_token_transactions_created_at` - For sorting by creation date
- `ix_token_transactions_reference_id` - For filtering by reference ID

**Relationships**:
- `balance` (Many-to-One) -> `TokenBalance`

### Goal

**Table**: `goals`

| Column | Type | Constraints | Description |
| --- | --- | --- | --- |
| `id` | UUID | PK, NOT NULL | Unique identifier |
| `deal_id` | UUID | FK, NOT NULL | Related deal ID |
| `title` | String | NOT NULL | Goal title |
| `description` | Text | | Goal description |
| `status` | String (Enum) | NOT NULL | Goal status (pending, in_progress, completed, failed) |
| `priority` | Integer | NOT NULL | Priority (1-5, 1 highest) |
| `due_date` | Timestamp | | Due date |
| `created_at` | Timestamp | NOT NULL | Creation timestamp |
| `updated_at` | Timestamp | NOT NULL | Last update timestamp |
| `metadata` | JSONB | | Additional metadata |

**Indexes**:
- `ix_goals_deal_id` - For fast lookup of deal's goals
- `ix_goals_status` - For filtering by status
- `ix_goals_priority` - For sorting by priority
- `ix_goals_due_date` - For sorting by due date

**Relationships**:
- `deal` (Many-to-One) -> `Deal`
- `tasks` (One-to-Many) -> `Task`

### Task

**Table**: `tasks`

| Column | Type | Constraints | Description |
| --- | --- | --- | --- |
| `id` | UUID | PK, NOT NULL | Unique identifier |
| `goal_id` | UUID | FK, NOT NULL | Related goal ID |
| `agent_id` | UUID | FK | Assigned agent ID |
| `title` | String | NOT NULL | Task title |
| `description` | Text | | Task description |
| `status` | String (Enum) | NOT NULL | Task status (pending, in_progress, completed, failed) |
| `priority` | Integer | NOT NULL | Priority (1-5, 1 highest) |
| `due_date` | Timestamp | | Due date |
| `created_at` | Timestamp | NOT NULL | Creation timestamp |
| `updated_at` | Timestamp | NOT NULL | Last update timestamp |
| `metadata` | JSONB | | Additional metadata |

**Indexes**:
- `ix_tasks_goal_id` - For fast lookup of goal's tasks
- `ix_tasks_agent_id` - For fast lookup of agent's tasks
- `ix_tasks_status` - For filtering by status
- `ix_tasks_priority` - For sorting by priority
- `ix_tasks_due_date` - For sorting by due date

**Relationships**:
- `goal` (Many-to-One) -> `Goal`
- `agent` (Many-to-One) -> `Agent`
- `activities` (One-to-Many) -> `TaskActivity`

### Agent

**Table**: `agents`

| Column | Type | Constraints | Description |
| --- | --- | --- | --- |
| `id` | UUID | PK, NOT NULL | Unique identifier |
| `name` | String | NOT NULL | Agent name |
| `type` | String (Enum) | NOT NULL | Agent type (market_analyst, research, negotiator, executor) |
| `status` | String (Enum) | NOT NULL | Agent status (active, inactive, busy) |
| `capabilities` | ARRAY[String] | NOT NULL | Array of agent capabilities |
| `created_at` | Timestamp | NOT NULL | Creation timestamp |
| `updated_at` | Timestamp | NOT NULL | Last update timestamp |
| `config` | JSONB | | Agent configuration |

**Indexes**:
- `ix_agents_type` - For filtering by agent type
- `ix_agents_status` - For filtering by status

**Relationships**:
- `tasks` (One-to-Many) -> `Task`

### DealActivity

**Table**: `deal_activities`

| Column | Type | Constraints | Description |
| --- | --- | --- | --- |
| `id` | UUID | PK, NOT NULL | Unique identifier |
| `deal_id` | UUID | FK, NOT NULL | Related deal ID |
| `user_id` | UUID | FK | User ID who performed the activity |
| `agent_id` | UUID | FK | Agent ID who performed the activity |
| `activity_type` | String (Enum) | NOT NULL | Activity type (created, updated, analyzed, etc.) |
| `description` | Text | | Activity description |
| `created_at` | Timestamp | NOT NULL | Creation timestamp |
| `metadata` | JSONB | | Additional metadata |

**Indexes**:
- `ix_deal_activities_deal_id` - For fast lookup of deal's activities
- `ix_deal_activities_user_id` - For filtering by user
- `ix_deal_activities_agent_id` - For filtering by agent
- `ix_deal_activities_activity_type` - For filtering by activity type
- `ix_deal_activities_created_at` - For sorting by creation date

**Relationships**:
- `deal` (Many-to-One) -> `Deal`
- `user` (Many-to-One) -> `User`
- `agent` (Many-to-One) -> `Agent`

### TaskActivity

**Table**: `task_activities`

| Column | Type | Constraints | Description |
| --- | --- | --- | --- |
| `id` | UUID | PK, NOT NULL | Unique identifier |
| `task_id` | UUID | FK, NOT NULL | Related task ID |
| `agent_id` | UUID | FK | Agent ID who performed the activity |
| `activity_type` | String (Enum) | NOT NULL | Activity type (started, progress, completed, etc.) |
| `description` | Text | | Activity description |
| `created_at` | Timestamp | NOT NULL | Creation timestamp |
| `metadata` | JSONB | | Additional metadata |

**Indexes**:
- `ix_task_activities_task_id` - For fast lookup of task's activities
- `ix_task_activities_agent_id` - For filtering by agent
- `ix_task_activities_activity_type` - For filtering by activity type
- `ix_task_activities_created_at` - For sorting by creation date

**Relationships**:
- `task` (Many-to-One) -> `Task`
- `agent` (Many-to-One) -> `Agent`

### UserSettings

**Table**: `user_settings`

| Column | Type | Constraints | Description |
| --- | --- | --- | --- |
| `id` | UUID | PK, NOT NULL | Unique identifier |
| `user_id` | UUID | FK, UNIQUE, NOT NULL | User ID |
| `notification_preferences` | JSONB | NOT NULL | Notification preferences |
| `ui_preferences` | JSONB | NOT NULL | UI preferences |
| `agent_preferences` | JSONB | NOT NULL | Agent behavior preferences |
| `created_at` | Timestamp | NOT NULL | Creation timestamp |
| `updated_at` | Timestamp | NOT NULL | Last update timestamp |

**Indexes**:
- `ix_user_settings_user_id` - For fast lookup of user's settings

**Relationships**:
- `user` (One-to-One) -> `User`

### MarketData

**Table**: `market_data`

| Column | Type | Constraints | Description |
| --- | --- | --- | --- |
| `id` | UUID | PK, NOT NULL | Unique identifier |
| `symbol` | String | NOT NULL | Market symbol |
| `market_type` | String (Enum) | NOT NULL | Market type (stock, crypto, forex, commodity) |
| `price` | Numeric | NOT NULL | Current price |
| `high_24h` | Numeric | | 24-hour high price |
| `low_24h` | Numeric | | 24-hour low price |
| `volume_24h` | Numeric | | 24-hour volume |
| `change_24h` | Numeric | | 24-hour price change |
| `change_percent_24h` | Numeric | | 24-hour price change percentage |
| `last_updated` | Timestamp | NOT NULL | Last update timestamp |
| `source` | String | NOT NULL | Data source |
| `metadata` | JSONB | | Additional metadata |

**Indexes**:
- `ix_market_data_symbol` - For fast lookup by symbol
- `ix_market_data_market_type` - For filtering by market type
- `ix_market_data_last_updated` - For sorting by update time
- `uq_market_data_symbol_source` - Unique constraint for symbol+source combination

## Database Migrations

Database migrations are managed using Alembic. The migration files are located in `backend/migrations/versions/`.

### Initial Migration

The initial migration file (`20240219_000001_initial_schema.py`) creates all the tables defined above with their relationships and constraints.

### Creating New Migrations

When making schema changes, create a new migration:

```bash
# From the backend directory
alembic revision --autogenerate -m "description_of_changes"
```

### Applying Migrations

To apply migrations:

```bash
# From the backend directory
alembic upgrade head
```

## Performance Considerations

The database schema is optimized for performance with the following considerations:

1. **Proper Indexing**:
   - Foreign keys are indexed for efficient joins
   - Frequently filtered columns have indexes
   - Columns used for sorting have indexes

2. **Denormalization**:
   - JSONB fields are used for flexible, schema-less data
   - Metadata fields allow for extensibility without schema changes

3. **Partitioning Strategy**:
   - Large tables like `market_data` can be partitioned by date
   - Historical data can be archived to maintain performance

4. **Query Optimization**:
   - Complex queries are optimized with joins and indexes
   - JSONB queries use GIN indexes for performance

5. **Connection Pooling**:
   - Production environment uses connection pooling
   - Pool size is configured based on server resources

## Database Administration

### Maintenance Tasks

1. **Regular Vacuum**:
   - Run vacuum analyze regularly to update statistics
   - Consider automated vacuum based on table growth

2. **Index Maintenance**:
   - Monitor index usage and bloat
   - Reindex when necessary

3. **Performance Monitoring**:
   - Monitor slow queries
   - Adjust indexes based on query patterns

4. **Backup Strategy**:
   - Regular database backups
   - Point-in-time recovery capability

### Connection Settings

Production database uses the following connection settings:

```python
# SQLAlchemy engine configuration for production
engine = create_async_engine(
    str(settings.DATABASE_URL),
    echo=False,
    future=True,
    pool_size=20,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=300,
    pool_pre_ping=True,
    connect_args={
        "statement_timeout": 30000,  # 30 seconds
        "options": "-c timezone=UTC"
    }
)
```

## Enum Values Reference

Below is a reference of all enum values used in the database:

### UserStatus
- `active` - Active user
- `inactive` - Inactive user
- `suspended` - Suspended user

### UserRole
- `admin` - Administrator
- `user` - Regular user
- `agent` - Agent user

### DealStatus
- `draft` - Draft deal
- `active` - Active deal
- `completed` - Completed deal
- `cancelled` - Cancelled deal

### MarketType
- `stock` - Stock market
- `crypto` - Cryptocurrency market
- `forex` - Foreign exchange market
- `commodity` - Commodity market

### ScoreType
- `risk` - Risk assessment
- `profit_potential` - Profit potential assessment
- `market_sentiment` - Market sentiment assessment

### TokenType
- `usage` - Usage tokens
- `api` - API tokens

### TransactionType
- `purchase` - Token purchase
- `usage` - Token usage
- `refund` - Token refund
- `bonus` - Bonus tokens

### GoalStatus
- `pending` - Pending goal
- `in_progress` - In-progress goal
- `completed` - Completed goal
- `failed` - Failed goal

### TaskStatus
- `pending` - Pending task
- `in_progress` - In-progress task
- `completed` - Completed task
- `failed` - Failed task

### AgentType
- `market_analyst` - Market analyst agent
- `research` - Research agent
- `negotiator` - Negotiator agent
- `executor` - Executor agent

### AgentStatus
- `active` - Active agent
- `inactive` - Inactive agent
- `busy` - Busy agent

### ActivityType (Deal)
- `created` - Deal created
- `updated` - Deal updated
- `analyzed` - Deal analyzed
- `goal_added` - Goal added
- `goal_completed` - Goal completed
- `completed` - Deal completed
- `cancelled` - Deal cancelled

### ActivityType (Task)
- `created` - Task created
- `started` - Task started
- `progress` - Task in progress
- `blocked` - Task blocked
- `completed` - Task completed
- `failed` - Task failed

## Data Migration

For major data migrations, use Alembic's `data_upgrades` feature in migration scripts. Example:

```python
def data_upgrades():
    """Add data migration logic here"""
    op.execute(
        "UPDATE users SET role = 'user' WHERE role IS NULL"
    )

def data_downgrades():
    """Add data migration rollback logic here"""
    pass
``` 