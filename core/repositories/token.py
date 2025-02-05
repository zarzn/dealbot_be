"""Token repository implementation for managing token transactions and balances.

This module provides a comprehensive interface for handling all token-related
database operations including transactions, balances, pricing, and wallet management.
"""

"""Token repository implementation for managing token transactions and balances.

This module provides a comprehensive interface for handling all token-related
database operations including transactions, balances, pricing, and wallet management.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, or_, desc, func
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import SQLAlchemyError

from core.models.token import (
    TokenTransaction,
    TokenPrice,
    TokenBalance,
    TokenWallet,
    TransactionType,
    TransactionStatus
)
from core.models.token_balance_history import TokenBalanceHistory
from core.models.token_pricing import TokenPricing
from core.models.user import User
from core.exceptions import (
    InsufficientBalanceError,
    WalletConnectionError,
    TokenNetworkError,
    TokenOperationError,
    DatabaseError,
    RepositoryError
)
from core.utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class PricingQuery:
    """Query parameters for token pricing."""
    service_type: str
    active_only: bool = True

class TokenRepository:
    """Repository for token-related database operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_transaction(
        self,
        user_id: str,
        transaction_type: TransactionType,
        amount: float,
        data: Optional[Dict[str, Any]] = None
    ) -> TokenTransaction:
        """Create a new transaction.
        
        Args:
            user_id: The ID of the user creating the transaction
            transaction_type: The type of transaction (e.g. payment, refund)
            amount: The transaction amount
            data: Optional additional transaction data
            
        Returns:
            The created transaction record
            
        Raises:
            DatabaseError: If there is an error creating the transaction
        """
        try:
            transaction = TokenTransaction(
                user_id=user_id,
                type=transaction_type,
                amount=amount,
                status=TransactionStatus.PENDING,
                data=data,
                created_at=datetime.now(timezone.utc)
            )
            
            self.session.add(transaction)
            await self.session.commit()
            await self.session.refresh(transaction)
            
            return transaction
            
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Error creating transaction: {str(e)}")
            raise DatabaseError(f"Failed to create transaction: {str(e)}")

    async def get_transaction(
        self,
        transaction_id: str
    ) -> Optional[TokenTransaction]:
        """Get transaction by ID.
        
        Args:
            transaction_id: The ID of the transaction to retrieve
            
        Returns:
            The transaction record if found, None otherwise
            
        Raises:
            DatabaseError: If there is an error retrieving the transaction
        """
        try:
            result = await self.session.execute(
                select(TokenTransaction)
                .where(TokenTransaction.id == transaction_id)
                .options(selectinload(TokenTransaction.user))
            )
            return result.scalar_one_or_none()
            
        except SQLAlchemyError as e:
            logger.error(f"Error getting transaction: {str(e)}")
            raise DatabaseError(f"Failed to get transaction: {str(e)}")

    async def get_user_transactions(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        transaction_type: Optional[TransactionType] = None,
        status: Optional[TransactionStatus] = None
    ) -> List[TokenTransaction]:
        """Get user's transactions.
        
        Args:
            user_id: The ID of the user
            limit: Maximum number of transactions to return
            offset: Number of transactions to skip
            transaction_type: Optional filter by transaction type
            status: Optional filter by transaction status
            
        Returns:
            List of transaction records
            
        Raises:
            DatabaseError: If there is an error retrieving transactions
        """
        try:
            query = select(TokenTransaction).where(
                TokenTransaction.user_id == user_id
            )
            
            if transaction_type:
                query = query.where(TokenTransaction.type == transaction_type)
                
            if status:
                query = query.where(TokenTransaction.status == status)
                
            query = query.order_by(desc(TokenTransaction.created_at))
            query = query.offset(offset).limit(limit)
            
            result = await self.session.execute(query)
            return list(result.scalars().all())
            
        except SQLAlchemyError as e:
            logger.error(f"Error getting user transactions: {str(e)}")
            raise DatabaseError(f"Failed to get user transactions: {str(e)}")

    async def update_transaction_status(
        self,
        transaction_id: str,
        status: TransactionStatus,
        error: Optional[str] = None
    ) -> TokenTransaction:
        """Update transaction status.
        
        Args:
            transaction_id: The ID of the transaction to update
            status: The new transaction status
            error: Optional error message if the transaction failed
            
        Returns:
            The updated transaction record
            
        Raises:
            DatabaseError: If there is an error updating the transaction
        """
        try:
            result = await self.session.execute(
                select(TokenTransaction).where(
                    TokenTransaction.id == transaction_id
                )
            )
            transaction = result.scalar_one_or_none()
            
            if not transaction:
                raise DatabaseError(f"Transaction {transaction_id} not found")
            
            transaction.status = status
            transaction.error = error
            transaction.processed_at = datetime.now(timezone.utc)
            
            await self.session.commit()
            await self.session.refresh(transaction)
            
            return transaction
            
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Error updating transaction status: {str(e)}")
            raise DatabaseError(f"Failed to update transaction status: {str(e)}")

    async def get_user_balance(
        self,
        user_id: str
    ) -> Optional[TokenBalance]:
        """Get user's token balance.
        
        Args:
            user_id: The ID of the user
            
        Returns:
            The user's balance record if found, None otherwise
            
        Raises:
            DatabaseError: If there is an error retrieving the balance
        """
        try:
            result = await self.session.execute(
                select(TokenBalance).where(
                    TokenBalance.user_id == user_id
                )
            )
            return result.scalar_one_or_none()
            
        except SQLAlchemyError as e:
            logger.error(f"Error getting user balance: {str(e)}")
            raise DatabaseError(f"Failed to get user balance: {str(e)}")

    async def update_user_balance(
        self,
        user_id: str,
        amount: float
    ) -> TokenBalance:
        """Update user's token balance.
        
        Args:
            user_id: The ID of the user
            amount: The amount to add/subtract from balance
            
        Returns:
            The updated balance record
            
        Raises:
            DatabaseError: If there is an error updating the balance
            InsufficientBalanceError: If the resulting balance would be negative
        """
        try:
            result = await self.session.execute(
                select(TokenBalance).where(
                    TokenBalance.user_id == user_id
                )
            )
            balance = result.scalar_one_or_none()
            
            if not balance:
                balance = TokenBalance(
                    user_id=user_id,
                    balance=amount,
                    last_updated=datetime.now(timezone.utc)
                )
                self.session.add(balance)
            else:
                new_balance = balance.balance + amount
                if new_balance < 0:
                    raise InsufficientBalanceError("Insufficient balance for operation")
                balance.balance = new_balance
                balance.last_updated = datetime.now(timezone.utc)
            
            await self.session.commit()
            await self.session.refresh(balance)
            
            return balance
            
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Error updating user balance: {str(e)}")
            raise DatabaseError(f"Failed to update user balance: {str(e)}")

    async def create_wallet(
        self,
        user_id: str,
        address: str,
        data: Optional[Dict[str, Any]] = None
    ) -> TokenWallet:
        """Create a new wallet.
        
        Args:
            user_id: The ID of the user
            address: The wallet address
            data: Optional additional wallet data
            
        Returns:
            The created wallet record
            
        Raises:
            DatabaseError: If there is an error creating the wallet
        """
        try:
            wallet = TokenWallet(
                user_id=user_id,
                address=address,
                data=data,
                created_at=datetime.now(timezone.utc)
            )
            
            self.session.add(wallet)
            await self.session.commit()
            await self.session.refresh(wallet)
            
            return wallet
            
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Error creating wallet: {str(e)}")
            raise DatabaseError(f"Failed to create wallet: {str(e)}")

    async def get_wallet(
        self,
        wallet_id: str
    ) -> Optional[TokenWallet]:
        """Get wallet by ID.
        
        Args:
            wallet_id: The ID of the wallet to retrieve
            
        Returns:
            The wallet record if found, None otherwise
            
        Raises:
            DatabaseError: If there is an error retrieving the wallet
        """
        try:
            result = await self.session.execute(
                select(TokenWallet)
                .where(TokenWallet.id == wallet_id)
                .options(selectinload(TokenWallet.user))
            )
            return result.scalar_one_or_none()
            
        except SQLAlchemyError as e:
            logger.error(f"Error getting wallet: {str(e)}")
            raise DatabaseError(f"Failed to get wallet: {str(e)}")

    async def get_wallet_by_address(
        self,
        address: str
    ) -> Optional[TokenWallet]:
        """Get wallet by address.
        
        Args:
            address: The wallet address to look up
            
        Returns:
            The wallet record if found, None otherwise
            
        Raises:
            DatabaseError: If there is an error retrieving the wallet
        """
        try:
            result = await self.session.execute(
                select(TokenWallet)
                .where(TokenWallet.address == address)
                .options(selectinload(TokenWallet.user))
            )
            return result.scalar_one_or_none()
            
        except SQLAlchemyError as e:
            logger.error(f"Error getting wallet by address: {str(e)}")
            raise DatabaseError(f"Failed to get wallet by address: {str(e)}")

    async def get_user_wallets(
        self,
        user_id: str,
        active_only: bool = True
    ) -> List[TokenWallet]:
        """Get user's wallets.
        
        Args:
            user_id: The ID of the user
            active_only: Whether to return only active wallets
            
        Returns:
            List of wallet records
            
        Raises:
            DatabaseError: If there is an error retrieving wallets
        """
        try:
            query = select(TokenWallet).where(
                TokenWallet.user_id == user_id
            )
            
            if active_only:
                query = query.where(TokenWallet.is_active == True)
                
            result = await self.session.execute(query)
            return list(result.scalars().all())
            
        except SQLAlchemyError as e:
            logger.error(f"Error getting user wallets: {str(e)}")
            raise DatabaseError(f"Failed to get user wallets: {str(e)}")

    async def update_wallet_status(
        self,
        wallet_id: str,
        is_active: bool
    ) -> TokenWallet:
        """Update wallet status.
        
        Args:
            wallet_id: The ID of the wallet to update
            is_active: The new active status
            
        Returns:
            The updated wallet record
            
        Raises:
            DatabaseError: If there is an error updating the wallet
        """
        try:
            result = await self.session.execute(
                select(TokenWallet).where(
                    TokenWallet.id == wallet_id
                )
            )
            wallet = result.scalar_one_or_none()
            
            if not wallet:
                raise DatabaseError(f"Wallet {wallet_id} not found")
            
            wallet.is_active = is_active
            wallet.last_used = datetime.now(timezone.utc)
            
            await self.session.commit()
            await self.session.refresh(wallet)
            
            return wallet
            
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Error updating wallet status: {str(e)}")
            raise DatabaseError(f"Failed to update wallet status: {str(e)}")

    async def get_pricing_info(self, query: PricingQuery) -> Optional[TokenPricing]:
        """Get token pricing information for a specific service type.
        
        Args:
            query: The pricing query parameters
            
        Returns:
            The pricing record if found, None otherwise
            
        Raises:
            DatabaseError: If there is an error retrieving pricing info
        """
        try:
            stmt = select(TokenPricing).where(
                TokenPricing.service_type == query.service_type
            )
            if query.active_only:
                stmt = stmt.where(TokenPricing.is_active.is_(True))
                
            result = await self.session.execute(
                stmt.order_by(TokenPricing.valid_from.desc())
            )
            return result.scalar_one_or_none()
            
        except SQLAlchemyError as e:
            logger.error(f"Error getting pricing info: {str(e)}")
            raise DatabaseError(f"Failed to get pricing info: {str(e)}")

    async def cleanup_old_transactions(
        self,
        days: int = 30
    ) -> int:
        """Clean up old transactions.
        
        Args:
            days: Number of days of history to keep
            
        Returns:
            Number of transactions cleaned up
            
        Raises:
            DatabaseError: If there is an error cleaning up transactions
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            result = await self.session.execute(
                select(TokenTransaction).where(
                    and_(
                        TokenTransaction.created_at < cutoff_date,
                        TokenTransaction.status.in_([
                            TransactionStatus.COMPLETED,
                            TransactionStatus.FAILED
                        ])
                    )
                )
            )
            transactions = list(result.scalars().all())
            
            for transaction in transactions:
                await self.session.delete(transaction)
            
            await self.session.commit()
            
            return len(transactions)
            
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Error cleaning up transactions: {str(e)}")
            raise DatabaseError(f"Failed to clean up transactions: {str(e)}")
