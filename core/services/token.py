"""Token service implementation"""
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
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
    TransactionType,
    TransactionStatus
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
            return Decimal(str(balance.balance))
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
        self, user_id: str, amount: Decimal, reason: str = ""
    ) -> Dict[str, Any]:
        """Deduct tokens from a user's balance"""
        try:
            # Check if user has enough balance
            current_balance = await self.check_balance(user_id)
            if current_balance < amount:
                raise TokenBalanceError(
                    operation="deduct_tokens",
                    reason=f"Insufficient balance for deduction. Required: {amount}, Available: {current_balance}",
                    balance=current_balance
                )

            # Create transaction - use positive amount for the transaction record
            # but specify the transaction type as DEDUCTION
            transaction = await self.repository.create_transaction(
                user_id=user_id,
                transaction_type=TransactionType.DEDUCTION.value,
                amount=amount,  # Use positive amount to satisfy the database constraint
                status=TransactionStatus.COMPLETED.value,
                meta_data={"reason": reason}
            )

            # Update user's balance - use negative amount for the balance update
            updated_balance = await self.repository.update_user_balance(user_id, -amount)

            # Clear balance cache
            if self._redis:
                cache_key = f"token:balance:{user_id}"
                await self._redis.delete(cache_key)

            return {
                "success": True,
                "transaction_id": transaction.id if transaction else "",
                "user_id": user_id,
                "amount": amount,
                "reason": reason,
                "new_balance": Decimal(str(updated_balance.balance)) if hasattr(updated_balance, 'balance') else updated_balance
            }
        except TokenBalanceError as e:
            logger.error(f"Token balance error during deduction: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to deduct tokens: {str(e)}")
            raise TokenTransactionError(
                transaction_id="",
                operation="deduct_tokens",
                reason=f"Failed to deduct tokens: {str(e)}"
            )

    async def add_reward(
        self,
        user_id: str,
        amount: Decimal,
        reason: str
    ) -> TokenTransaction:
        """Add reward tokens to user's balance"""
        if amount <= 0:
            logger.error(f"Invalid token reward amount: {amount}")
            raise TokenValidationError(
                message="Amount must be positive",
                field="amount",
                value=amount
            )
        
        try:
            # Create reward transaction
            transaction = await self.repository.create_transaction(
                user_id=user_id,
                amount=amount,
                transaction_type=TransactionType.REWARD.value,
                status=TransactionStatus.COMPLETED.value,
                meta_data={"reason": reason}
            )
            
            # Clear cache
            await self.clear_balance_cache(user_id)
            
            logger.info(f"Added {amount} reward tokens to user {user_id} for {reason}")
            return transaction
        except Exception as e:
            logger.error(f"Failed to add reward tokens for user {user_id}: {str(e)}")
            raise TokenTransactionError(
                transaction_id=None,
                operation="add_reward",
                reason=f"Failed to add reward tokens: {str(e)}",
                details={"user_id": user_id, "amount": amount, "reason": reason}
            )

    def validate_wallet_address(self, address: str) -> bool:
        """Validate Solana wallet address format"""
        try:
            # Solana addresses are base58 encoded and 32 bytes long
            decoded = b58decode(address)
            return len(decoded) == 32
        except Exception:
            return False

    async def _verify_wallet_exists(self, address: str) -> bool:
        """Verify wallet exists on Solana network"""
        try:
            response = await self.client.get_account_info(address)
            return response.value is not None
        except Exception as e:
            logger.error(f"Error verifying wallet {address}: {str(e)}")
            return False

    async def validate_operation(
        self,
        user_id: str,
        operation: str
    ) -> None:
        """Validate if user can perform an operation"""
        try:
            # Get pricing for operation
            pricing = await self.get_pricing_info(operation)
            if not pricing:
                logger.warning(f"No pricing found for operation {operation}")
                return
            
            # Get user balance
            balance = await self.check_balance(user_id)
            
            # Check if user has enough tokens
            if balance < pricing.cost:
                logger.error(f"Insufficient balance for operation {operation}: {balance} < {pricing.cost}")
                raise TokenBalanceError(
                    operation=operation,
                    reason="Insufficient balance for operation",
                    balance=balance
                )
        except TokenBalanceError:
            raise
        except Exception as e:
            logger.error(f"Failed to validate operation {operation} for user {user_id}: {str(e)}")
            raise TokenValidationError(
                field="operation",
                reason=f"Failed to validate operation: {str(e)}",
                details={"user_id": user_id, "operation": operation}
            )

    async def get_balance(self, user_id: str) -> Decimal:
        """Get user's token balance with caching"""
        # Try to get from cache first
        if self._redis:
            cache_key = f"token:balance:{user_id}"
            cached = await self._redis.get(cache_key)
            if cached:
                try:
                    return Decimal(cached)
                except (ValueError, TypeError):
                    # Invalid cache value, continue to fetch from DB
                    pass
        
        # Get from database
        balance = await self.check_balance(user_id)
        
        # Handle None balance by returning 0
        if balance is None:
            balance = Decimal("0.0")
        
        # If balance is a TokenBalance object, extract the balance value
        if hasattr(balance, 'balance'):
            balance = Decimal(str(balance.balance))
        
        # Cache the result
        if self._redis:
            cache_key = f"token:balance:{user_id}"
            await self._redis.setex(cache_key, 300, str(balance))  # 5 minutes in seconds
        
        return balance

    async def transfer(
        self, from_user_id: str, to_user_id: str, amount: Decimal, reason: str = ""
    ) -> Dict[str, Any]:
        """Transfer tokens from one user to another"""
        try:
            # Check if sender has enough balance
            sender_balance = await self.check_balance(from_user_id)
            if sender_balance < amount:
                raise TokenBalanceError(
                    operation="transfer",
                    reason=f"Insufficient balance for transfer. Required: {amount}, Available: {sender_balance}",
                    balance=sender_balance
                )

            # Create outgoing transaction (use DEDUCTION instead of OUTGOING)
            outgoing_tx = await self.repository.create_transaction(
                user_id=from_user_id,
                transaction_type=TransactionType.DEDUCTION.value,  # Use DEDUCTION instead of OUTGOING
                amount=amount,  # Use positive amount
                status=TransactionStatus.COMPLETED.value,
                meta_data={"recipient": str(to_user_id), "reason": reason, "transfer_type": "outgoing"}  # Add transfer_type for clarity
            )

            # Create incoming transaction (use CREDIT instead of INCOMING)
            incoming_tx = await self.repository.create_transaction(
                user_id=to_user_id,
                transaction_type=TransactionType.CREDIT.value,  # Use CREDIT instead of INCOMING
                amount=amount,  # Positive for incoming
                status=TransactionStatus.COMPLETED.value,
                meta_data={"sender": str(from_user_id), "reason": reason, "transfer_type": "incoming"}  # Add transfer_type for clarity
            )

            # Update sender's balance
            await self.repository.update_user_balance(from_user_id, -amount)
            
            # Update recipient's balance
            await self.repository.update_user_balance(to_user_id, amount)

            # Clear balance cache for both users
            if self._redis:
                sender_cache_key = f"token:balance:{from_user_id}"
                recipient_cache_key = f"token:balance:{to_user_id}"
                await self._redis.delete(sender_cache_key)
                await self._redis.delete(recipient_cache_key)

            return {
                "success": True,
                "outgoing_transaction_id": outgoing_tx.id if outgoing_tx else "",
                "incoming_transaction_id": incoming_tx.id if incoming_tx else "",
                "amount": amount,
                "from_user_id": from_user_id,
                "to_user_id": to_user_id,
                "reason": reason
            }
        except TokenBalanceError as e:
            logger.error(f"Token balance error during transfer: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to transfer tokens: {str(e)}")
            raise TokenTransactionError(
                transaction_id="",
                operation="transfer",
                reason=f"Failed to transfer tokens: {str(e)}"
            )

    async def deduct_service_fee(
        self, user_id: str, amount: Decimal, service_type: str
    ) -> Dict[str, Any]:
        """Deduct service fee from user's balance"""
        try:
            result = await self.deduct_tokens(
                user_id=user_id,
                amount=amount,
                reason=f"Service fee: {service_type}"
            )
            return result
        except TokenBalanceError as e:
            logger.error(f"Token balance error during service fee deduction: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to deduct service fee: {str(e)}")
            raise TokenTransactionError(
                transaction_id="",
                operation="deduct_service_fee",
                reason=f"Failed to deduct service fee: {str(e)}"
            )

    async def clear_balance_cache(self, user_id: str) -> None:
        """Clear user's balance cache"""
        if self._redis:
            cache_key = f"token:balance:{user_id}"
            await self._redis.delete(cache_key)
            logger.debug(f"Cleared balance cache for user {user_id}")

    async def create_transaction(
        self,
        user_id: str,
        amount: Decimal,
        type: str,
        status: str,
        description: Optional[str] = None,
        meta_data: Optional[Dict[str, Any]] = None
    ) -> TokenTransaction:
        """Create a token transaction.
        
        Args:
            user_id: User ID
            amount: Transaction amount
            type: Transaction type
            status: Transaction status
            description: Optional transaction description (for backward compatibility)
            meta_data: Optional transaction metadata
            
        Returns:
            The created transaction
        """
        # Validate amount
        if amount <= 0:
            raise TokenValidationError(
                field="amount",
                reason="Amount must be positive"
            )
        
        # Ensure amount has at most 8 decimal places
        if amount.as_tuple().exponent < -8:
            raise TokenValidationError(
                field="amount",
                reason="Amount cannot have more than 8 decimal places"
            )
        
        # Handle description for backward compatibility
        transaction_meta_data = meta_data or {}
        if description and 'description' not in transaction_meta_data:
            transaction_meta_data['description'] = description
        
        try:
            # Create transaction
            transaction = await self.repository.create_transaction(
                user_id=user_id,
                transaction_type=type,
                amount=amount,
                status=status,
                meta_data=transaction_meta_data
            )
            
            # Update user balance if transaction is completed
            if status == TransactionStatus.COMPLETED.value:
                # For deduction type, we subtract from balance
                if type in [TransactionType.DEDUCTION.value, TransactionType.OUTGOING.value]:
                    await self.repository.update_user_balance(user_id, -amount)
                # For other types (reward, refund, credit, incoming), we add to balance
                else:
                    await self.repository.update_user_balance(user_id, amount)
                
                # Clear balance cache
                await self.clear_balance_cache(user_id)
            
            return transaction
        except Exception as e:
            logger.error(f"Failed to create transaction for user {user_id}: {str(e)}")
            raise TokenTransactionError(
                transaction_id=None,
                operation="create_transaction",
                reason=f"Failed to create transaction: {str(e)}",
                details={"user_id": user_id, "amount": amount, "type": type}
            )

    async def validate_transaction(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate transaction data"""
        errors = {}
        
        # Validate amount
        amount = data.get("amount")
        if not amount or not isinstance(amount, Decimal) or amount <= 0:
            errors["amount"] = "Amount must be a positive decimal"
        
        # Validate type
        tx_type = data.get("type")
        if not tx_type or tx_type not in [t.value for t in TokenTransactionType]:
            errors["type"] = f"Type must be one of: {', '.join([t.value for t in TokenTransactionType])}"
        
        # Validate status
        status = data.get("status")
        if status and status not in [s.value for s in TokenTransactionStatus]:
            errors["status"] = f"Status must be one of: {', '.join([s.value for s in TokenTransactionStatus])}"
        
        if errors:
            raise ValidationError(
                message="Invalid transaction data",
                errors=errors
            )
        
        return data

    async def update_balance(self, user_id: str, amount: Decimal) -> Decimal:
        """Update user's token balance"""
        try:
            # Get current balance first to ensure it exists
            current_balance = await self.check_balance(user_id)
            
            # Update balance in repository
            updated_balance = await self.repository.update_user_balance(user_id, amount)
            
            # Clear cache
            if self._redis:
                cache_key = f"token:balance:{user_id}"
                await self._redis.delete(cache_key)
            
            # Return the updated balance value
            if updated_balance is None:
                return Decimal("0.0")
            
            if hasattr(updated_balance, 'balance'):
                return Decimal(str(updated_balance.balance))
            
            return Decimal(str(updated_balance))
        except Exception as e:
            logger.error(f"Failed to update balance for user {user_id}: {str(e)}")
            raise TokenBalanceError(
                operation="update_balance",
                reason=f"Failed to update balance: {str(e)}",
                balance=current_balance if 'current_balance' in locals() else Decimal("0.0")
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
