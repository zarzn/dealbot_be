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
        transaction_type: str,
        amount: float,
        status: Optional[str] = None,
        meta_data: Optional[Dict[str, Any]] = None
    ) -> TokenTransaction:
        """Create a new transaction.
        
        Args:
            user_id: The ID of the user creating the transaction
            transaction_type: The type of transaction (e.g. payment, refund)
            amount: The transaction amount
            status: The transaction status (defaults to PENDING)
            meta_data: Optional additional transaction data
            
        Returns:
            The created transaction record
            
        Raises:
            DatabaseError: If there is an error creating the transaction
        """
        try:
            # Set default status if not provided
            if not status:
                status = TransactionStatus.PENDING.value
                
            transaction = TokenTransaction(
                user_id=user_id,
                type=transaction_type,
                amount=amount,
                status=status,
                meta_data=meta_data,
                created_at=datetime.now(timezone.utc)
            )
            
            self.session.add(transaction)
            await self.session.commit()
            await self.session.refresh(transaction)
            
            return transaction
            
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Error creating transaction: {str(e)}")
            raise DatabaseError(
                operation="create_transaction",
                message=f"Failed to create transaction: {str(e)}"
            )

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
            The user's balance record or None if not found
            
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

    async def add_reward(
        self,
        user_id: str,
        amount: float,
        reason: str
    ) -> TokenTransaction:
        """Add reward tokens to user's balance.
        
        Args:
            user_id: The ID of the user
            amount: The reward amount
            reason: The reason for the reward
            
        Returns:
            The created transaction record
            
        Raises:
            DatabaseError: If there is an error processing the reward
        """
        try:
            # Create transaction record
            transaction = TokenTransaction(
                user_id=user_id,
                type=TransactionType.REWARD.value,
                amount=amount,
                status=TransactionStatus.PENDING.value,
                meta_data={"reason": reason}
            )
            self.session.add(transaction)

            # Get or create user balance
            balance = await self.get_user_balance(user_id)
            if not balance:
                balance = TokenBalance(user_id=user_id, balance=0)
                self.session.add(balance)

            # Update balance
            old_balance = balance.balance
            balance.balance += amount

            # Record balance history
            history = TokenBalanceHistory(
                user_id=user_id,
                token_balance_id=balance.id,
                balance_before=old_balance,
                balance_after=balance.balance,
                change_amount=amount,
                change_type=TransactionType.REWARD.value,
                reason=reason,
                transaction_id=transaction.id
            )
            self.session.add(history)

            # Commit changes
            await self.session.commit()
            await self.session.refresh(transaction)
            
            return transaction

        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Error adding reward: {str(e)}")
            raise DatabaseError(
                operation="add_reward",
                message=f"Failed to add reward: {str(e)}"
            )

    async def transfer_tokens(
        self,
        from_user_id: str,
        to_user_id: str,
        amount: float,
        reason: str
    ) -> TokenTransaction:
        """Transfer tokens between users.
        
        Args:
            from_user_id: Source user ID
            to_user_id: Destination user ID
            amount: Amount to transfer
            reason: Reason for transfer
            
        Returns:
            The created transaction record
            
        Raises:
            InsufficientBalanceError: If source has insufficient balance
            DatabaseError: If there is an error processing the transfer
        """
        try:
            # Get source user balance
            from_balance = await self.get_user_balance(from_user_id)
            if not from_balance or from_balance.balance < amount:
                raise InsufficientBalanceError(
                    required=amount,
                    available=from_balance.balance if from_balance else 0
                )
                
            # Get or create destination user balance
            to_balance = await self.get_user_balance(to_user_id)
            if not to_balance:
                to_balance = TokenBalance(
                    user_id=to_user_id, 
                    balance=0
                )
                self.session.add(to_balance)
                # Flush the session to generate IDs for the new balance
                await self.session.flush()
                logger.debug(f"Created new balance for user {to_user_id} with ID {to_balance.id}")
                
            # Create transaction record with UUIDs converted to strings in meta_data
            transaction = TokenTransaction(
                user_id=from_user_id,
                type=TransactionType.CREDIT.value,
                amount=amount,
                status=TransactionStatus.PENDING.value,
                meta_data={
                    "reason": reason,
                    "to_user_id": str(to_user_id)  # Convert UUID to string
                }
            )
            self.session.add(transaction)
            # Flush to generate ID for the transaction
            await self.session.flush()
            logger.debug(f"Created transaction with ID {transaction.id}")
            
            # Update source balance
            old_from_balance = from_balance.balance
            from_balance.balance -= amount
            
            # Record source balance history - ensure from_balance.id is set
            from_history = TokenBalanceHistory(
                user_id=from_user_id,
                token_balance_id=from_balance.id,
                balance_before=old_from_balance,
                balance_after=from_balance.balance,
                change_amount=-amount,
                change_type=TransactionType.DEDUCTION.value,
                reason=f"Transfer to {to_user_id}: {reason}",
                transaction_id=transaction.id
            )
            self.session.add(from_history)
            
            # Update destination balance
            old_to_balance = to_balance.balance
            to_balance.balance += amount
            
            # Record destination balance history - ensure to_balance.id is set
            to_history = TokenBalanceHistory(
                user_id=to_user_id,
                token_balance_id=to_balance.id,
                balance_before=old_to_balance,
                balance_after=to_balance.balance,
                change_amount=amount,
                change_type=TransactionType.CREDIT.value,
                reason=f"Transfer from {from_user_id}: {reason}",
                transaction_id=transaction.id
            )
            self.session.add(to_history)
            
            # Update transaction status
            transaction.status = TransactionStatus.COMPLETED.value
            transaction.processed_at = datetime.now(timezone.utc)
            
            # Commit changes
            await self.session.commit()
            await self.session.refresh(transaction)
            
            return transaction
            
        except InsufficientBalanceError:
            await self.session.rollback()
            raise
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Error transferring tokens: {str(e)}")
            raise DatabaseError(
                operation="transfer_tokens",
                message=f"Failed to transfer tokens: {str(e)}"
            )
            
    async def deduct_tokens(
        self,
        user_id: str,
        amount: float,
        reason: str
    ) -> TokenTransaction:
        """Deduct tokens from user's balance.
        
        Args:
            user_id: User ID
            amount: Amount to deduct
            reason: Reason for deduction
            
        Returns:
            The created transaction record
            
        Raises:
            InsufficientBalanceError: If user has insufficient balance
            DatabaseError: If there is an error processing the deduction
        """
        try:
            # Get user balance
            balance = await self.get_user_balance(user_id)
            if not balance or balance.balance < amount:
                raise InsufficientBalanceError(
                    required=amount,
                    available=balance.balance if balance else 0
                )
                
            # Create transaction record
            transaction = TokenTransaction(
                user_id=user_id,
                type=TransactionType.DEDUCTION.value,
                amount=amount,
                status=TransactionStatus.PENDING.value,
                meta_data={"reason": reason}
            )
            self.session.add(transaction)
            
            # Update balance
            old_balance = balance.balance
            balance.balance -= amount
            balance.last_updated = datetime.now(timezone.utc)
            
            # Record balance history
            history = TokenBalanceHistory(
                user_id=user_id,
                token_balance_id=balance.id,
                balance_before=old_balance,
                balance_after=balance.balance,
                change_amount=-amount,
                change_type=TransactionType.DEDUCTION.value,
                reason=reason,
                transaction_id=transaction.id
            )
            self.session.add(history)
            
            # Update transaction status
            transaction.status = TransactionStatus.COMPLETED.value
            transaction.processed_at = datetime.now(timezone.utc)
            
            # Commit changes
            await self.session.commit()
            await self.session.refresh(transaction)
            
            return transaction
            
        except InsufficientBalanceError:
            await self.session.rollback()
            raise
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Error deducting tokens: {str(e)}")
            raise DatabaseError(
                operation="deduct_tokens",
                message=f"Failed to deduct tokens: {str(e)}"
            )
            
    async def get_transaction_history(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[TokenTransaction]:
        """Get user's transaction history.
        
        Args:
            user_id: User ID
            limit: Maximum number of transactions to return
            offset: Offset for pagination
            
        Returns:
            List of transaction records
            
        Raises:
            DatabaseError: If there is an error retrieving the history
        """
        try:
            result = await self.session.execute(
                select(TokenTransaction)
                .where(TokenTransaction.user_id == user_id)
                .order_by(desc(TokenTransaction.created_at))
                .offset(offset)
                .limit(limit)
            )
            return list(result.scalars().all())
            
        except SQLAlchemyError as e:
            logger.error(f"Error getting transaction history: {str(e)}")
            raise DatabaseError(
                operation="get_transaction_history",
                message=f"Failed to get transaction history: {str(e)}"
            )

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

    async def get_pricing_by_service(self, service_type: str) -> Optional[TokenPricing]:
        """Get token pricing for a specific service type.
        
        Args:
            service_type: The type of service to get pricing for
            
        Returns:
            The pricing record if found, None otherwise
            
        Raises:
            DatabaseError: If there is an error retrieving pricing info
        """
        try:
            now = datetime.now(timezone.utc)
            async with self.session.begin() as session:
                stmt = select(TokenPricing).where(
                    and_(
                        TokenPricing.service_type == service_type,
                        TokenPricing.is_active.is_(True),
                        TokenPricing.valid_from <= now,
                        or_(
                            TokenPricing.valid_to.is_(None),
                            TokenPricing.valid_to >= now
                        )
                    )
                ).order_by(desc(TokenPricing.valid_from))
                
                result = await session.execute(stmt)
                return result.scalar_one_or_none()
            
        except SQLAlchemyError as e:
            logger.error(f"Error getting pricing info for service {service_type}: {str(e)}")
            raise DatabaseError(f"Failed to get pricing info: {str(e)}")

    async def clean_up_transactions(self, cutoff_date: datetime) -> int:
        """Clean up transactions older than a specified date.
        
        Args:
            cutoff_date: The date to use as the cutoff for cleaning up transactions
            
        Returns:
            The number of transactions cleaned up
            
        Raises:
            DatabaseError: If there is an error cleaning up transactions
        """
        try:
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

    async def connect_wallet(
        self,
        user_id: str,
        wallet_address: str
    ) -> bool:
        """Connect a wallet to a user.
        
        Args:
            user_id: The ID of the user
            wallet_address: The wallet address to connect
            
        Returns:
            True if successful
            
        Raises:
            DatabaseError: If there is an error connecting the wallet
        """
        try:
            # Check if wallet already exists
            result = await self.session.execute(
                select(TokenWallet).where(
                    TokenWallet.address == wallet_address
                )
            )
            existing_wallet = result.scalar_one_or_none()
            
            if existing_wallet:
                if existing_wallet.user_id != user_id:
                    raise WalletConnectionError(
                        address=wallet_address,
                        reason="Wallet already connected to another user"
                    )
                # Wallet already belongs to this user
                return True
                
            # Create new wallet
            wallet = TokenWallet(
                user_id=user_id,
                address=wallet_address,
                is_active=True,
                connected_at=datetime.now(timezone.utc)
            )
            
            self.session.add(wallet)
            await self.session.commit()
            
            return True
            
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Error connecting wallet: {str(e)}")
            raise DatabaseError(f"Failed to connect wallet: {str(e)}")

    async def disconnect_wallet(
        self,
        user_id: str
    ) -> bool:
        """Disconnect all wallets for a user.
        
        Args:
            user_id: The ID of the user
            
        Returns:
            True if successful
            
        Raises:
            DatabaseError: If there is an error disconnecting the wallets
        """
        try:
            # Update all user's wallets to inactive
            await self.session.execute(
                update(TokenWallet)
                .where(TokenWallet.user_id == user_id)
                .values(
                    is_active=False,
                    disconnected_at=datetime.now(timezone.utc)
                )
            )
            
            await self.session.commit()
            return True
            
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Error disconnecting wallets: {str(e)}")
            raise DatabaseError(
                operation="disconnect_wallet",
                message=f"Failed to disconnect wallets: {str(e)}"
            )
    
    async def rollback_transaction(
        self,
        tx_id: str
    ) -> bool:
        """Rollback a transaction.
        
        Args:
            tx_id: Transaction ID to rollback
            
        Returns:
            True if successful
            
        Raises:
            DatabaseError: If there is an error rolling back the transaction
        """
        try:
            # Get the transaction
            result = await self.session.execute(
                select(TokenTransaction).where(
                    TokenTransaction.id == tx_id
                )
            )
            transaction = result.scalar_one_or_none()
            
            if not transaction:
                logger.warning(f"Transaction not found for rollback: {tx_id}")
                return False
                
            # Only completed or pending transactions can be rolled back
            if transaction.status not in [
                TransactionStatus.COMPLETED.value,
                TransactionStatus.PENDING.value
            ]:
                logger.warning(
                    f"Transaction {tx_id} in status {transaction.status} cannot be rolled back"
                )
                return False
                
            # Reverse the transaction
            if transaction.type == TransactionType.DEDUCTION.value:
                # For deductions, add the amount back
                await self.update_user_balance(transaction.user_id, transaction.amount)
            elif transaction.type in [
                TransactionType.REWARD.value,
                TransactionType.CREDIT.value,
                TransactionType.REFUND.value
            ]:
                # For additions, subtract the amount
                await self.update_user_balance(transaction.user_id, -transaction.amount)
                
            # Update transaction status
            transaction.status = TransactionStatus.ROLLED_BACK.value
            transaction.processed_at = datetime.now(timezone.utc)
            
            # Add rollback reason to metadata
            if not transaction.meta_data:
                transaction.meta_data = {}
            transaction.meta_data["rollback_reason"] = "Manual rollback"
            transaction.meta_data["rollback_time"] = datetime.now(timezone.utc).isoformat()
            
            await self.session.commit()
            return True
            
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Error rolling back transaction: {str(e)}")
            raise DatabaseError(
                operation="rollback_transaction",
                message=f"Failed to rollback transaction: {str(e)}"
            )
