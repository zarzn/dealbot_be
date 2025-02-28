"""Token service implementation"""
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment
from solana.transaction import Transaction
from base58 import b58decode
from uuid import UUID, uuid4
from redis.asyncio import Redis
from fastapi import Depends

from core.repositories.token import TokenRepository
from core.models.token import (
    TokenTransaction,
    TransactionStatus as TokenTransactionStatus,
    TransactionType as TokenTransactionType,
    TransactionType
)
from core.models.token_pricing import TokenPricing
from core.models.token_balance_history import TokenBalanceHistory
from core.exceptions import (
    TokenError,
    TokenBalanceError,
    TokenTransactionError,
    TokenValidationError,
    TokenRateLimitError,
    TokenServiceError,
    TokenOperationError,
    WalletConnectionError,
    SmartContractError,
    NetworkError,
    RepositoryError,
    APIError,
    APIServiceUnavailableError,
    APIAuthenticationError,
    APITimeoutError,
    ValidationError,
    TokenPricingError
)
from core.config import settings
from core.utils.logger import get_logger
from core.database import get_db
from core.services.redis import get_redis_service

logger = get_logger(__name__)

class ITokenService(ABC):
    """Abstract base class defining the token service interface"""
    
    @abstractmethod
    async def check_balance(self, user_id: str) -> Decimal:
        """Get user's current token balance"""
        raise NotImplementedError
    
    @abstractmethod
    async def connect_wallet(self, user_id: str, wallet_address: str) -> bool:
        """Connect user's wallet address"""
        raise NotImplementedError
    
    @abstractmethod
    async def get_transaction_history(
        self, 
        user_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[TokenTransaction]:
        """Get user's token transaction history"""
        raise NotImplementedError
    
    @abstractmethod
    async def get_pricing_info(self, service_type: str) -> Optional[TokenPricing]:
        """Get token pricing information"""
        raise NotImplementedError
    
    @abstractmethod
    async def deduct_tokens(
        self,
        user_id: str,
        amount: Decimal,
        reason: str
    ) -> TokenTransaction:
        """Deduct tokens from user's balance"""
        raise NotImplementedError
    
    @abstractmethod
    async def add_reward(
        self,
        user_id: str,
        amount: Decimal,
        reason: str
    ) -> TokenTransaction:
        """Add reward tokens to user's balance"""
        raise NotImplementedError
    
    @abstractmethod
    def validate_wallet_address(self, address: str) -> bool:
        """Validate Solana wallet address format"""
        raise NotImplementedError

    @abstractmethod
    async def validate_operation(
        self,
        user_id: str,
        operation: str
    ) -> None:
        """Validate if user can perform an operation"""
        raise NotImplementedError

class SolanaTokenService(ITokenService):
    """Solana token service implementation"""
    
    def __init__(self, db: AsyncSession, redis_service: Optional[Redis] = None):
        """Initialize Solana client and repository"""
        self.db = db
        self.repository = TokenRepository(db)
        self._redis = redis_service
        try:
            self.client = AsyncClient(
                settings.SOL_NETWORK_RPC,
                commitment=Commitment(settings.COMMITMENT_LEVEL)
            )
            self.program_id = settings.TOKEN_CONTRACT_ADDRESS
            
        except Exception as e:
            logger.error(f"Failed to initialize Solana client: {str(e)}")
            raise APIAuthenticationError(
                endpoint=settings.SOL_NETWORK_RPC,
                auth_type="rpc",
                error_details={"error": str(e)}
            )
        self._setup_retry_policy()

    def _setup_retry_policy(self):
        """Configure retry policy for external service calls"""
        self.retry_policy = retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=4, max=10),
            retry=retry_if_exception_type((APIError, TokenError)),
            reraise=True
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def check_balance(self, user_id: str) -> Decimal:
        """Get user's current token balance"""
        try:
            balance = await self.repository.get_user_balance(user_id)
            logger.debug(f"Retrieved balance for user {user_id}: {balance}")
            # Return 0 if balance is None
            if balance is None:
                return Decimal("0.0")
            return balance
        except Exception as e:
            logger.error(f"Failed to check balance for user {user_id}: {str(e)}")
            raise TokenBalanceError(
                operation="check_balance",
                reason=f"Failed to check balance: {str(e)}",
                balance=Decimal("0.0")
            )

    async def connect_wallet(self, user_id: str, wallet_address: str) -> bool:
        """Connect user's wallet address"""
        if not self.validate_wallet_address(wallet_address):
            logger.error(f"Invalid wallet address format: {wallet_address}")
            raise TokenValidationError(
                field="wallet_address",
                reason="Invalid wallet address format",
                details={"wallet_address": wallet_address}
            )
        
        try:
            # Verify wallet exists on Solana
            if not await self._verify_wallet_exists(wallet_address):
                raise TokenValidationError(
                    field="wallet_address",
                    reason="Wallet not found on Solana network",
                    details={"wallet_address": wallet_address}
                )
                
            result = await self.repository.connect_wallet(user_id, wallet_address)
            logger.info(f"Successfully connected wallet for user {user_id}")
            return result
        except TokenValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to connect wallet for user {user_id}: {str(e)}")
            raise TokenError(
                message=f"Failed to connect wallet: {str(e)}",
                details={"user_id": user_id, "wallet_address": wallet_address}
            )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def get_transaction_history(
        self, 
        user_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[TokenTransaction]:
        """Get user's token transaction history"""
        try:
            transactions = await self.repository.get_transaction_history(
                user_id, limit, offset
            )
            logger.debug(f"Retrieved {len(transactions)} transactions for user {user_id}")
            return transactions
        except Exception as e:
            logger.error(f"Failed to get transaction history for user {user_id}: {str(e)}")
            raise TokenTransactionError(
                transaction_id="history",
                operation="get_transaction_history",
                reason=f"Failed to get transaction history: {str(e)}",
                details={"user_id": user_id, "limit": limit, "offset": offset}
            )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def get_pricing_info(self, service_type: str) -> Optional[TokenPricing]:
        """Get token pricing for specific service type"""
        try:
            pricing = await self.repository.get_pricing_by_service(service_type)
            logger.debug(f"Retrieved pricing info for service {service_type}")
            return pricing
        except Exception as e:
            logger.error(f"Failed to get pricing info for service {service_type}: {str(e)}")
            raise TokenPricingError(
                operation="get_pricing_info",
                reason=f"Failed to get pricing info: {str(e)}",
                details={"service_type": service_type}
            )

    async def deduct_tokens(
        self,
        user_id: str,
        amount: Decimal,
        reason: str
    ) -> TokenTransaction:
        """Deduct tokens from user's balance"""
        if amount <= 0:
            logger.error(f"Invalid token deduction amount: {amount}")
            raise TokenValidationError(
                field="amount",
                reason="Amount must be positive",
                details={"amount": amount}
            )
        
        try:
            transaction = await self.repository.deduct_tokens(user_id, amount, reason)
            logger.info(f"Successfully deducted {amount} tokens from user {user_id}")
            return transaction
        except TokenBalanceError:
            logger.error(f"Insufficient balance for user {user_id}")
            raise
        except Exception as e:
            logger.error(f"Failed to deduct tokens for user {user_id}: {str(e)}")
            raise TokenTransactionError(
                transaction_id="deduct_tokens",
                operation="deduct_tokens", 
                reason=f"Failed to deduct tokens: {str(e)}",
                details={"user_id": user_id, "amount": str(amount), "reason": reason}
            )

    async def deduct_tokens_for_operation(
        self,
        user_id: str,
        operation: str,
        **kwargs
    ) -> TokenTransaction:
        """Deduct tokens for a specific operation.
        
        Args:
            user_id: The ID of the user
            operation: The operation type (e.g., market_search)
            **kwargs: Additional operation-specific parameters
            
        Returns:
            The created transaction record
            
        Raises:
            TokenValidationError: If validation fails
            TokenBalanceError: If insufficient balance
        """
        try:
            # Get pricing for the operation
            pricing = await self.get_pricing_info(operation)
            if not pricing:
                logger.warning(f"No pricing found for operation {operation}, skipping token deduction")
                # Create a dummy transaction for tracking purposes
                return TokenTransaction(
                    id=uuid4(),
                    user_id=user_id,
                    type=TransactionType.DEDUCTION.value,
                    amount=Decimal('0'),
                    status=TokenTransactionStatus.COMPLETED.value,
                    meta_data={"operation": operation, "reason": f"No pricing for {operation}", **kwargs}
                )
            
            # Deduct tokens based on the pricing
            reason = f"{operation} operation"
            if 'market_id' in kwargs:
                reason += f" for market {kwargs['market_id']}"
            
            return await self.deduct_tokens(user_id, pricing.token_cost, reason)
            
        except TokenBalanceError:
            raise
        except Exception as e:
            logger.error(f"Failed to deduct tokens for operation {operation}: {str(e)}")
            raise TokenTransactionError(
                transaction_id="deduct_tokens_for_operation",
                operation=operation,
                reason=f"Failed to deduct tokens for operation: {str(e)}",
                details={"user_id": user_id, "operation": operation, **kwargs}
            )

    async def add_reward(
        self,
        user_id: str,
        amount: Decimal,
        reason: str
    ) -> TokenTransaction:
        """Add reward tokens to user's balance"""
        if amount <= 0:
            logger.error(f"Invalid reward amount: {amount}")
            raise TokenValidationError(
                field="amount",
                reason="Amount must be positive",
                details={"amount": amount}
            )
        
        try:
            transaction = await self.repository.add_reward(user_id, amount, reason)
            logger.info(f"Successfully added {amount} tokens to user {user_id}")
            return transaction
        except Exception as e:
            logger.error(f"Failed to add reward for user {user_id}: {str(e)}")
            raise TokenTransactionError(
                transaction_id="add_reward",
                operation="add_reward",
                reason=str(e),
                details={
                    "user_id": user_id,
                    "amount": str(amount),
                    "reward_reason": reason
                }
            )

    async def rollback_transaction(self, tx_id: str) -> bool:
        """Rollback a failed transaction"""
        try:
            result = await self.repository.rollback_transaction(tx_id)
            logger.info(f"Successfully rolled back transaction {tx_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to rollback transaction {tx_id}: {str(e)}")
            raise TokenTransactionError(
                transaction_id=tx_id,
                operation="rollback_transaction",
                reason=f"Failed to rollback transaction: {str(e)}",
                details={"transaction_id": tx_id}
            )

    async def disconnect_wallet(self, user_id: str) -> bool:
        """Disconnect user's wallet"""
        try:
            result = await self.repository.disconnect_wallet(user_id)
            logger.info(f"Successfully disconnected wallet for user {user_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to disconnect wallet for user {user_id}: {str(e)}")
            raise TokenTransactionError(
                transaction_id="disconnect_wallet",
                operation="disconnect_wallet",
                reason=f"Failed to disconnect wallet: {str(e)}",
                details={"user_id": user_id}
            )

    async def validate_operation(
        self,
        user_id: str,
        operation: str
    ) -> None:
        """Validate if user can perform an operation.
        
        Args:
            user_id: The ID of the user
            operation: The operation to validate
            
        Raises:
            TokenValidationError: If validation fails
            TokenBalanceError: If insufficient balance
        """
        try:
            # Get operation cost
            pricing = await self.get_pricing_info(operation)
            if not pricing:
                logger.warning(f"No pricing found for operation {operation}")
                return  # No pricing means no cost
                
            # Check user balance
            balance = await self.check_balance(user_id)
            if balance < pricing.token_cost:
                raise TokenBalanceError(
                    operation="validate_operation",
                    reason=f"Insufficient balance for operation {operation}. Required: {pricing.token_cost}, Available: {balance}",
                    balance=balance
                )
                
            logger.debug(f"Operation {operation} validated for user {user_id}")
            
        except TokenBalanceError:
            raise
        except Exception as e:
            logger.error(f"Failed to validate operation {operation} for user {user_id}: {str(e)}")
            raise TokenValidationError(
                field="operation",
                reason=f"Operation validation failed: {str(e)}",
                details={"user_id": user_id, "operation": operation}
            )

    def validate_wallet_address(self, address: str) -> bool:
        """Validate Solana wallet address format"""
        try:
            # Decode base58 address
            decoded = b58decode(address)
            # Solana addresses are 32 bytes
            return len(decoded) == 32
        except Exception:
            return False

    async def _verify_wallet_exists(self, wallet_address: str) -> bool:
        """Verify wallet exists on Solana network"""
        try:
            response = await self.client.get_account_info(wallet_address)
            return response.value is not None
        except Exception as e:
            logger.error(f"Failed to verify wallet {wallet_address}: {str(e)}")
            return False

    async def get_balance(self, user_id: str) -> Decimal:
        """Get user's token balance.
        
        Args:
            user_id: User ID
            
        Returns:
            Decimal: User's current token balance
            
        Raises:
            TokenBalanceError: If retrieval fails
        """
        try:
            # Try to get from cache first if redis is available
            if self._redis:
                cached_balance = await self._redis.get(f"balance:{user_id}")
                if cached_balance:
                    # Check if cached_balance is a string or bytes
                    if isinstance(cached_balance, bytes):
                        balance = Decimal(cached_balance.decode())
                    else:
                        balance = Decimal(str(cached_balance))
                    logger.debug(f"Retrieved cached balance for user {user_id}: {balance}")
                    return balance
            
            # Get from repository
            balance_obj = await self.repository.get_user_balance(user_id)
            
            # Extract the actual balance value
            if balance_obj is None:
                balance = Decimal('0')
            elif hasattr(balance_obj, 'balance'):
                balance = Decimal(str(balance_obj.balance))
            else:
                balance = Decimal(str(balance_obj))
            
            # Cache the result if redis is available
            if self._redis and balance_obj:
                await self._redis.setex(
                    f"balance:{user_id}",
                    settings.BALANCE_CACHE_TTL,
                    str(balance)
                )
            
            logger.debug(f"Retrieved balance for user {user_id}: {balance_obj}")
            return balance
        except Exception as e:
            logger.error(f"Failed to get balance for user {user_id}: {str(e)}")
            raise TokenBalanceError(
                operation="get_balance",
                reason=f"Failed to get balance: {str(e)}",
                balance=None
            )
            
    async def transfer(
        self,
        from_user_id: str,
        to_user_id: str,
        amount: Decimal,
        reason: str
    ) -> TokenTransaction:
        """Transfer tokens between users.
        
        Args:
            from_user_id: Source user ID
            to_user_id: Destination user ID
            amount: Amount to transfer
            reason: Reason for transfer
            
        Returns:
            TokenTransaction: Created transaction
            
        Raises:
            TokenBalanceError: If source has insufficient balance
            TokenTransactionError: If transfer fails
        """
        if amount <= 0:
            raise TokenValidationError(
                field="amount",
                reason="Transfer amount must be positive",
                details={"amount": amount}
            )
        
        try:
            transaction = await self.repository.transfer_tokens(
                from_user_id=from_user_id,
                to_user_id=to_user_id,
                amount=amount,
                reason=reason
            )
            
            # Invalidate cache for both users
            if self._redis:
                await self._redis.delete(f"balance:{from_user_id}")
                await self._redis.delete(f"balance:{to_user_id}")
            
            logger.info(
                f"Successfully transferred {amount} tokens from {from_user_id} to {to_user_id}: {reason}"
            )
            return transaction
        except TokenBalanceError:
            raise
        except Exception as e:
            logger.error(f"Failed to transfer tokens: {str(e)}")
            raise TokenTransactionError(
                transaction_id="transfer",
                operation="transfer",
                reason=f"Transfer failed: {str(e)}",
                details={"from_user_id": from_user_id, "to_user_id": to_user_id, "amount": str(amount)}
            )
            
    async def deduct_service_fee(
        self,
        user_id: str,
        amount: Decimal,
        service_type: str
    ) -> TokenTransaction:
        """Deduct service fee from user's balance.
        
        Args:
            user_id: User ID
            amount: Fee amount
            service_type: Type of service
            
        Returns:
            TokenTransaction: Created transaction
            
        Raises:
            TokenBalanceError: If insufficient balance
            TokenTransactionError: If deduction fails
        """
        if amount <= 0:
            raise TokenValidationError(
                field="amount",
                reason="Fee amount must be positive",
                details={"amount": amount}
            )
            
        try:
            transaction = await self.repository.deduct_tokens(
                user_id=user_id,
                amount=amount,
                reason=f"Service fee: {service_type}"
            )
            
            # Invalidate cache
            if self._redis:
                await self._redis.delete(f"balance:{user_id}")
                
            logger.info(f"Deducted service fee of {amount} from user {user_id} for {service_type}")
            return transaction
        except TokenBalanceError:
            raise
        except Exception as e:
            logger.error(f"Failed to deduct service fee: {str(e)}")
            raise TokenTransactionError(
                transaction_id="service_fee",
                operation="deduct_service_fee",
                reason=f"Failed to deduct service fee: {str(e)}",
                details={"user_id": user_id, "amount": str(amount), "service_type": service_type}
            )
            
    async def clear_balance_cache(self, user_id: str) -> None:
        """Clear cached balance for a user.
        
        Args:
            user_id: User ID
        """
        if self._redis:
            await self._redis.delete(f"balance:{user_id}")
            logger.debug(f"Cleared balance cache for user {user_id}")
            
    async def validate_transaction(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate transaction data.
        
        Args:
            transaction_data: Transaction data to validate
            
        Returns:
            Dict[str, Any]: Validated transaction data
            
        Raises:
            ValidationError: If validation fails
        """
        # Validate amount
        amount = transaction_data.get('amount')
        if not amount or not isinstance(amount, Decimal) or amount <= 0:
            raise ValidationError("Transaction amount must be a positive Decimal")
            
        # Check if the amount is too small (less than 1E-8)
        if amount < Decimal('0.00000001'):
            raise ValidationError("Transaction amount is too small. Minimum allowed is 0.00000001")
            
        # Validate type
        tx_type = transaction_data.get('type')
        token_valid_types = [t.value for t in TokenTransactionType]
        transaction_valid_types = [t.value for t in TransactionType]
        
        # Combine all valid types
        valid_types = list(set(token_valid_types + transaction_valid_types))
        
        if not tx_type or tx_type not in valid_types:
            raise ValidationError(f"Invalid transaction type. Must be one of: {', '.join(valid_types)}")
            
        # Return validated data
        return transaction_data
        
    async def create_transaction(
        self,
        user_id: str,
        amount: Decimal,
        type: str,
        status: Optional[str] = None,
        reason: Optional[str] = None,
        meta_data: Optional[Dict[str, Any]] = None
    ) -> TokenTransaction:
        """Create a new token transaction.
        
        Args:
            user_id: User ID
            amount: Transaction amount
            type: Transaction type (one of TokenTransactionType values)
            status: Transaction status (optional)
            reason: Reason for transaction (optional)
            meta_data: Optional transaction metadata
            
        Returns:
            TokenTransaction: Created transaction
            
        Raises:
            TokenTransactionError: If transaction creation fails
            ValidationError: If transaction data is invalid
        """
        try:
            # Process meta_data to ensure UUID objects are serialized
            processed_meta_data = {}
            if meta_data:
                for key, value in meta_data.items():
                    # Convert UUID to string
                    if isinstance(value, UUID):
                        processed_meta_data[key] = str(value)
                    else:
                        processed_meta_data[key] = value
            
            # Validate transaction data
            transaction_data = {
                'user_id': user_id,
                'type': type,
                'amount': amount,
                'reason': reason or "",
                'meta_data': processed_meta_data or {}
            }
            
            await self.validate_transaction(transaction_data)
            
            # Set default status if not provided
            if not status:
                status = TokenTransactionStatus.PENDING.value
            
            # Create transaction record
            transaction = await self.repository.create_transaction(
                user_id=user_id,
                transaction_type=type,
                amount=amount,
                status=status,
                meta_data={
                    'reason': reason or "Transaction",
                    **(processed_meta_data or {})
                }
            )
            
            # Update user balance based on transaction type
            if type in [TokenTransactionType.REWARD.value, TokenTransactionType.REFUND.value, TokenTransactionType.CREDIT.value]:
                # Add to balance
                balance = await self.repository.get_user_balance(user_id)
                if balance:
                    await balance.update_balance(
                        self.db,
                        amount,
                        type,
                        reason or "Transaction",
                        transaction.id,
                        processed_meta_data
                    )
                    
                # Invalidate cache
                if self._redis:
                    await self._redis.delete(f"balance:{user_id}")
            
            # Return transaction
            return transaction
        except ValidationError as e:
            raise e
        except Exception as e:
            logger.error(f"Failed to create transaction: {str(e)}")
            raise TokenTransactionError(
                transaction_id="create_transaction",
                operation="create_transaction",
                reason=f"Failed to create transaction: {str(e)}",
                details={"user_id": user_id, "amount": str(amount), "type": type}
            )

# Export SolanaTokenService as TokenService for backward compatibility
TokenService = SolanaTokenService

# Add this function to provide a dependency for the token service
async def get_token_service(
    db: AsyncSession = Depends(get_db),
    redis_service = Depends(get_redis_service)
) -> SolanaTokenService:
    """Get a token service instance."""
    return SolanaTokenService(db, redis_service)
