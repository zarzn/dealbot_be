# Database Schema Documentation

## Overview

This document describes the database schema for the AI Agentic Deals System. The system uses PostgreSQL as its primary database, leveraging SQLAlchemy 2.0 style for object-relational mapping. The schema is designed to support all core system functionalities while maintaining data integrity, performance, and scalability.

## Schema Conventions

The database follows these conventions:

1. **Naming**:
   - Tables use snake_case, singular form (e.g., `user`, not `users`)
   - Primary keys are named `id`
   - Foreign keys follow the pattern `{table_name}_id`
   - Junction tables for many-to-many relationships follow the pattern `{table1}_{table2}`
   - Indexes follow the pattern `ix_{table}_{column(s)}`
   - Unique constraints follow the pattern `uq_{table}_{column(s)}`

2. **Data Types**:
   - UUIDs are used for primary keys
   - Text is used for variable-length strings (preferred over VARCHAR)
   - JSONB is used for semi-structured data
   - Enums are stored as lowercase string values
   - Timestamps include timezone information (timestamptz)

3. **Relationships**:
   - Foreign keys have appropriate ON DELETE actions
   - Many-to-many relationships use junction tables
   - Self-referential relationships are supported where needed

## Entity-Relationship Diagram

```
┌──────────────┐       ┌───────────────┐       ┌──────────────┐
│              │       │               │       │              │
│     user     │───────│  user_market  │───────│    market    │
│              │       │               │       │              │
└──────────────┘       └───────────────┘       └──────────────┘
       │                                               │
       │                                               │
       │                ┌───────────────┐              │
       │                │               │              │
       └────────────────│     deal      │──────────────┘
                        │               │
                        └───────────────┘
                               │
                 ┌─────────────┼─────────────┐
                 │             │             │
        ┌────────────────┐ ┌──────────┐ ┌──────────────┐
        │                │ │          │ │              │
        │  deal_comment  │ │deal_tag  │ │deal_reaction │
        │                │ │          │ │              │
        └────────────────┘ └──────────┘ └──────────────┘
                 │
                 │
        ┌────────────────┐       ┌──────────────┐       ┌───────────────┐
        │                │       │              │       │               │
        │    comment     │───────│ user_follow  │───────│  user_profile │
        │                │       │              │       │               │
        └────────────────┘       └──────────────┘       └───────────────┘
                                        │
                                        │
                                 ┌──────────────┐       ┌───────────────┐
                                 │              │       │               │
                                 │   token      │───────│token_transfer │
                                 │              │       │               │
                                 └──────────────┘       └───────────────┘
                                        │
                                        │
                                 ┌──────────────┐
                                 │              │
                                 │token_balance │
                                 │              │
                                 └──────────────┘
```

## Core Tables

### user

Stores user account information.

```sql
CREATE TABLE "user" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT true,
    is_superuser BOOLEAN NOT NULL DEFAULT false,
    preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT uq_user_email UNIQUE (email)
);

CREATE INDEX ix_user_email ON "user" (email);
CREATE INDEX ix_user_created_at ON "user" (created_at);
```

### user_profile

Stores extended user profile information.

```sql
CREATE TABLE user_profile (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES "user" (id) ON DELETE CASCADE,
    display_name TEXT,
    bio TEXT,
    avatar_url TEXT,
    location TEXT,
    website TEXT,
    social_links JSONB DEFAULT '{}'::jsonb,
    visibility TEXT NOT NULL DEFAULT 'public',
    reputation_score INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_user_profile_user_id UNIQUE (user_id)
);

CREATE INDEX ix_user_profile_user_id ON user_profile (user_id);
CREATE INDEX ix_user_profile_reputation_score ON user_profile (reputation_score);
```

### market

Stores information about different marketplaces.

```sql
CREATE TABLE market (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    logo_url TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    market_type TEXT NOT NULL,
    scraping_enabled BOOLEAN NOT NULL DEFAULT true,
    scraping_interval INTEGER NOT NULL DEFAULT 3600,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    credentials JSONB DEFAULT NULL,
    configuration JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT uq_market_name UNIQUE (name),
    CONSTRAINT uq_market_url UNIQUE (url)
);

CREATE INDEX ix_market_market_type ON market (market_type);
CREATE INDEX ix_market_status ON market (status);
```

### user_market

Junction table that associates users with markets they're interested in.

```sql
CREATE TABLE user_market (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES "user" (id) ON DELETE CASCADE,
    market_id UUID NOT NULL REFERENCES market (id) ON DELETE CASCADE,
    is_favorite BOOLEAN NOT NULL DEFAULT false,
    notification_preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_user_market_user_id_market_id UNIQUE (user_id, market_id)
);

CREATE INDEX ix_user_market_user_id ON user_market (user_id);
CREATE INDEX ix_user_market_market_id ON user_market (market_id);
```

### deal

Stores deal information.

```sql
CREATE TABLE deal (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    description TEXT,
    url TEXT NOT NULL,
    image_url TEXT,
    price DECIMAL(15, 2),
    original_price DECIMAL(15, 2),
    currency TEXT NOT NULL DEFAULT 'USD',
    discount_percentage DECIMAL(5, 2),
    market_id UUID NOT NULL REFERENCES market (id) ON DELETE CASCADE,
    external_id TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    deal_type TEXT NOT NULL,
    category TEXT,
    subcategory TEXT,
    tags JSONB DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    ai_analysis JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ,
    CONSTRAINT uq_deal_market_id_external_id UNIQUE (market_id, external_id)
);

CREATE INDEX ix_deal_market_id ON deal (market_id);
CREATE INDEX ix_deal_status ON deal (status);
CREATE INDEX ix_deal_deal_type ON deal (deal_type);
CREATE INDEX ix_deal_category ON deal (category);
CREATE INDEX ix_deal_created_at ON deal (created_at);
CREATE INDEX ix_deal_expires_at ON deal (expires_at);
CREATE INDEX ix_deal_price ON deal (price);
CREATE INDEX ix_deal_discount_percentage ON deal (discount_percentage);
```

### deal_tag

Stores tags associated with deals.

```sql
CREATE TABLE deal_tag (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deal_id UUID NOT NULL REFERENCES deal (id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_deal_tag_deal_id_tag UNIQUE (deal_id, tag)
);

CREATE INDEX ix_deal_tag_deal_id ON deal_tag (deal_id);
CREATE INDEX ix_deal_tag_tag ON deal_tag (tag);
```

### deal_reaction

Stores user reactions to deals.

```sql
CREATE TABLE deal_reaction (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deal_id UUID NOT NULL REFERENCES deal (id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES "user" (id) ON DELETE CASCADE,
    reaction_type TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_deal_reaction_deal_id_user_id UNIQUE (deal_id, user_id)
);

CREATE INDEX ix_deal_reaction_deal_id ON deal_reaction (deal_id);
CREATE INDEX ix_deal_reaction_user_id ON deal_reaction (user_id);
CREATE INDEX ix_deal_reaction_reaction_type ON deal_reaction (reaction_type);
```

### comment

Stores comments that can be associated with deals or other content.

```sql
CREATE TABLE comment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES "user" (id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    parent_comment_id UUID REFERENCES comment (id) ON DELETE CASCADE
);

CREATE INDEX ix_comment_user_id ON comment (user_id);
CREATE INDEX ix_comment_parent_comment_id ON comment (parent_comment_id);
CREATE INDEX ix_comment_created_at ON comment (created_at);
```

### deal_comment

Connects comments to deals.

```sql
CREATE TABLE deal_comment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deal_id UUID NOT NULL REFERENCES deal (id) ON DELETE CASCADE,
    comment_id UUID NOT NULL REFERENCES comment (id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_deal_comment_deal_id_comment_id UNIQUE (deal_id, comment_id)
);

CREATE INDEX ix_deal_comment_deal_id ON deal_comment (deal_id);
CREATE INDEX ix_deal_comment_comment_id ON deal_comment (comment_id);
```

### user_follow

Stores user follow relationships.

```sql
CREATE TABLE user_follow (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    follower_id UUID NOT NULL REFERENCES "user" (id) ON DELETE CASCADE,
    followed_id UUID NOT NULL REFERENCES "user" (id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_user_follow_follower_id_followed_id UNIQUE (follower_id, followed_id),
    CONSTRAINT chk_user_follow_not_self CHECK (follower_id != followed_id)
);

CREATE INDEX ix_user_follow_follower_id ON user_follow (follower_id);
CREATE INDEX ix_user_follow_followed_id ON user_follow (followed_id);
```

### token

Stores information about the system's token.

```sql
CREATE TABLE token (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    decimals INTEGER NOT NULL DEFAULT 18,
    total_supply DECIMAL(38, 18) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT uq_token_symbol UNIQUE (symbol)
);
```

### token_balance

Stores user token balances.

```sql
CREATE TABLE token_balance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES "user" (id) ON DELETE CASCADE,
    token_id UUID NOT NULL REFERENCES token (id) ON DELETE CASCADE,
    balance DECIMAL(38, 18) NOT NULL DEFAULT 0,
    locked_balance DECIMAL(38, 18) NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_token_balance_user_id_token_id UNIQUE (user_id, token_id),
    CONSTRAINT chk_token_balance_non_negative CHECK (balance >= 0 AND locked_balance >= 0)
);

CREATE INDEX ix_token_balance_user_id ON token_balance (user_id);
CREATE INDEX ix_token_balance_token_id ON token_balance (token_id);
```

### token_transfer

Stores token transfer history.

```sql
CREATE TABLE token_transfer (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_id UUID NOT NULL REFERENCES token (id) ON DELETE CASCADE,
    from_user_id UUID REFERENCES "user" (id) ON DELETE SET NULL,
    to_user_id UUID REFERENCES "user" (id) ON DELETE SET NULL,
    amount DECIMAL(38, 18) NOT NULL,
    transfer_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'completed',
    reference_id UUID,
    reference_type TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_token_transfer_amount_positive CHECK (amount > 0)
);

CREATE INDEX ix_token_transfer_token_id ON token_transfer (token_id);
CREATE INDEX ix_token_transfer_from_user_id ON token_transfer (from_user_id);
CREATE INDEX ix_token_transfer_to_user_id ON token_transfer (to_user_id);
CREATE INDEX ix_token_transfer_transfer_type ON token_transfer (transfer_type);
CREATE INDEX ix_token_transfer_reference_id ON token_transfer (reference_id);
CREATE INDEX ix_token_transfer_created_at ON token_transfer (created_at);
```

## Additional Social and Sharing Tables

### shared_deal

Stores information about shared deals.

```sql
CREATE TABLE shared_deal (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deal_id UUID NOT NULL REFERENCES deal (id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES "user" (id) ON DELETE CASCADE,
    share_token TEXT NOT NULL,
    title TEXT,
    custom_message TEXT,
    privacy_level TEXT NOT NULL DEFAULT 'public',
    expiration_date TIMESTAMPTZ,
    view_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_shared_deal_share_token UNIQUE (share_token)
);

CREATE INDEX ix_shared_deal_deal_id ON shared_deal (deal_id);
CREATE INDEX ix_shared_deal_user_id ON shared_deal (user_id);
CREATE INDEX ix_shared_deal_created_at ON shared_deal (created_at);
```

### deal_collection

Stores collections of deals created by users.

```sql
CREATE TABLE deal_collection (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES "user" (id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    is_public BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_deal_collection_user_id_name UNIQUE (user_id, name)
);

CREATE INDEX ix_deal_collection_user_id ON deal_collection (user_id);
```

### deal_collection_item

Stores deals that belong to collections.

```sql
CREATE TABLE deal_collection_item (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_id UUID NOT NULL REFERENCES deal_collection (id) ON DELETE CASCADE,
    deal_id UUID NOT NULL REFERENCES deal (id) ON DELETE CASCADE,
    added_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    notes TEXT,
    CONSTRAINT uq_deal_collection_item_collection_id_deal_id UNIQUE (collection_id, deal_id)
);

CREATE INDEX ix_deal_collection_item_collection_id ON deal_collection_item (collection_id);
CREATE INDEX ix_deal_collection_item_deal_id ON deal_collection_item (deal_id);
```

### deal_comparison

Stores deal comparisons created by users.

```sql
CREATE TABLE deal_comparison (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES "user" (id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    is_public BOOLEAN NOT NULL DEFAULT false,
    share_token TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_deal_comparison_user_id ON deal_comparison (user_id);
CREATE INDEX ix_deal_comparison_share_token ON deal_comparison (share_token);
```

### deal_comparison_item

Stores deals included in comparisons.

```sql
CREATE TABLE deal_comparison_item (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    comparison_id UUID NOT NULL REFERENCES deal_comparison (id) ON DELETE CASCADE,
    deal_id UUID NOT NULL REFERENCES deal (id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_deal_comparison_item_comparison_id_deal_id UNIQUE (comparison_id, deal_id)
);

CREATE INDEX ix_deal_comparison_item_comparison_id ON deal_comparison_item (comparison_id);
CREATE INDEX ix_deal_comparison_item_deal_id ON deal_comparison_item (deal_id);
```

### user_activity

Stores user activity events for the activity feed.

```sql
CREATE TABLE user_activity (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES "user" (id) ON DELETE CASCADE,
    activity_type TEXT NOT NULL,
    entity_id UUID NOT NULL,
    entity_type TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_public BOOLEAN NOT NULL DEFAULT true
);

CREATE INDEX ix_user_activity_user_id ON user_activity (user_id);
CREATE INDEX ix_user_activity_activity_type ON user_activity (activity_type);
CREATE INDEX ix_user_activity_entity_id ON user_activity (entity_id);
CREATE INDEX ix_user_activity_created_at ON user_activity (created_at);
```

### community

Stores community information.

```sql
CREATE TABLE community (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    description TEXT,
    logo_url TEXT,
    creator_id UUID NOT NULL REFERENCES "user" (id) ON DELETE SET NULL,
    is_public BOOLEAN NOT NULL DEFAULT true,
    member_count INTEGER NOT NULL DEFAULT 0,
    rules TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_community_name UNIQUE (name)
);

CREATE INDEX ix_community_creator_id ON community (creator_id);
CREATE INDEX ix_community_created_at ON community (created_at);
```

### community_member

Stores community membership information.

```sql
CREATE TABLE community_member (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    community_id UUID NOT NULL REFERENCES community (id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES "user" (id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'member',
    joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_community_member_community_id_user_id UNIQUE (community_id, user_id)
);

CREATE INDEX ix_community_member_community_id ON community_member (community_id);
CREATE INDEX ix_community_member_user_id ON community_member (user_id);
CREATE INDEX ix_community_member_role ON community_member (role);
```

## Views

### active_deals

A view that shows only active deals.

```sql
CREATE VIEW active_deals AS
SELECT d.*
FROM deal d
WHERE d.status = 'active'
  AND (d.expires_at IS NULL OR d.expires_at > now());
```

### user_deal_interactions

A view that aggregates user interactions with deals.

```sql
CREATE VIEW user_deal_interactions AS
SELECT 
    d.id AS deal_id,
    d.title AS deal_title,
    u.id AS user_id,
    u.full_name AS user_name,
    COUNT(dr.id) AS reaction_count,
    COUNT(dc.id) AS comment_count,
    MAX(GREATEST(dr.created_at, dc.created_at)) AS last_interaction_at
FROM 
    deal d
    JOIN "user" u ON TRUE
    LEFT JOIN deal_reaction dr ON dr.deal_id = d.id AND dr.user_id = u.id
    LEFT JOIN deal_comment dc ON dc.deal_id = d.id
    LEFT JOIN comment c ON c.id = dc.comment_id AND c.user_id = u.id
GROUP BY
    d.id, d.title, u.id, u.full_name;
```

### popular_deals

A view that shows deals ranked by popularity.

```sql
CREATE VIEW popular_deals AS
SELECT 
    d.*,
    COUNT(DISTINCT dr.user_id) AS reaction_count,
    COUNT(DISTINCT dc.comment_id) AS comment_count,
    (COUNT(DISTINCT dr.user_id) * 2 + COUNT(DISTINCT dc.comment_id) * 3) AS popularity_score
FROM 
    deal d
    LEFT JOIN deal_reaction dr ON dr.deal_id = d.id
    LEFT JOIN deal_comment dc ON dc.deal_id = d.id
WHERE 
    d.status = 'active'
    AND (d.expires_at IS NULL OR d.expires_at > now())
GROUP BY
    d.id
ORDER BY
    popularity_score DESC;
```

## Database Migrations

The database schema is version-controlled through migration files located in `backend/alembic/versions/`. Each migration file represents a set of schema changes and follows a standard naming convention:

```
YYYYMMDD_NNNNNN_description.py
```

Where:
- `YYYYMMDD` is the date the migration was created
- `NNNNNN` is a sequential number
- `description` is a brief description of what the migration does

The initial schema migration is defined in `20240219_000001_initial_schema.py`, and subsequent migrations build upon this foundation.

## Schema Evolution Guidelines

When evolving the schema, follow these guidelines:

1. **Backward Compatibility**: Ensure changes do not break existing functionality
2. **Use Migrations**: Always create a migration file for schema changes
3. **Test Migrations**: Test both up and down migrations before committing
4. **Comment Complex Changes**: Add comments to explain complex migration logic
5. **Data Migration**: Handle data migration alongside schema changes where necessary
6. **Foreign Keys**: Always include appropriate foreign key constraints
7. **Indexes**: Add indexes for frequently queried columns

## Performance Considerations

The schema is designed with the following performance considerations:

1. **Indexing Strategy**: Indexes are added to columns used in WHERE clauses, JOIN conditions, and ORDER BY statements
2. **Denormalization**: Strategic denormalization is used for frequently accessed read patterns
3. **JSON/JSONB**: JSONB is used for semi-structured data with indexes on commonly queried JSON paths
4. **Partitioning**: Large tables (like deal_reaction, token_transfer) may be partitioned for better performance
5. **Connection Pooling**: The application uses connection pooling to efficiently manage database connections

## Security Considerations

1. **No Plain Passwords**: Password hash is stored, never the plain password
2. **Secure Defaults**: Default values ensure secure operation out of the box
3. **Row-Level Security**: Applied where necessary for multi-tenant data
4. **Audit Trails**: Created_at and updated_at timestamps are present on all tables
5. **Data Sensitivity**: No PII in logs or error messages

## Schema Validation

The schema can be validated using the setup_db.py script:

```
python backend/scripts/dev/database/setup_db.py --validate
```

This script verifies that the database schema matches the SQLAlchemy models defined in the codebase. 