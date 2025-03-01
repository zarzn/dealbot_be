# Token System Documentation

## Overview
The AI Agentic Deals System uses a native cryptocurrency token built on the Solana blockchain for service access and rewards. The token system manages user balances, transactions, and service costs.

## Token Contract

### Configuration
```typescript
// Token contract configuration
const TOKEN_CONFIG = {
  name: "Deals Token",
  symbol: "DEAL",
  decimals: 8,
  initialSupply: 1_000_000_000,  // 1 billion tokens
  mintAuthority: TREASURY_WALLET
};
```

### Smart Contract Interface
```solidity
interface IDealsToken {
    function balanceOf(address account) external view returns (uint256);
    function transfer(address to, uint256 amount) external returns (bool);
    function approve(address spender, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function mint(address to, uint256 amount) external;
    function burn(uint256 amount) external;
}
```

## Token Service

### Service Implementation
```python
# backend/core/services/token.py
from decimal import Decimal
from uuid import UUID
from typing import Optional

class TokenService:
    def __init__(self, contract: Contract, redis: Redis):
        self.contract = contract
        self.redis = redis
        self.cache_ttl = 300  # 5 minutes

    async def get_balance(self, user_id: UUID) -> Decimal:
        """Get user's token balance."""
        # Try cache first
        cached = await self.redis.get(f"balance:{user_id}")
        if cached:
            return Decimal(cached)

        # Get from blockchain
        balance = await self.contract.balance_of(user_id)
        
        # Cache result
        await self.redis.setex(
            f"balance:{user_id}",
            self.cache_ttl,
            str(balance)
        )
        
        return balance

    async def transfer(
        self,
        from_id: UUID,
        to_id: UUID,
        amount: Decimal,
        reason: str
    ) -> bool:
        """Transfer tokens between users."""
        try:
            # Execute transfer
            tx = await self.contract.transfer(from_id, to_id, amount)
            
            # Record transaction
            await self.record_transaction(
                from_id=from_id,
                to_id=to_id,
                amount=amount,
                tx_hash=tx.hash,
                reason=reason
            )
            
            # Invalidate cache
            await self.redis.delete(f"balance:{from_id}")
            await self.redis.delete(f"balance:{to_id}")
            
            return True
        except Exception as e:
            logger.error(f"Transfer failed: {str(e)}")
            return False

    async def deduct_service_fee(
        self,
        user_id: UUID,
        service_type: str
    ) -> bool:
        """Deduct service fee from user."""
        fee = await self.get_service_fee(service_type)
        
        if not await self.has_sufficient_balance(user_id, fee):
            raise InsufficientBalanceError()
        
        return await self.transfer(
            from_id=user_id,
            to_id=TREASURY_WALLET,
            amount=fee,
            reason=f"Service fee: {service_type}"
        )
```

### Balance Management
```python
class BalanceManager:
    def __init__(self, token_service: TokenService):
        self.token_service = token_service

    async def check_balance(
        self,
        user_id: UUID,
        required_amount: Decimal
    ) -> bool:
        """Check if user has sufficient balance."""
        balance = await self.token_service.get_balance(user_id)
        return balance >= required_amount

    async def update_balance_cache(
        self,
        user_id: UUID,
        new_balance: Decimal
    ):
        """Update cached balance."""
        await self.redis.setex(
            f"balance:{user_id}",
            300,  # 5 minutes TTL
            str(new_balance)
        )
```

## Transaction Management

### Transaction Recording
```python
class TransactionRecorder:
    async def record_transaction(
        self,
        from_id: Optional[UUID],
        to_id: Optional[UUID],
        amount: Decimal,
        tx_hash: str,
        reason: str
    ):
        """Record token transaction."""
        transaction = TokenTransaction(
            from_user_id=from_id,
            to_user_id=to_id,
            amount=amount,
            tx_hash=tx_hash,
            type=self.get_transaction_type(from_id, to_id),
            status="pending",
            created_at=datetime.utcnow()
        )
        
        await transaction.save()
        
        # Record in balance history
        if from_id:
            await self.record_balance_change(
                user_id=from_id,
                amount=-amount,
                reason=reason
            )
        
        if to_id:
            await self.record_balance_change(
                user_id=to_id,
                amount=amount,
                reason=reason
            )
```

### Balance History
```python
class BalanceHistoryRecorder:
    async def record_balance_change(
        self,
        user_id: UUID,
        amount: Decimal,
        reason: str
    ):
        """Record balance change in history."""
        old_balance = await self.token_service.get_balance(user_id)
        new_balance = old_balance + amount
        
        history = TokenBalanceHistory(
            user_id=user_id,
            balance_before=old_balance,
            balance_after=new_balance,
            change_amount=amount,
            change_type=self.get_change_type(amount),
            reason=reason,
            created_at=datetime.utcnow()
        )
        
        await history.save()
```

## Service Pricing

### Price Configuration
```python
# backend/core/config/token_pricing.py
TOKEN_PRICING = {
    "search": Decimal("0.1"),    # 0.1 tokens per search
    "goal": Decimal("1.0"),      # 1.0 tokens per goal
    "analysis": Decimal("0.5"),  # 0.5 tokens per analysis
    "notification": Decimal("0.05")  # 0.05 tokens per notification
}

class PricingService:
    async def get_service_fee(self, service_type: str) -> Decimal:
        """Get current fee for service type."""
        pricing = await TokenPricing.filter(
            service_type=service_type,
            is_active=True,
            valid_from__lte=datetime.utcnow(),
            valid_to__gte=datetime.utcnow()
        ).first()
        
        return pricing.token_cost if pricing else TOKEN_PRICING[service_type]
```

## Wallet Integration

### Wallet Connection
```python
class WalletManager:
    async def connect_wallet(
        self,
        user_id: UUID,
        wallet_address: str
    ) -> bool:
        """Connect user's wallet."""
        # Validate wallet address
        if not is_valid_solana_address(wallet_address):
            raise InvalidWalletAddressError()
        
        # Check if wallet is already connected
        existing = await TokenWallet.filter(
            wallet_address=wallet_address
        ).first()
        if existing:
            raise WalletAlreadyConnectedError()
        
        # Create wallet connection
        wallet = TokenWallet(
            user_id=user_id,
            wallet_address=wallet_address,
            status="active",
            connected_at=datetime.utcnow()
        )
        
        await wallet.save()
        return True

    async def disconnect_wallet(
        self,
        user_id: UUID,
        wallet_address: str
    ) -> bool:
        """Disconnect user's wallet."""
        wallet = await TokenWallet.filter(
            user_id=user_id,
            wallet_address=wallet_address
        ).first()
        
        if not wallet:
            raise WalletNotFoundError()
        
        wallet.status = "inactive"
        wallet.disconnected_at = datetime.utcnow()
        await wallet.save()
        
        return True
```

## Reward System

### Reward Distribution
```python
class RewardDistributor:
    async def distribute_reward(
        self,
        user_id: UUID,
        reward_type: str,
        amount: Decimal
    ) -> bool:
        """Distribute reward to user."""
        try:
            # Transfer reward tokens
            success = await self.token_service.transfer(
                from_id=REWARD_WALLET,
                to_id=user_id,
                amount=amount,
                reason=f"Reward: {reward_type}"
            )
            
            if success:
                # Record reward
                await self.record_reward(
                    user_id=user_id,
                    reward_type=reward_type,
                    amount=amount
                )
            
            return success
        except Exception as e:
            logger.error(f"Reward distribution failed: {str(e)}")
            return False
```

## Error Handling

### Token Errors
```python
class TokenError(Exception):
    """Base class for token errors."""
    pass

class InsufficientBalanceError(TokenError):
    """Raised when user has insufficient balance."""
    pass

class InvalidWalletAddressError(TokenError):
    """Raised when wallet address is invalid."""
    pass

class TransactionFailedError(TokenError):
    """Raised when transaction fails."""
    pass
```

### Error Handling
```python
async def handle_token_error(error: TokenError):
    """Handle token-related errors."""
    error_handlers = {
        InsufficientBalanceError: handle_insufficient_balance,
        InvalidWalletAddressError: handle_invalid_wallet,
        TransactionFailedError: handle_transaction_failure
    }
    
    handler = error_handlers.get(type(error))
    if handler:
        await handler(error)
    else:
        logger.error(f"Unhandled token error: {str(error)}")
```

## Monitoring and Metrics

### Token Metrics
```python
# Prometheus metrics
token_transactions = Counter(
    'token_transactions_total',
    'Total token transactions',
    ['type', 'status']
)

token_balances = Gauge(
    'token_balances',
    'User token balances',
    ['user_id']
)

transaction_duration = Histogram(
    'token_transaction_duration_seconds',
    'Token transaction duration'
)
```

### Transaction Monitoring
```python
class TransactionMonitor:
    async def monitor_transaction(self, tx_hash: str):
        """Monitor transaction status."""
        try:
            with transaction_duration.time():
                status = await self.contract.get_transaction_status(tx_hash)
                
                if status == "confirmed":
                    await self.handle_confirmed_transaction(tx_hash)
                elif status == "failed":
                    await self.handle_failed_transaction(tx_hash)
                
                token_transactions.labels(
                    type="transfer",
                    status=status
                ).inc()
        except Exception as e:
            logger.error(f"Transaction monitoring failed: {str(e)}")
```

## Testing

### Unit Tests
```python
async def test_token_transfer():
    """Test token transfer between users."""
    from_user = await create_test_user()
    to_user = await create_test_user()
    amount = Decimal("1.0")
    
    # Initial balance
    initial_from = await token_service.get_balance(from_user.id)
    initial_to = await token_service.get_balance(to_user.id)
    
    # Execute transfer
    success = await token_service.transfer(
        from_id=from_user.id,
        to_id=to_user.id,
        amount=amount,
        reason="Test transfer"
    )
    
    assert success
    
    # Verify balances
    final_from = await token_service.get_balance(from_user.id)
    final_to = await token_service.get_balance(to_user.id)
    
    assert final_from == initial_from - amount
    assert final_to == initial_to + amount
```

### Integration Tests
```python
async def test_service_fee_deduction():
    """Test service fee deduction."""
    user = await create_test_user()
    service_type = "search"
    
    # Get service fee
    fee = await token_service.get_service_fee(service_type)
    
    # Initial balance
    initial_balance = await token_service.get_balance(user.id)
    
    # Deduct fee
    success = await token_service.deduct_service_fee(
        user_id=user.id,
        service_type=service_type
    )
    
    assert success
    
    # Verify balance
    final_balance = await token_service.get_balance(user.id)
    assert final_balance == initial_balance - fee
```

## Best Practices

### 1. Transaction Safety
- Validate balances before transfer
- Use atomic transactions
- Implement proper rollback
- Monitor transaction status

### 2. Cache Management
- Cache balance queries
- Implement cache invalidation
- Use appropriate TTL
- Handle cache failures

### 3. Error Handling
- Handle network errors
- Implement retry logic
- Log all errors
- Notify on critical errors

### 4. Security
- Validate wallet addresses
- Secure private keys
- Monitor suspicious activity
- Implement rate limiting 