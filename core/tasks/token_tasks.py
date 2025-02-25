"""Token processing tasks."""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import asyncio
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from core.config import get_settings
from core.models.token import TokenTransaction, TokenPrice, TokenBalanceHistory
from core.models.user import User
from core.utils.logger import get_logger
from core.utils.metrics import MetricsCollector
from core.utils.redis import RedisClient
from core.exceptions.token_exceptions import TokenError
from core.exceptions.base_exceptions import BaseError
from core.config import settings
from core.celery import celery_app

logger = logging.getLogger(__name__)
metrics = MetricsCollector()

# Create synchronous engine and session factory
settings = get_settings()
engine = create_engine(str(settings.sync_database_url))
SessionLocal = sessionmaker(bind=engine)

def get_db() -> Session:
    """Get synchronous database session."""
    db = SessionLocal()
    try:
        return db
    except Exception as e:
        db.close()
        raise e

@celery_app.task(
    name="update_token_balances",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    rate_limit="10/m"
)
def update_token_balances(
    self,
    user_ids: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Update token balances for users."""
    db = get_db()
    try:
        # Build query for users
        query = db.query(User)
        if user_ids:
            query = query.filter(User.id.in_(user_ids))
        
        # Get users to update
        users = query.all()
        
        # Update each user's balance
        results = {
            "successful": [],
            "failed": []
        }
        
        for user in users:
            try:
                # Calculate new balance from transactions
                new_balance = _calculate_user_balance(user.id, db)
                
                # Update user balance
                user.token_balance = new_balance
                
                # Record balance history
                history = TokenBalanceHistory(
                    user_id=user.id,
                    balance_before=user.token_balance,
                    balance_after=new_balance,
                    change_amount=new_balance - user.token_balance,
                    change_type="recalculation",
                    reason="Periodic balance update"
                )
                db.add(history)
                
                results["successful"].append({
                    "user_id": str(user.id),
                    "old_balance": float(user.token_balance),
                    "new_balance": float(new_balance)
                })
                
            except Exception as e:
                logger.error(f"Error updating balance for user {user.id}: {str(e)}")
                results["failed"].append({
                    "user_id": str(user.id),
                    "error": str(e)
                })
        
        db.commit()
        
        # Track metrics
        metrics.track_token_transaction("balance_update", "success")
        if results["failed"]:
            metrics.track_token_transaction("balance_update", "failed")
        
        return {
            "status": "completed",
            "message": "Balance updates completed",
            "results": results
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error in balance update task: {str(e)}")
        self.retry(exc=e)
    finally:
        db.close()

def _calculate_user_balance(
    user_id: str,
    session: Session
) -> float:
    """Calculate user's token balance from transactions"""
    try:
        # Get all completed transactions for user
        transactions = session.query(TokenTransaction).filter(
            TokenTransaction.user_id == user_id,
            TokenTransaction.status == "completed"
        ).all()
        
        # Calculate balance
        balance = 0.0
        for tx in transactions:
            if tx.type == "credit":
                balance += tx.amount
            elif tx.type == "debit":
                balance -= tx.amount
        
        return balance
        
    except Exception as e:
        logger.error(f"Error calculating balance for user {user_id}: {str(e)}")
        raise TokenError(f"Balance calculation failed: {str(e)}")

@celery_app.task(
    name="update_token_prices",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    rate_limit="4/m"
)
def update_token_prices(self) -> Dict[str, Any]:
    """Update token prices from external sources"""
    db = get_db()
    try:
        # Get token price from external source
        current_price = _get_token_price_from_source()
        
        # Create price record
        price_record = TokenPrice(
            price=current_price,
            timestamp=datetime.utcnow()
        )
        
        db.add(price_record)
        db.commit()
        db.refresh(price_record)
        
        # Update cache
        cache = RedisClient()
        cache.set(
            "current_price",
            {
                "price": current_price,
                "timestamp": price_record.timestamp.isoformat()
            },
            expire=settings.TOKEN_CACHE_TTL
        )
        
        # Track metric
        metrics.track_token_transaction("price_update", "success")
        
        return {
            "status": "success",
            "message": "Token price updated successfully",
            "price": current_price,
            "timestamp": price_record.timestamp.isoformat()
        }
        
    except BaseError as e:
        db.rollback()
        logger.error(f"Error in token price update task: {str(e)}")
        metrics.track_token_transaction("price_update", "error")
        self.retry(exc=e)
    finally:
        db.close()

def _get_token_price_from_source() -> float:
    """Get token price from external source."""
    # TODO: Implement external price source integration
    return 1.0  # Default price for testing

@celery_app.task(
    name="process_token_transactions",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    rate_limit="10/m"
)
def process_token_transactions(
    self,
    transaction_id: str
) -> Dict[str, Any]:
    """Process token transaction"""
    db = get_db()
    try:
        # Get transaction
        transaction = db.query(TokenTransaction).get(transaction_id)
        if not transaction:
            raise TokenError(f"Transaction {transaction_id} not found")
            
        # Process based on type
        if transaction.type == "payment":
            _process_payment_transaction(transaction, db)
        elif transaction.type == "refund":
            _process_refund_transaction(transaction, db)
            
        db.commit()
        
        metrics.track_token_transaction(transaction.type, "success")
        
        return {
            "status": "success",
            "message": "Transaction processed successfully",
            "transaction_id": transaction_id
        }
            
    except BaseError as e:
        db.rollback()
        logger.error(f"Error processing token transaction: {str(e)}")
        metrics.track_token_transaction("transaction", "error")
        self.retry(exc=e)
    finally:
        db.close()

def _process_payment_transaction(
    transaction: TokenTransaction,
    session: Session
) -> None:
    """Process payment transaction"""
    try:
        # Verify balance
        if not _verify_user_balance(transaction.user_id, transaction.amount, session):
            raise TokenError("Insufficient balance")
            
        # Update balance
        _update_user_balance(transaction.user_id, -transaction.amount, session)
        
        # Update transaction status
        transaction.status = "completed"
        transaction.completed_at = datetime.utcnow()
        
    except Exception as e:
        raise TokenError(f"Payment processing failed: {str(e)}")

def _process_refund_transaction(
    transaction: TokenTransaction,
    session: Session
) -> None:
    """Process refund transaction"""
    try:
        # Update balance
        _update_user_balance(transaction.user_id, transaction.amount, session)
        
        # Update transaction status
        transaction.status = "completed"
        transaction.completed_at = datetime.utcnow()
        
    except Exception as e:
        raise TokenError(f"Refund processing failed: {str(e)}")

def _verify_user_balance(
    user_id: str,
    amount: float,
    session: Session
) -> bool:
    """Verify user has sufficient balance"""
    try:
        user = session.query(User).get(user_id)
        if not user:
            raise TokenError(f"User {user_id} not found")
            
        return user.token_balance >= amount
        
    except Exception as e:
        raise TokenError(f"Balance verification failed: {str(e)}")

def _update_user_balance(
    user_id: str,
    amount: float,
    session: Session
) -> None:
    """Update user's token balance"""
    try:
        user = session.query(User).get(user_id)
        if not user:
            raise TokenError(f"User {user_id} not found")
            
        user.token_balance += amount
        
        # Record balance history
        history = TokenBalanceHistory(
            user_id=user_id,
            balance_before=user.token_balance - amount,
            balance_after=user.token_balance,
            change_amount=amount,
            change_type="transaction",
            reason="Token transaction"
        )
        session.add(history)
        
    except Exception as e:
        raise TokenError(f"Balance update failed: {str(e)}")

@celery_app.task(
    name="cleanup_old_transactions",
    bind=True,
    max_retries=3,
    default_retry_delay=300
)
def cleanup_old_transactions(
    self,
    days: int = 30
) -> Dict[str, Any]:
    """Clean up old transactions"""
    db = get_db()
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Get old transactions
        transactions = db.query(TokenTransaction).filter(
            TokenTransaction.created_at < cutoff_date,
            TokenTransaction.status.in_(["completed", "failed"])
        ).all()
        
        if not transactions:
            return {
                "status": "success",
                "message": "No old transactions to clean up",
                "deleted": 0
            }
            
        # Archive transactions
        for tx in transactions:
            tx.is_archived = True
            tx.archived_at = datetime.utcnow()
            
        db.commit()
        
        return {
            "status": "success",
            "message": "Old transactions cleaned up successfully",
            "archived": len(transactions)
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error cleaning up transactions: {str(e)}")
        self.retry(exc=e)
    finally:
        db.close()
