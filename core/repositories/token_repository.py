from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select, and_, or_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.token import (
    TokenTransaction,
    TokenPrice,
    TokenBalance,
    TokenWallet,
    TransactionType,
    TransactionStatus
)
from ..utils.logger import get_logger
from ..exceptions import DatabaseError

logger = get_logger(__name__)

class TokenRepository:
    """Repository for token-related database operations"""
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_transaction(
        self,
        user_id: str,
        transaction_type: TransactionType,
        amount: float,
        data: Optional[Dict[str, Any]] = None
    ) -> TokenTransaction:
        """Create a new transaction"""
        try:
            transaction = TokenTransaction(
                user_id=user_id,
                type=transaction_type,
                amount=amount,
                status=TransactionStatus.PENDING,
                data=data,
                created_at=datetime.utcnow()
            )
            
            self.session.add(transaction)
            await self.session.commit()
            await self.session.refresh(transaction)
            
            return transaction
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating transaction: {str(e)}")
            raise DatabaseError(f"Failed to create transaction: {str(e)}")

    async def get_transaction(
        self,
        transaction_id: str
    ) -> Optional[TokenTransaction]:
        """Get transaction by ID"""
        try:
            result = await self.session.execute(
                select(TokenTransaction)
                .where(TokenTransaction.id == transaction_id)
                .options(selectinload(TokenTransaction.user))
            )
            return result.scalar_one_or_none()
            
        except Exception as e:
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
        """Get user's transactions"""
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
            
        except Exception as e:
            logger.error(f"Error getting user transactions: {str(e)}")
            raise DatabaseError(f"Failed to get user transactions: {str(e)}")

    async def update_transaction_status(
        self,
        transaction_id: str,
        status: TransactionStatus,
        error: Optional[str] = None
    ) -> TokenTransaction:
        """Update transaction status"""
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
            transaction.processed_at = datetime.utcnow()
            
            await self.session.commit()
            await self.session.refresh(transaction)
            
            return transaction
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating transaction status: {str(e)}")
            raise DatabaseError(f"Failed to update transaction status: {str(e)}")

    async def get_user_balance(
        self,
        user_id: str
    ) -> Optional[TokenBalance]:
        """Get user's token balance"""
        try:
            result = await self.session.execute(
                select(TokenBalance).where(
                    TokenBalance.user_id == user_id
                )
            )
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Error getting user balance: {str(e)}")
            raise DatabaseError(f"Failed to get user balance: {str(e)}")

    async def update_user_balance(
        self,
        user_id: str,
        amount: float
    ) -> TokenBalance:
        """Update user's token balance"""
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
                    last_updated=datetime.utcnow()
                )
                self.session.add(balance)
            else:
                balance.balance += amount
                balance.last_updated = datetime.utcnow()
            
            await self.session.commit()
            await self.session.refresh(balance)
            
            return balance
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating user balance: {str(e)}")
            raise DatabaseError(f"Failed to update user balance: {str(e)}")

    async def create_wallet(
        self,
        user_id: str,
        address: str,
        data: Optional[Dict[str, Any]] = None
    ) -> TokenWallet:
        """Create a new wallet"""
        try:
            wallet = TokenWallet(
                user_id=user_id,
                address=address,
                data=data,
                created_at=datetime.utcnow()
            )
            
            self.session.add(wallet)
            await self.session.commit()
            await self.session.refresh(wallet)
            
            return wallet
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating wallet: {str(e)}")
            raise DatabaseError(f"Failed to create wallet: {str(e)}")

    async def get_wallet(
        self,
        wallet_id: str
    ) -> Optional[TokenWallet]:
        """Get wallet by ID"""
        try:
            result = await self.session.execute(
                select(TokenWallet)
                .where(TokenWallet.id == wallet_id)
                .options(selectinload(TokenWallet.user))
            )
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Error getting wallet: {str(e)}")
            raise DatabaseError(f"Failed to get wallet: {str(e)}")

    async def get_wallet_by_address(
        self,
        address: str
    ) -> Optional[TokenWallet]:
        """Get wallet by address"""
        try:
            result = await self.session.execute(
                select(TokenWallet)
                .where(TokenWallet.address == address)
                .options(selectinload(TokenWallet.user))
            )
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Error getting wallet by address: {str(e)}")
            raise DatabaseError(f"Failed to get wallet by address: {str(e)}")

    async def get_user_wallets(
        self,
        user_id: str,
        active_only: bool = True
    ) -> List[TokenWallet]:
        """Get user's wallets"""
        try:
            query = select(TokenWallet).where(
                TokenWallet.user_id == user_id
            )
            
            if active_only:
                query = query.where(TokenWallet.is_active == True)
                
            result = await self.session.execute(query)
            return list(result.scalars().all())
            
        except Exception as e:
            logger.error(f"Error getting user wallets: {str(e)}")
            raise DatabaseError(f"Failed to get user wallets: {str(e)}")

    async def update_wallet_status(
        self,
        wallet_id: str,
        is_active: bool
    ) -> TokenWallet:
        """Update wallet status"""
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
            wallet.last_used = datetime.utcnow()
            
            await self.session.commit()
            await self.session.refresh(wallet)
            
            return wallet
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating wallet status: {str(e)}")
            raise DatabaseError(f"Failed to update wallet status: {str(e)}")

    async def create_price_record(
        self,
        price: float,
        source: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> TokenPrice:
        """Create a new price record"""
        try:
            price_record = TokenPrice(
                price=price,
                source=source,
                data=data,
                timestamp=datetime.utcnow()
            )
            
            self.session.add(price_record)
            await self.session.commit()
            await self.session.refresh(price_record)
            
            return price_record
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating price record: {str(e)}")
            raise DatabaseError(f"Failed to create price record: {str(e)}")

    async def get_latest_price(self) -> Optional[TokenPrice]:
        """Get latest token price"""
        try:
            result = await self.session.execute(
                select(TokenPrice)
                .order_by(desc(TokenPrice.timestamp))
                .limit(1)
            )
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Error getting latest price: {str(e)}")
            raise DatabaseError(f"Failed to get latest price: {str(e)}")

    async def get_price_history(
        self,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        interval: str = "1h"
    ) -> List[TokenPrice]:
        """Get token price history"""
        try:
            query = select(TokenPrice).where(
                TokenPrice.timestamp >= start_time
            )
            
            if end_time:
                query = query.where(TokenPrice.timestamp <= end_time)
                
            # Add interval-based sampling
            if interval == "1h":
                query = query.where(
                    func.date_trunc('hour', TokenPrice.timestamp) == TokenPrice.timestamp
                )
            elif interval == "1d":
                query = query.where(
                    func.date_trunc('day', TokenPrice.timestamp) == TokenPrice.timestamp
                )
                
            query = query.order_by(TokenPrice.timestamp.asc())
            
            result = await self.session.execute(query)
            return list(result.scalars().all())
            
        except Exception as e:
            logger.error(f"Error getting price history: {str(e)}")
            raise DatabaseError(f"Failed to get price history: {str(e)}")

    async def cleanup_old_transactions(
        self,
        days: int = 30
    ) -> int:
        """Clean up old transactions"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
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
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error cleaning up transactions: {str(e)}")
            raise DatabaseError(f"Failed to clean up transactions: {str(e)}")

    async def cleanup_old_prices(
        self,
        days: int = 30
    ) -> int:
        """Clean up old price records"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            result = await self.session.execute(
                select(TokenPrice).where(
                    TokenPrice.timestamp < cutoff_date
                )
            )
            prices = list(result.scalars().all())
            
            for price in prices:
                await self.session.delete(price)
            
            await self.session.commit()
            
            return len(prices)
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error cleaning up prices: {str(e)}")
            raise DatabaseError(f"Failed to clean up prices: {str(e)}") 