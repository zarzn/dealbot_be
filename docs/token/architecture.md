# Token System Architecture

## Overview

The token system provides a virtual currency mechanism for the AI Agentic Deals platform, allowing users to pay for AI-powered features like deal analysis, personalized recommendations, and premium content. This document outlines the token system architecture, components, and implementation details.

## Architecture Principles

1. **Secure**: Prevents token manipulation, theft, or unauthorized creation
2. **Scalable**: Handles high volume of token transactions with minimal latency
3. **Reliable**: Ensures token operations are atomic and consistent
4. **Transparent**: Provides clear visibility into token balances and transactions
5. **Extensible**: Supports future token features and integrations

## System Components

### Core Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│                 │    │                 │    │                 │
│  Token Service  │◄───┤  Token Manager  │◄───┤  Token Storage  │
│                 │    │                 │    │                 │
└────────┬────────┘    └────────┬────────┘    └─────────────────┘
         │                      │
         │                      │
┌────────▼────────┐    ┌────────▼────────┐    ┌─────────────────┐
│                 │    │                 │    │                 │
│  Token Gateway  │◄───┤ Token Validator │◄───┤ Token Analytics │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Component Descriptions

1. **Token Service**: Primary interface for token operations
   - Exposes REST API endpoints for token management
   - Handles token allocation, deduction, and transfer
   - Implements business rules for token usage

2. **Token Manager**: Core business logic for tokens
   - Enforces token rules and policies
   - Manages token lifecycle
   - Handles token balance updates

3. **Token Storage**: Persistence layer for token data
   - Stores token balances in PostgreSQL database
   - Caches frequent token operations in Redis
   - Maintains transaction history

4. **Token Gateway**: External interface for token system
   - Connects with payment processors for token purchases
   - Handles token redemption codes
   - Provides integration points with external systems

5. **Token Validator**: Security component for token operations
   - Validates token transaction requests
   - Prevents unauthorized token operations
   - Implements rate limiting for token requests

6. **Token Analytics**: Monitoring and reporting
   - Tracks token usage patterns
   - Generates token usage reports
   - Provides insights for token economy management

## Database Schema

```sql
-- Token balances for users
CREATE TABLE user_token_balances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    balance INTEGER NOT NULL DEFAULT 0,
    lifetime_earned INTEGER NOT NULL DEFAULT 0,
    lifetime_spent INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT positive_balance CHECK (balance >= 0)
);

-- Token transaction history
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

-- Token packages for purchase
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

-- Token redemption codes
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
```

## Token Transaction Types

| Type | Description | Flow |
|------|-------------|------|
| `PURCHASE` | Tokens purchased with money | External → User Balance |
| `AI_USAGE` | Tokens spent on AI features | User Balance → System |
| `SIGNUP_BONUS` | Initial tokens for new users | System → User Balance |
| `REFERRAL_BONUS` | Tokens earned from referrals | System → User Balance |
| `ADMIN_ADJUSTMENT` | Manual adjustment by admin | Admin → User Balance |
| `REDEMPTION_CODE` | Tokens from redemption code | System → User Balance |
| `REFUND` | Refunded tokens | System → User Balance |
| `EXPIRATION` | Expired tokens (if applicable) | User Balance → System |

## Implementation Details

### Token Service API

```python
# core/services/token_service.py
from typing import Optional, Dict, Any
from uuid import UUID
import asyncio
from fastapi import HTTPException, status

from core.models.token import UserTokenBalance, TokenTransaction
from core.models.enums import TokenTransactionType
from core.utils.logger import logger

class TokenService:
    """Service for managing user tokens and token transactions."""
    
    async def get_user_balance(self, user_id: UUID) -> int:
        """Get token balance for a user."""
        balance = await UserTokenBalance.get_or_create(user_id)
        return balance.balance
    
    async def add_tokens(
        self, 
        user_id: UUID, 
        amount: int, 
        transaction_type: TokenTransactionType,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        reference_id: Optional[UUID] = None
    ) -> int:
        """Add tokens to a user's balance."""
        if amount <= 0:
            raise ValueError("Token amount must be positive")
        
        # Use a database transaction to ensure atomicity
        async with db.transaction():
            # Get or create user balance
            balance = await UserTokenBalance.get_or_create(user_id)
            
            # Update balance
            balance.balance += amount
            balance.lifetime_earned += amount
            await balance.save()
            
            # Record transaction
            await TokenTransaction.create(
                user_id=user_id,
                transaction_type=transaction_type.value.lower(),
                amount=amount,
                balance_after=balance.balance,
                description=description,
                metadata=metadata,
                reference_id=reference_id
            )
            
            logger.info(f"Added {amount} tokens to user {user_id}, new balance: {balance.balance}")
            return balance.balance
    
    async def deduct_tokens(
        self, 
        user_id: UUID, 
        amount: int, 
        transaction_type: TokenTransactionType,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        reference_id: Optional[UUID] = None
    ) -> int:
        """Deduct tokens from a user's balance."""
        if amount <= 0:
            raise ValueError("Token amount must be positive")
            
        # Use a database transaction to ensure atomicity
        async with db.transaction():
            # Get user balance
            balance = await UserTokenBalance.get_or_create(user_id)
            
            # Ensure sufficient balance
            if balance.balance < amount:
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail=f"Insufficient token balance. Required: {amount}, Available: {balance.balance}"
                )
            
            # Update balance
            balance.balance -= amount
            balance.lifetime_spent += amount
            await balance.save()
            
            # Record transaction
            await TokenTransaction.create(
                user_id=user_id,
                transaction_type=transaction_type.value.lower(),
                amount=-amount,  # Negative for deductions
                balance_after=balance.balance,
                description=description,
                metadata=metadata,
                reference_id=reference_id
            )
            
            logger.info(f"Deducted {amount} tokens from user {user_id}, new balance: {balance.balance}")
            return balance.balance
    
    async def has_sufficient_balance(self, user_id: UUID, amount: int) -> bool:
        """Check if user has sufficient token balance."""
        balance = await UserTokenBalance.get_or_create(user_id)
        return balance.balance >= amount
```

### Redis Caching for Token Balances

```python
# core/services/redis.py (token-related methods)
async def cache_token_balance(user_id: str, balance: int) -> None:
    """Cache user token balance in Redis for 5 minutes."""
    key = f"token:balance:{user_id}"
    await redis.set(key, str(balance), ex=300)  # 5 minutes

async def get_cached_token_balance(user_id: str) -> Optional[int]:
    """Retrieve cached token balance from Redis."""
    key = f"token:balance:{user_id}"
    value = await redis.get(key)
    return int(value) if value is not None else None

async def invalidate_token_balance_cache(user_id: str) -> None:
    """Invalidate cached token balance."""
    key = f"token:balance:{user_id}"
    await redis.delete(key)
```

### Token Rate Limiting

```python
# core/services/token_limiter.py
from fastapi import HTTPException, status
from datetime import datetime, timedelta

class TokenRateLimiter:
    """Rate limiter for token operations to prevent abuse."""
    
    async def check_transaction_limit(self, user_id: UUID) -> None:
        """
        Limit token transactions to prevent abuse.
        Raises HTTPException if limit exceeded.
        """
        key = f"rate:token:txn:{user_id}"
        count = await redis.incr(key)
        
        # First transaction sets expiry
        if count == 1:
            await redis.expire(key, 60)  # 1 minute window
        
        # Limit to 30 transactions per minute
        if count > 30:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Token transaction rate limit exceeded. Please try again later."
            )
            
    async def check_purchase_limit(self, user_id: UUID) -> None:
        """
        Limit token purchases to prevent potential fraud.
        Raises HTTPException if limit exceeded.
        """
        key = f"rate:token:purchase:{user_id}"
        count = await redis.incr(key)
        
        # First transaction sets expiry
        if count == 1:
            await redis.expire(key, 3600)  # 1 hour window
        
        # Limit to 5 purchases per hour
        if count > 5:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Token purchase rate limit exceeded. Please try again later."
            )
```

## Security Considerations

1. **Atomic Transactions**: All token operations use database transactions for atomicity
2. **Positive Balance Constraint**: Database enforces non-negative token balances
3. **Rate Limiting**: Prevents abuse and potential DoS attacks
4. **Audit Trail**: Complete transaction history for all token operations
5. **Authorization**: Token operations require authenticated users with proper permissions
6. **Input Validation**: All token amounts validated before processing

## Monitoring and Alerts

The token system is monitored with the following alerts:

1. **High Token Consumption Rate**: Alert when token usage exceeds normal patterns
2. **Token Balance Low**: Alert when system token reserve becomes low
3. **Failed Token Transactions**: Alert on high rate of failed token operations
4. **Token Revenue Tracking**: Daily reports on token purchases and revenue
5. **Token Performance Metrics**: Monitor latency of token operations

## Integration Points

The token system integrates with:

1. **Payment Gateway**: For processing token purchases
2. **AI Services**: For token deduction on AI feature usage
3. **User Management**: For user token balance and profile information
4. **Analytics**: For user token usage patterns and business metrics
5. **Admin Dashboard**: For managing token packages and promotions

## Token Economy Management

Guidelines for managing the token economy:

1. **Value Consistency**: Maintain consistent token pricing relative to features
2. **Reward Mechanisms**: Implement strategic token rewards to drive engagement
3. **Special Promotions**: Create limited-time token offers for marketing campaigns
4. **Usage Analysis**: Regularly analyze token usage patterns to optimize pricing
5. **User Feedback**: Collect and incorporate user feedback on token economy

## Future Enhancements

Planned enhancements to the token system:

1. **Subscription Plans**: Token allocations as part of subscription plans
2. **Token Gifting**: Allow users to gift tokens to others
3. **Token Rewards Program**: Earn tokens through platform engagement
4. **Token Bundles**: Feature-specific token packages for different use cases
5. **Enhanced Analytics**: More granular reporting on token usage patterns 