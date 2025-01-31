from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.models.token import (
    TransactionCreate,
    TransactionResponse,
    TokenPriceResponse,
    TokenBalanceResponse,
    TokenWalletCreate,
    TokenWalletResponse
)
from ....core.services.token_service import TokenService
from ....core.database import get_session
from ....core.auth import get_current_user
from ....core.models.user import User
from ....core.utils.metrics import MetricsCollector
from ....core.utils.logger import get_logger

router = APIRouter(prefix="/tokens", tags=["tokens"])
logger = get_logger(__name__)

@router.post("/transactions", response_model=TransactionResponse)
async def create_transaction(
    transaction: TransactionCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Create a new token transaction"""
    try:
        token_service = TokenService(session)
        result = await token_service.create_transaction(
            user_id=current_user.id,
            transaction_type=transaction.type,
            amount=transaction.amount,
            data=transaction.data
        )
        return result
    except Exception as e:
        logger.error(f"Error creating transaction: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/transactions/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get transaction by ID"""
    try:
        token_service = TokenService(session)
        transaction = await token_service.get_transaction(transaction_id)
        
        if not transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")
            
        if transaction.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to view this transaction")
            
        return transaction
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting transaction: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/transactions", response_model=List[TransactionResponse])
async def get_user_transactions(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get user's transactions"""
    try:
        token_service = TokenService(session)
        transactions = await token_service.get_user_transactions(
            user_id=current_user.id,
            limit=limit,
            offset=offset
        )
        return transactions
    except Exception as e:
        logger.error(f"Error getting user transactions: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/balance", response_model=TokenBalanceResponse)
async def get_balance(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Get user's token balance"""
    try:
        token_service = TokenService(session)
        balance = await token_service.get_user_balance(current_user.id)
        return balance
    except Exception as e:
        logger.error(f"Error getting balance: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/wallets", response_model=TokenWalletResponse)
async def connect_wallet(
    wallet: TokenWalletCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Connect wallet to user account"""
    try:
        token_service = TokenService(session)
        result = await token_service.connect_wallet(
            user_id=current_user.id,
            address=wallet.address
        )
        return result
    except Exception as e:
        logger.error(f"Error connecting wallet: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/wallets/{wallet_id}")
async def disconnect_wallet(
    wallet_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Disconnect wallet from user account"""
    try:
        token_service = TokenService(session)
        await token_service.disconnect_wallet(
            user_id=current_user.id,
            wallet_id=wallet_id
        )
        return {"status": "success", "message": "Wallet disconnected successfully"}
    except Exception as e:
        logger.error(f"Error disconnecting wallet: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/price", response_model=TokenPriceResponse)
async def get_token_price(
    session: AsyncSession = Depends(get_session)
):
    """Get current token price"""
    try:
        token_service = TokenService(session)
        price = await token_service.get_token_price()
        return {
            "price": price,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting token price: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/payments", response_model=TransactionResponse)
async def process_payment(
    amount: float = Query(..., gt=0),
    reason: str = Query(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Process token payment"""
    try:
        token_service = TokenService(session)
        transaction = await token_service.process_payment(
            user_id=current_user.id,
            amount=amount,
            reason=reason
        )
        return transaction
    except Exception as e:
        logger.error(f"Error processing payment: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/refunds", response_model=TransactionResponse)
async def process_refund(
    amount: float = Query(..., gt=0),
    reason: str = Query(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Process token refund"""
    try:
        token_service = TokenService(session)
        transaction = await token_service.process_refund(
            user_id=current_user.id,
            amount=amount,
            reason=reason
        )
        return transaction
    except Exception as e:
        logger.error(f"Error processing refund: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/price/history")
async def get_price_history(
    days: int = Query(30, ge=1, le=365),
    interval: str = Query("1h", regex="^(1h|4h|1d|1w)$"),
    session: AsyncSession = Depends(get_session)
):
    """Get token price history"""
    try:
        token_service = TokenService(session)
        history = await token_service.get_price_history(
            days=days,
            interval=interval
        )
        return history
    except Exception as e:
        logger.error(f"Error getting price history: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/verify-balance")
async def verify_balance(
    amount: float = Query(..., gt=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Verify user has sufficient balance"""
    try:
        token_service = TokenService(session)
        has_balance = await token_service.verify_balance(
            user_id=current_user.id,
            required_amount=amount
        )
        return {
            "has_sufficient_balance": has_balance,
            "required_amount": amount
        }
    except Exception as e:
        logger.error(f"Error verifying balance: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e)) 