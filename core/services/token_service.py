"""Token service module.

This module provides token-related services for the AI Agentic Deals System,
including transaction management, balance tracking, and wallet operations.
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
import uuid
from decimal import Decimal
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment
from solana.transaction import Transaction
from solana.system_program import TransactionInstruction
from spl.token.instructions import get_associated_token_account
from base58 import b58decode, b58encode

from backend.core.models.token import (
    TokenTransaction,
    TokenPrice,
    TokenBalance,
    TokenWallet,
    TransactionType,
    TransactionStatus,
    TokenBalanceHistory
)
from backend.core.models.user import User
from backend.core.utils.logger import get_logger
from backend.core.utils.metrics import MetricsCollector
from backend.core.utils.redis import RedisCache
from backend.core.utils.validation import TokenValidator
from backend.core.exceptions import (
    TokenError,
    InsufficientTokensError,
    SolanaError,
    SolanaTransactionError,
    SolanaConnectionError
)
from backend.core.config import settings
from backend.core.tasks.token_tasks import process_token_transaction

logger = get_logger(__name__)

class TokenService:
    """Token service for handling Solana token operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.cache = RedisCache("token")
        self.solana_client = AsyncClient(
            settings.SOL_NETWORK_RPC,
            commitment=Commitment(settings.COMMITMENT_LEVEL)
        )

    async def create_transaction(
        self,
        user_id: str,
        transaction_type: TransactionType,
        amount: float,
        data: Optional[Dict[str, Any]] = None
    ) -> TokenTransaction:
        """Create a new token transaction with Solana integration.
        
        Args:
            user_id: User identifier
            transaction_type: Type of transaction
            amount: Token amount
            data: Additional transaction data
            
        Returns:
            Created transaction record
            
        Raises:
            TokenError: If transaction creation fails
            InsufficientTokensError: If user has insufficient balance
        """
        try:
            # Validate transaction data
            TokenValidator.validate_token_data({
                "user_id": user_id,
                "amount": amount,
                "type": transaction_type
            })

            # Check balance for deductions
            if transaction_type == TransactionType.DEDUCTION:
                balance = await self.get_user_balance(user_id)
                if balance.balance < amount:
                    raise InsufficientTokensError(
                        required=amount,
                        available=balance.balance
                    )

            # Create transaction record
            transaction = TokenTransaction(
                id=str(uuid.uuid4()),
                user_id=user_id,
                type=transaction_type,
                amount=Decimal(str(amount)),
                status=TransactionStatus.PENDING,
                data=data,
                created_at=datetime.utcnow(),
                network=settings.SOL_NETWORK
            )

            self.session.add(transaction)
            await self.session.commit()
            await self.session.refresh(transaction)

            # Track metric
            MetricsCollector.track_token_transaction(
                transaction_type=transaction_type,
                status="created",
                amount=amount
            )

            # Trigger async processing
            await process_token_transaction.delay(transaction.id)

            return transaction

        except InsufficientTokensError:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating transaction: {str(e)}", exc_info=True)
            raise TokenError(f"Failed to create transaction: {str(e)}")

    async def get_transaction(
        self,
        transaction_id: str
    ) -> Optional[TokenTransaction]:
        """Get transaction by ID with Solana status check.
        
        Args:
            transaction_id: Transaction identifier
            
        Returns:
            Transaction record if found
            
        Raises:
            TokenError: If retrieval fails
        """
        try:
            # Try cache first
            cached_tx = await self.cache.get(f"tx:{transaction_id}")
            if cached_tx:
                return TokenTransaction(**cached_tx)

            # Get from database
            result = await self.session.execute(
                select(TokenTransaction).where(
                    TokenTransaction.id == transaction_id
                )
            )
            transaction = result.scalar_one_or_none()

            if transaction:
                # Check Solana transaction status if signature exists
                if transaction.signature:
                    try:
                        status = await self.solana_client.get_signature_statuses(
                            [transaction.signature]
                        )
                        if status.value[0]:
                            transaction.confirmations = status.value[0].confirmations
                            await self.session.commit()
                    except Exception as e:
                        logger.warning(
                            f"Failed to check Solana status: {str(e)}",
                            exc_info=True
                        )

                # Cache transaction
                await self.cache.set(
                    f"tx:{transaction_id}",
                    transaction.model_dump(),
                    expire=settings.TOKEN_CACHE_TTL
                )

            return transaction

        except Exception as e:
            logger.error(f"Error getting transaction: {str(e)}", exc_info=True)
            raise TokenError(f"Failed to get transaction: {str(e)}")

    async def get_user_transactions(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        status: Optional[TransactionStatus] = None,
        transaction_type: Optional[TransactionType] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Tuple[List[TokenTransaction], int]:
        """Get user's transactions with filtering and pagination.
        
        Args:
            user_id: User identifier
            limit: Maximum number of records
            offset: Pagination offset
            status: Filter by transaction status
            transaction_type: Filter by transaction type
            start_date: Filter by start date
            end_date: Filter by end date
            
        Returns:
            Tuple of (transactions list, total count)
            
        Raises:
            TokenError: If retrieval fails
        """
        try:
            # Build query
            query = select(TokenTransaction).where(
                TokenTransaction.user_id == user_id
            )

            # Apply filters
            if status:
                query = query.where(TokenTransaction.status == status)
            if transaction_type:
                query = query.where(TokenTransaction.type == transaction_type)
            if start_date:
                query = query.where(TokenTransaction.created_at >= start_date)
            if end_date:
                query = query.where(TokenTransaction.created_at <= end_date)

            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total = await self.session.scalar(count_query)

            # Get paginated results
            result = await self.session.execute(
                query.order_by(TokenTransaction.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            transactions = list(result.scalars().all())

            return transactions, total

        except Exception as e:
            logger.error(f"Error getting user transactions: {str(e)}", exc_info=True)
            raise TokenError(f"Failed to get user transactions: {str(e)}")

    async def get_user_balance(
        self,
        user_id: str,
        force_refresh: bool = False
    ) -> TokenBalance:
        """Get user's token balance with Solana balance check.
        
        Args:
            user_id: User identifier
            force_refresh: Force Solana balance refresh
            
        Returns:
            User's token balance
            
        Raises:
            TokenError: If balance retrieval fails
        """
        try:
            # Try cache first if not forcing refresh
            if not force_refresh:
                cached_balance = await self.cache.get(f"balance:{user_id}")
                if cached_balance:
                    return TokenBalance(**cached_balance)

            # Get from database
            result = await self.session.execute(
                select(TokenBalance).where(
                    TokenBalance.user_id == user_id
                )
            )
            balance = result.scalar_one_or_none()

            if not balance:
                # Create new balance record
                balance = TokenBalance(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    balance=Decimal('0'),
                    last_updated=datetime.utcnow()
                )
                self.session.add(balance)
                await self.session.commit()
                await self.session.refresh(balance)

            # Check Solana balance if wallet connected
            wallet = await self.get_user_wallet(user_id)
            if wallet:
                try:
                    token_account = await get_associated_token_account(
                        wallet.address,
                        settings.TOKEN_CONTRACT_ADDRESS
                    )
                    response = await self.solana_client.get_token_account_balance(
                        token_account
                    )
                    if response.value:
                        on_chain_balance = Decimal(response.value.amount) / Decimal(
                            10 ** settings.TOKEN_DECIMALS
                        )
                        if on_chain_balance != balance.balance:
                            logger.warning(
                                f"Balance mismatch for user {user_id}: "
                                f"DB={balance.balance}, Chain={on_chain_balance}"
                            )
                            # Update balance if chain shows less
                            if on_chain_balance < balance.balance:
                                balance.balance = on_chain_balance
                                balance.last_updated = datetime.utcnow()
                                await self.session.commit()
                                await self.session.refresh(balance)
                except Exception as e:
                    logger.error(
                        f"Failed to check Solana balance: {str(e)}",
                        exc_info=True
                    )

            # Cache balance
            await self.cache.set(
                f"balance:{user_id}",
                balance.model_dump(),
                expire=settings.TOKEN_CACHE_TTL
            )

            return balance

        except Exception as e:
            logger.error(f"Error getting user balance: {str(e)}", exc_info=True)
            raise TokenError(f"Failed to get user balance: {str(e)}")

    async def update_user_balance(
        self,
        user_id: str,
        amount: float,
        reason: str,
        reference_id: Optional[str] = None
    ) -> TokenBalance:
        """Update user's token balance with transaction tracking.
        
        Args:
            user_id: User identifier
            amount: Amount to add/subtract
            reason: Reason for update
            reference_id: Optional reference ID
            
        Returns:
            Updated balance record
            
        Raises:
            TokenError: If update fails
            InsufficientTokensError: If resulting balance would be negative
        """
        try:
            balance = await self.get_user_balance(user_id)
            
            # Validate resulting balance
            new_balance = balance.balance + Decimal(str(amount))
            if new_balance < 0:
                raise InsufficientTokensError(
                    required=abs(amount),
                    available=float(balance.balance)
                )
            
            # Update balance
            balance.balance = new_balance
            balance.last_updated = datetime.utcnow()
            
            await self.session.commit()
            await self.session.refresh(balance)
            
            # Update cache
            await self.cache.set(
                f"balance:{user_id}",
                balance.model_dump(),
                expire=settings.TOKEN_CACHE_TTL
            )
            
            # Create balance history record
            history = TokenBalanceHistory(
                id=str(uuid.uuid4()),
                user_id=user_id,
                amount=Decimal(str(amount)),
                balance_before=balance.balance - Decimal(str(amount)),
                balance_after=balance.balance,
                reason=reason,
                reference_id=reference_id,
                created_at=datetime.utcnow()
            )
            self.session.add(history)
            await self.session.commit()
            
            # Track metric
            MetricsCollector.track_balance_update(
                amount=amount,
                reason=reason
            )
            
            return balance
            
        except InsufficientTokensError:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating user balance: {str(e)}", exc_info=True)
            raise TokenError(f"Failed to update balance: {str(e)}")

    async def connect_wallet(
        self,
        user_id: str,
        address: str
    ) -> TokenWallet:
        """Connect Solana wallet to user account.
        
        Args:
            user_id: User identifier
            address: Solana wallet address
            
        Returns:
            Connected wallet record
            
        Raises:
            TokenError: If connection fails
            ValueError: If address is invalid
        """
        try:
            # Validate Solana address
            try:
                b58decode(address)
                if len(address) < 32 or len(address) > 44:
                    raise ValueError("Invalid address length")
            except Exception as e:
                raise ValueError(f"Invalid Solana address: {str(e)}")

            # Check if wallet already exists
            result = await self.session.execute(
                select(TokenWallet).where(
                    or_(
                        TokenWallet.address == address,
                        and_(
                            TokenWallet.user_id == user_id,
                            TokenWallet.is_active == True
                        )
                    )
                )
            )
            existing_wallet = result.scalar_one_or_none()
            
            if existing_wallet:
                if existing_wallet.address == address:
                    raise TokenError("Wallet already connected to an account")
                else:
                    raise TokenError("User already has an active wallet")

            # Verify address on Solana
            try:
                response = await self.solana_client.get_account_info(address)
                if not response.value:
                    raise ValueError("Address not found on Solana")
            except Exception as e:
                raise SolanaError(
                    operation="verify_address",
                    message=f"Failed to verify address: {str(e)}"
                )

            # Create wallet record
            wallet = TokenWallet(
                id=str(uuid.uuid4()),
                user_id=user_id,
                address=address,
                network=settings.SOL_NETWORK,
                is_active=True,
                created_at=datetime.utcnow()
            )
            
            self.session.add(wallet)
            await self.session.commit()
            await self.session.refresh(wallet)
            
            # Track metric
            MetricsCollector.track_wallet_connection(
                network=settings.SOL_NETWORK
            )
            
            return wallet
            
        except (ValueError, SolanaError) as e:
            await self.session.rollback()
            raise
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error connecting wallet: {str(e)}", exc_info=True)
            raise TokenError(f"Failed to connect wallet: {str(e)}")

    async def disconnect_wallet(
        self,
        user_id: str,
        wallet_id: str
    ) -> None:
        """Disconnect wallet from user account.
        
        Args:
            user_id: User identifier
            wallet_id: Wallet identifier
            
        Raises:
            TokenError: If disconnection fails
        """
        try:
            result = await self.session.execute(
                select(TokenWallet).where(
                    TokenWallet.id == wallet_id,
                    TokenWallet.user_id == user_id,
                    TokenWallet.is_active == True
                )
            )
            wallet = result.scalar_one_or_none()
            
            if not wallet:
                raise TokenError("Wallet not found or already disconnected")
            
            # Deactivate wallet
            wallet.is_active = False
            wallet.disconnected_at = datetime.utcnow()
            
            await self.session.commit()
            
            # Track metric
            MetricsCollector.track_wallet_disconnection(
                network=settings.SOL_NETWORK
            )
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error disconnecting wallet: {str(e)}", exc_info=True)
            raise TokenError(f"Failed to disconnect wallet: {str(e)}")

    async def get_user_wallet(
        self,
        user_id: str
    ) -> Optional[TokenWallet]:
        """Get user's active wallet.
        
        Args:
            user_id: User identifier
            
        Returns:
            Active wallet record if found
            
        Raises:
            TokenError: If retrieval fails
        """
        try:
            result = await self.session.execute(
                select(TokenWallet).where(
                    TokenWallet.user_id == user_id,
                    TokenWallet.is_active == True
                )
            )
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Error getting user wallet: {str(e)}", exc_info=True)
            raise TokenError(f"Failed to get user wallet: {str(e)}")

    async def check_connection(self) -> bool:
        """Check Solana connection health.
        
        Returns:
            True if connection is healthy
            
        Raises:
            SolanaConnectionError: If connection check fails
        """
        try:
            response = await self.solana_client.get_health()
            return response.value == "ok"
        except Exception as e:
            logger.error(f"Solana connection check failed: {str(e)}", exc_info=True)
            raise SolanaConnectionError(
                endpoint=settings.SOL_NETWORK_RPC,
                message=f"Connection check failed: {str(e)}"
            )

    async def get_token_price(self) -> float:
        """Get current token price"""
        try:
            # Try to get from cache first
            cached_price = await self.cache.get("current_price")
            if cached_price:
                return cached_price["price"]

            # Get latest price from database
            result = await self.session.execute(
                select(TokenPrice)
                .order_by(TokenPrice.timestamp.desc())
                .limit(1)
            )
            price_record = result.scalar_one_or_none()
            
            if not price_record:
                raise TokenError("Token price not available")
            
            # Cache price
            await self.cache.set(
                "current_price",
                {
                    "price": price_record.price,
                    "timestamp": price_record.timestamp.isoformat()
                },
                expire=settings.TOKEN_CACHE_TTL
            )
            
            return price_record.price
            
        except Exception as e:
            logger.error(f"Error getting token price: {str(e)}")
            raise TokenError(f"Failed to get token price: {str(e)}")

    async def verify_balance(
        self,
        user_id: str,
        required_amount: float
    ) -> bool:
        """Verify user has sufficient balance"""
        try:
            balance = await self.get_user_balance(user_id)
            return balance.balance >= required_amount
            
        except Exception as e:
            logger.error(f"Error verifying balance: {str(e)}")
            raise TokenError(f"Failed to verify balance: {str(e)}")

    async def process_payment(
        self,
        user_id: str,
        amount: float,
        reason: str
    ) -> TokenTransaction:
        """Process token payment"""
        try:
            # Verify balance
            if not await self.verify_balance(user_id, amount):
                raise TokenError("Insufficient balance")

            # Create transaction
            transaction = await self.create_transaction(
                user_id=user_id,
                transaction_type=TransactionType.PAYMENT,
                amount=amount,
                data={"reason": reason}
            )

            return transaction
            
        except Exception as e:
            logger.error(f"Error processing payment: {str(e)}")
            raise TokenError(f"Failed to process payment: {str(e)}")

    async def process_refund(
        self,
        user_id: str,
        amount: float,
        reason: str
    ) -> TokenTransaction:
        """Process token refund"""
        try:
            # Create transaction
            transaction = await self.create_transaction(
                user_id=user_id,
                transaction_type=TransactionType.REFUND,
                amount=amount,
                data={"reason": reason}
            )

            return transaction
            
        except Exception as e:
            logger.error(f"Error processing refund: {str(e)}")
            raise TokenError(f"Failed to process refund: {str(e)}")

    async def get_price_history(
        self,
        days: int = 30,
        interval: str = "1h"
    ) -> List[Dict[str, Any]]:
        """Get token price history"""
        try:
            result = await self.session.execute(
                select(TokenPrice)
                .where(
                    TokenPrice.timestamp >= datetime.utcnow() - timedelta(days=days)
                )
                .order_by(TokenPrice.timestamp.asc())
            )
            prices = list(result.scalars().all())
            
            return [
                {
                    "price": price.price,
                    "timestamp": price.timestamp.isoformat(),
                    "source": price.source
                }
                for price in prices
            ]
            
        except Exception as e:
            logger.error(f"Error getting price history: {str(e)}")
            raise TokenError(f"Failed to get price history: {str(e)}") 