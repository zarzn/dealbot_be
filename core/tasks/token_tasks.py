from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import asyncio
from celery import shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.models.token import TokenTransaction, TokenPrice
from core.models.user import User
from core.utils.logger import get_logger
from core.utils.metrics import track_token_transaction
from core.utils.redis import RedisClient
from core.exceptions.token_exceptions import TokenError
from core.exceptions.base_exceptions import BaseException
from core.config import settings

logger = get_logger(__name__)

@shared_task(
    name="update_token_prices",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    rate_limit="4/m"
)
def update_token_prices(self) -> Dict[str, Any]:
    """Update token prices from external sources"""
    try:
        # Run async task
        return asyncio.run(_update_token_prices_async())
    except BaseException as e:
        logger.error(f"Error updating token prices: {str(e)}")
        self.retry(exc=e)

async def _update_token_prices_async() -> Dict[str, Any]:
    """Async implementation of token price update"""
    db_to_close = None
    try:
        session = await get_db()
        db_to_close = session

        # Get token price from external source
        current_price = await _get_token_price_from_source()
        
        # Create price record
        price_record = TokenPrice(
            price=current_price,
            timestamp=datetime.utcnow()
        )
        
        session.add(price_record)
        await session.commit()
        await session.refresh(price_record)
        
        # Update cache
        cache = RedisClient("token_price")
        await cache.set(
            "current_price",
            {
                "price": current_price,
                "timestamp": price_record.timestamp.isoformat()
            },
            expire=settings.TOKEN_CACHE_TTL
        )
        
        # Track metric
        track_token_transaction(
            transaction_type="price_update",
            status="success"
        )
        
        return {
            "status": "success",
            "message": "Token price updated successfully",
            "price": current_price,
            "timestamp": price_record.timestamp.isoformat()
        }
        
    except BaseException as e:
        if session:
            await session.rollback()
        logger.error(f"Error in token price update task: {str(e)}")
        
        # Track metric
        track_token_transaction(
            transaction_type="price_update",
            status="error"
        )
        
        raise TokenError(f"Failed to update token price: {str(e)}")
    finally:
        if db_to_close:
            await db_to_close.close()

async def _get_token_price_from_source() -> float:
    """Get token price from external source"""
    # This is a placeholder - implement your price fetching logic
    # You should integrate with your chosen price oracle or API
    return 1.0

@shared_task(
    name="process_token_transaction",
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def process_token_transaction(
    self,
    transaction_id: str
) -> Dict[str, Any]:
    """Process token transaction"""
    try:
        # Run async task
        return asyncio.run(_process_token_transaction_async(transaction_id))
    except BaseException as e:
        logger.error(f"Error processing token transaction: {str(e)}")
        self.retry(exc=e)

async def _process_token_transaction_async(
    transaction_id: str,
    session: Optional[AsyncSession] = None
) -> Dict[str, Any]:
    """Async implementation of token transaction processing"""
    db_to_close = None
    try:
        if session is None:
            db_to_close = await get_db()
            session = db_to_close

        # Get transaction
        result = await session.execute(
            select(TokenTransaction).where(
                TokenTransaction.id == transaction_id
            )
        )
        transaction = result.scalar_one_or_none()
        
        if not transaction:
            raise TokenError(f"Transaction {transaction_id} not found")
        
        # Process transaction based on type
        if transaction.type == "payment":
            await _process_payment_transaction(transaction, session)
        elif transaction.type == "refund":
            await _process_refund_transaction(transaction, session)
        
        # Update transaction status
        transaction.processed_at = datetime.utcnow()
        transaction.status = "completed"
        
        await session.commit()
        await session.refresh(transaction)
        
        # Track metric
        track_token_transaction(
            transaction_type=transaction.type,
            status="success"
        )
        
        return {
            "status": "success",
            "message": "Transaction processed successfully",
            "transaction_id": transaction_id,
            "processed_at": transaction.processed_at.isoformat()
        }
        
    except BaseException as e:
        if session:
            await session.rollback()
        logger.error(f"Error processing transaction {transaction_id}: {str(e)}")
        
        if transaction:
            transaction.status = "failed"
            transaction.error = str(e)
            await session.commit()
        
        # Track metric
        track_token_transaction(
            transaction_type=transaction.type if transaction else "unknown",
            status="error"
        )
        
        raise TokenError(f"Failed to process transaction: {str(e)}")
    finally:
        if db_to_close:
            await db_to_close.close()

async def _process_payment_transaction(
    transaction: TokenTransaction,
    session: AsyncSession
) -> None:
    """Process payment transaction"""
    try:
        # Verify user has sufficient balance
        if not await _verify_user_balance(
            transaction.user_id,
            transaction.amount,
            session
        ):
            raise TokenError("Insufficient balance")
        
        # Deduct tokens from user's balance
        await _update_user_balance(
            transaction.user_id,
            -transaction.amount,
            session
        )
        
    except BaseException as e:
        logger.error(f"Error processing payment: {str(e)}")
        raise TokenError(f"Payment processing failed: {str(e)}")

async def _process_refund_transaction(
    transaction: TokenTransaction,
    session: AsyncSession
) -> None:
    """Process refund transaction"""
    try:
        # Add tokens to user's balance
        await _update_user_balance(
            transaction.user_id,
            transaction.amount,
            session
        )
        
    except BaseException as e:
        logger.error(f"Error processing refund: {str(e)}")
        raise TokenError(f"Refund processing failed: {str(e)}")

async def _verify_user_balance(
    user_id: str,
    amount: float,
    session: Optional[AsyncSession] = None
) -> bool:
    """Verify user has sufficient balance"""
    db_to_close = None
    try:
        if session is None:
            db_to_close = await get_db()
            session = db_to_close

        # Get user's current balance
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise TokenError(f"User {user_id} not found")
        
        return user.token_balance >= amount
            
    except BaseException as e:
        logger.error(f"Error verifying user balance: {str(e)}")
        raise TokenError(f"Balance verification failed: {str(e)}")
    finally:
        if db_to_close:
            await db_to_close.close()

async def _update_user_balance(
    user_id: str,
    amount: float,
    session: AsyncSession
) -> None:
    """Update user's token balance"""
    try:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise TokenError(f"User {user_id} not found")
        
        user.token_balance += amount
        
        if user.token_balance < 0:
            raise TokenError("Balance cannot be negative")
        
    except BaseException as e:
        logger.error(f"Error updating user balance: {str(e)}")
        raise TokenError(f"Balance update failed: {str(e)}")

@shared_task(
    name="cleanup_old_transactions",
    bind=True,
    max_retries=3,
    default_retry_delay=300
)
def cleanup_old_transactions(
    self,
    days: int = 30
) -> Dict[str, Any]:
    """Clean up old token transactions"""
    try:
        # Run async task
        return asyncio.run(_cleanup_old_transactions_async(days))
    except BaseException as e:
        logger.error(f"Error cleaning up transactions: {str(e)}")
        self.retry(exc=e)

async def _cleanup_old_transactions_async(
    days: int,
    session: Optional[AsyncSession] = None
) -> Dict[str, Any]:
    """Async implementation of transaction cleanup"""
    db_to_close = None
    try:
        if session is None:
            db_to_close = await get_db()
            session = db_to_close

        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Get old transactions
        result = await session.execute(
            select(TokenTransaction).where(
                TokenTransaction.created_at < cutoff_date,
                TokenTransaction.status.in_(["completed", "failed"])
            )
        )
        transactions = list(result.scalars().all())
        
        if not transactions:
            return {
                "status": "success",
                "message": "No old transactions to clean up",
                "deleted": 0
            }
        
        # Delete transactions
        for transaction in transactions:
            await session.delete(transaction)
        
        await session.commit()
        
        return {
            "status": "success",
            "message": "Old transactions cleaned up successfully",
            "deleted": len(transactions)
        }
        
    except BaseException as e:
        if session:
            await session.rollback()
        logger.error(f"Error in transaction cleanup task: {str(e)}")
        raise TokenError(f"Transaction cleanup failed: {str(e)}")
    finally:
        if db_to_close:
            await db_to_close.close()
