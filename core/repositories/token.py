"""Token repository implementation for managing token transactions and balances"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from backend.core.models import (
    TokenTransaction,
    TokenBalanceHistory,
    TokenPricing,
    User
)
from backend.core.exceptions import (
    RepositoryError,
    InsufficientBalanceError,
    WalletConnectionError,
    NetworkError
)

class ITokenRepository(ABC):
    """Abstract base class defining the token repository interface"""
    
    @abstractmethod
    async def get_user_balance(self, user_id: str) -> Optional[Decimal]:
        """Get user's token balance"""
        raise NotImplementedError
    
    @abstractmethod
    async def create_transaction(
        self,
        user_id: str,
        transaction_type: str,
        amount: Decimal,
        status: str = "pending",
        reason: Optional[str] = None
    ) -> TokenTransaction:
        """Create a new token transaction"""
        raise NotImplementedError
    
    @abstractmethod
    async def create_balance_history(
        self,
        user_id: str,
        balance_before: Decimal,
        balance_after: Decimal,
        change_amount: Decimal,
        change_type: str,
        reason: Optional[str] = None
    ) -> TokenBalanceHistory:
        """Create token balance history record"""
        raise NotImplementedError
    
    @abstractmethod
    async def update_user_balance(
        self,
        user_id: str,
        new_balance: Decimal
    ) -> None:
        """Update user's token balance"""
        raise NotImplementedError
    
    @abstractmethod
    async def get_pricing_info(self, service_type: str) -> Optional[TokenPricing]:
        """Get token pricing information"""
        raise NotImplementedError

class TokenRepository(ITokenRepository):
    """Concrete implementation of token repository using SQLAlchemy"""
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_balance(self, user_id: str) -> Optional[Decimal]:
        """Get user's token balance directly from database"""
        try:
            result = await self.db.execute(
                select(User.token_balance)
                .where(User.id == user_id)
            )
            balance = result.scalar_one_or_none()
            if balance is None:
                raise WalletConnectionError("User wallet not found")
            return balance
        except Exception as e:
            raise NetworkError(f"Failed to get user balance: {str(e)}") from e

    async def create_transaction(
        self,
        user_id: str,
        transaction_type: str,
        amount: Decimal,
        status: str = "pending",
        reason: Optional[str] = None
    ) -> TokenTransaction:
        """Create a new token transaction record"""
        try:
            transaction = TokenTransaction(
                user_id=user_id,
                type=transaction_type,
                amount=amount,
                status=status,
                reason=reason
            )
            self.db.add(transaction)
            await self.db.flush()
            return transaction
        except Exception as e:
            raise RepositoryError(
                f"Failed to create {transaction_type} transaction for user {user_id}: {str(e)}"
            ) from e

    async def create_balance_history(
        self,
        user_id: str,
        balance_before: Decimal,
        balance_after: Decimal,
        change_amount: Decimal,
        change_type: str,
        reason: Optional[str] = None
    ) -> TokenBalanceHistory:
        """Create a new token balance history record"""
        try:
            history = TokenBalanceHistory(
                user_id=user_id,
                balance_before=balance_before,
                balance_after=balance_after,
                change_amount=change_amount,
                change_type=change_type,
                reason=reason
            )
            self.db.add(history)
            await self.db.flush()
            return history
        except Exception as e:
            raise RepositoryError(
                f"Failed to create balance history for user {user_id}: {str(e)}"
            ) from e

    async def update_user_balance(
        self,
        user_id: str,
        new_balance: Decimal
    ) -> None:
        """Update user's token balance"""
        if new_balance < Decimal(0):
            raise InsufficientBalanceError("Balance cannot be negative")
            
        try:
            await self.db.execute(
                update(User)
                .where(User.id == user_id)
                .values(token_balance=new_balance)
            )
            await self.db.flush()
        except Exception as e:
            raise NetworkError(f"Failed to update user balance: {str(e)}") from e

    @dataclass
    class PricingQuery:
        service_type: str
        active_only: bool = True

    async def get_pricing_info(self, query: PricingQuery) -> Optional[TokenPricing]:
        """Get token pricing information for a specific service type."""
        try:
            stmt = select(TokenPricing).where(
                TokenPricing.service_type == query.service_type
            )
            if query.active_only:
                stmt = stmt.where(TokenPricing.is_active == True)  # pylint: disable=singleton-comparison
                
            result = await self.db.execute(
                stmt.order_by(TokenPricing.valid_from.desc())
            )
            return result.scalar_one_or_none()
        except Exception as e:
            raise RepositoryError(f"Failed to get pricing info: {str(e)}") from e

    async def get_transaction_by_hash(self, tx_hash: str) -> Optional[TokenTransaction]:
        """Get transaction by its hash"""
        try:
            result = await self.db.execute(
                select(TokenTransaction)
                .where(TokenTransaction.tx_hash == tx_hash)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            raise RepositoryError(f"Failed to get transaction by hash: {str(e)}") from e

    async def update_transaction_status(
        self,
        transaction_id: str,
        status: str,
        tx_hash: Optional[str] = None
    ) -> None:
        """Update transaction status and optional hash"""
        try:
            await self.db.execute(
                update(TokenTransaction)
                .where(TokenTransaction.id == transaction_id)
                .values(status=status, tx_hash=tx_hash)
            )
            await self.db.flush()
        except Exception as e:
            raise RepositoryError(f"Failed to update transaction status: {str(e)}") from e
