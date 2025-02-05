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

from core.repositories.token import TokenRepository
from core.models.token import (
    TokenTransaction,
    TransactionStatus as TokenTransactionStatus,
    TransactionType as TokenTransactionType
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
    APITimeoutError
)
from core.config import settings
from core.utils.logger import get_logger

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

class SolanaTokenService(ITokenService):
    """Solana token service implementation"""
    
    def __init__(self, db: AsyncSession):
        """Initialize Solana client and repository"""
        self.db = db
        self.repository = TokenRepository(db)
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
            return balance
        except Exception as e:
            logger.error(f"Failed to check balance for user {user_id}: {str(e)}")
            raise TokenBalanceError(f"Failed to check balance: {str(e)}")

    async def connect_wallet(self, user_id: str, wallet_address: str) -> bool:
        """Connect user's wallet address"""
        if not self.validate_wallet_address(wallet_address):
            logger.error(f"Invalid wallet address format: {wallet_address}")
            raise TokenValidationError("Invalid wallet address format")
        
        try:
            # Verify wallet exists on Solana
            if not await self._verify_wallet_exists(wallet_address):
                raise TokenValidationError("Wallet not found on Solana network")
                
            result = await self.repository.connect_wallet(user_id, wallet_address)
            logger.info(f"Successfully connected wallet for user {user_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to connect wallet for user {user_id}: {str(e)}")
            raise TokenError(f"Failed to connect wallet: {str(e)}")

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
            raise TokenTransactionError(f"Failed to get transaction history: {str(e)}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def get_pricing_info(self, service_type: str) -> Optional[TokenPricing]:
        """Get token pricing for specific service type"""
        try:
            pricing = await self.repository.get_pricing_by_service(service_type)
            logger.debug(f"Retrieved pricing info for service {service_type}")
            return pricing
        except Exception as e:
            logger.error(f"Failed to get pricing info for service {service_type}: {str(e)}")
            raise

    async def deduct_tokens(
        self,
        user_id: str,
        amount: Decimal,
        reason: str
    ) -> TokenTransaction:
        """Deduct tokens from user's balance"""
        if amount <= 0:
            logger.error(f"Invalid token deduction amount: {amount}")
            raise TokenValidationError("Amount must be positive")
        
        try:
            transaction = await self.repository.deduct_tokens(user_id, amount, reason)
            logger.info(f"Successfully deducted {amount} tokens from user {user_id}")
            return transaction
        except TokenBalanceError:
            logger.error(f"Insufficient balance for user {user_id}")
            raise
        except Exception as e:
            logger.error(f"Failed to deduct tokens for user {user_id}: {str(e)}")
            raise TokenTransactionError(f"Failed to deduct tokens: {str(e)}")

    async def add_reward(
        self,
        user_id: str,
        amount: Decimal,
        reason: str
    ) -> TokenTransaction:
        """Add reward tokens to user's balance"""
        if amount <= 0:
            logger.error(f"Invalid reward amount: {amount}")
            raise TokenValidationError("Amount must be positive")
        
        try:
            transaction = await self.repository.add_reward(user_id, amount, reason)
            logger.info(f"Successfully added {amount} tokens to user {user_id}")
            return transaction
        except Exception as e:
            logger.error(f"Failed to add reward for user {user_id}: {str(e)}")
            raise TokenTransactionError(f"Failed to add reward: {str(e)}")

    async def rollback_transaction(self, tx_id: str) -> bool:
        """Rollback a failed transaction"""
        try:
            result = await self.repository.rollback_transaction(tx_id)
            logger.info(f"Successfully rolled back transaction {tx_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to rollback transaction {tx_id}: {str(e)}")
            raise TokenTransactionError(f"Failed to rollback transaction: {str(e)}")

    async def disconnect_wallet(self, user_id: str) -> bool:
        """Disconnect user's wallet"""
        try:
            result = await self.repository.disconnect_wallet(user_id)
            logger.info(f"Successfully disconnected wallet for user {user_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to disconnect wallet for user {user_id}: {str(e)}")
            raise TokenTransactionError(f"Failed to disconnect wallet: {str(e)}")

    async def validate_wallet(self, wallet_address: str) -> bool:
        """Validate wallet address and check balance"""
        if not self.validate_wallet_address(wallet_address):
            return False
        
        try:
            return await self._verify_wallet_exists(wallet_address)
        except Exception as e:
            logger.error(f"Failed to validate wallet {wallet_address}: {str(e)}")
            return False

    async def process_transaction(self, tx_id: str) -> bool:
        """Process a pending transaction"""
        try:
            result = await self.repository.process_transaction(tx_id)
            logger.info(f"Successfully processed transaction {tx_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to process transaction {tx_id}: {str(e)}")
            raise TokenTransactionError(f"Failed to process transaction: {str(e)}")

    async def monitor_transactions(self) -> Dict[str, Any]:
        """Monitor transaction status and health"""
        try:
            stats = await self.repository.get_transaction_stats()
            logger.info("Successfully retrieved transaction stats")
            return stats
        except Exception as e:
            logger.error(f"Failed to monitor transactions: {str(e)}")
            raise TokenTransactionError(f"Failed to monitor transactions: {str(e)}")

    async def _verify_wallet_exists(self, wallet_address: str) -> bool:
        """Verify wallet exists on Solana network"""
        try:
            response = await self.client.get_account_info(wallet_address)
            return response.get('result') is not None
        except Exception as e:
            logger.error(f"Failed to verify wallet {wallet_address}: {str(e)}")
            return False

    def validate_wallet_address(self, address: str) -> bool:
        """Validate Solana wallet address format"""
        try:
            # Solana addresses are base58 encoded and 32-44 characters long
            if not address or len(address) < 32 or len(address) > 44:
                return False
            # Check if address is valid base58
            b58decode(address)
            return True
        except Exception:
            return False

    async def validate_pricing(self, service_type: str, amount: Decimal) -> bool:
        """Validate token pricing for a service"""
        try:
            pricing = await self.get_pricing_info(service_type)
            if not pricing:
                return False
            return amount >= pricing.token_cost
        except Exception as e:
            logger.error(f"Failed to validate pricing for {service_type}: {str(e)}")
            return False

# Export SolanaTokenService as TokenService for backward compatibility
TokenService = SolanaTokenService
