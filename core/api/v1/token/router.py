"""Token API module."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy import select
from uuid import uuid4

from core.database import get_db
from core.dependencies import get_current_user
from core.services.token import TokenService
from core.services.analytics import AnalyticsService
from core.models.user import UserInDB
from core.models.token import (
    TokenBalanceResponse,
    WalletConnectRequest,
    TransactionHistoryResponse,
    TokenPricingResponse,
    TokenAnalytics,
    TokenReward,
    TokenUsageStats,
    TokenTransferRequest,
    TokenBurnRequest,
    TokenMintRequest,
    TokenStakeRequest,
    TokenBalance
)
from core.models.token_transaction import TransactionResponse
from core.dependencies import get_analytics_service

router = APIRouter(tags=["token"])

@router.get("/balance", response_model=TokenBalanceResponse)
async def get_balance(
    db: AsyncSession = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
):
    """Get token balance for current user"""
    token_service = TokenService(db)
    balance_decimal = await token_service.get_balance(current_user.id)
    
    # Get the TokenBalance record for additional information
    result = await db.execute(
        select(TokenBalance).where(TokenBalance.user_id == current_user.id)
    )
    token_balance = result.scalar_one_or_none()
    
    # If we don't have a token balance record, create a response with defaults
    if token_balance is None:
        return TokenBalanceResponse(
            id=uuid4(),
            user_id=current_user.id,
            balance=float(balance_decimal),
            last_updated=datetime.utcnow(),
            data={"source": "calculated"}
        )
    
    # Return the properly formatted response
    return TokenBalanceResponse(
        id=token_balance.id,
        user_id=current_user.id,
        balance=float(balance_decimal),
        last_updated=token_balance.updated_at,
        data={"source": "database"}
    )

@router.post("/connect-wallet")
async def connect_wallet(
    request: WalletConnectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
):
    """Connect wallet to user account"""
    token_service = TokenService(db)
    return await token_service.connect_wallet(current_user.id, request.wallet_address)

@router.get("/transactions", response_model=List[TransactionResponse])
async def get_transactions(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    transaction_type: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
):
    """Get transaction history for current user with filtering and pagination"""
    token_service = TokenService(db)
    
    # Fetch transactions
    transactions = await token_service.get_transactions(
        user_id=current_user.id,
        start_date=start_date,
        end_date=end_date,
        transaction_type=transaction_type,
        status=status,
        page=page,
        page_size=page_size
    )
    
    # Convert response for compatibility
    # Map TokenTransactionType to TransactionType accepted by the response model
    response_transactions = []
    for tx in transactions:
        # Map transaction types for compatibility
        tx_type = tx.type
        # Convert 'credit' to 'reward' if needed
        if tx_type == 'credit':
            tx_type = 'reward'
        
        # Create a compatible transaction response
        response_tx = {
            "id": tx.id,
            "user_id": tx.user_id,
            "type": tx_type,
            "amount": float(tx.amount),
            "status": tx.status,
            "tx_hash": tx.tx_hash,
            "created_at": tx.created_at,
            "balance_before": 0.0,  # Default values since we might not have these in the original model
            "balance_after": 0.0, 
            "details": tx.meta_data,
            "signature": None,
            "updated_at": tx.updated_at,
            "completed_at": tx.completed_at
        }
        
        # If there's balance history related to this transaction, use those values
        if hasattr(tx, 'balance_history') and tx.balance_history:
            history = tx.balance_history[0] if len(tx.balance_history) > 0 else None
            if history:
                response_tx["balance_before"] = float(history.balance_before)
                response_tx["balance_after"] = float(history.balance_after)
        
        response_transactions.append(response_tx)
    
    return response_transactions

@router.get("/pricing", response_model=List[TokenPricingResponse])
async def get_token_pricing(
    service_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get token pricing information"""
    token_service = TokenService(db)
    return await token_service.get_pricing_info(service_type)

@router.get("/analytics", response_model=TokenAnalytics)
async def get_token_analytics(
    time_range: Optional[str] = Query(
        "30d",
        description="Time range for analytics (7d, 30d, 90d, all)"
    ),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Get token analytics for current user"""
    try:
        # Convert time range to datetime
        now = datetime.utcnow()
        ranges = {
            "7d": now - timedelta(days=7),
            "30d": now - timedelta(days=30),
            "90d": now - timedelta(days=90),
            "all": None
        }
        start_date = ranges.get(time_range)
        
        analytics = await analytics_service.get_token_analytics(
            user_id=current_user.id,
            start_date=start_date
        )
        return analytics
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/rewards", response_model=List[TokenReward])
async def get_token_rewards(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    reward_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
):
    """Get token rewards history"""
    token_service = TokenService(db)
    return await token_service.get_rewards(
        user_id=current_user.id,
        start_date=start_date,
        end_date=end_date,
        reward_type=reward_type,
        page=page,
        page_size=page_size
    )

@router.get("/usage", response_model=TokenUsageStats)
async def get_token_usage(
    time_range: Optional[str] = Query(
        "30d",
        description="Time range for usage stats (7d, 30d, 90d, all)"
    ),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Get token usage statistics"""
    try:
        # Convert time range to datetime
        now = datetime.utcnow()
        ranges = {
            "7d": now - timedelta(days=7),
            "30d": now - timedelta(days=30),
            "90d": now - timedelta(days=90),
            "all": None
        }
        start_date = ranges.get(time_range)
        
        usage_stats = await analytics_service.get_token_usage_stats(
            user_id=current_user.id,
            start_date=start_date
        )
        return usage_stats
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/transfer")
async def transfer_tokens(
    request: TokenTransferRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
):
    """Transfer tokens to another user"""
    try:
        token_service = TokenService(db)
        result = await token_service.transfer_tokens(
            from_user_id=current_user.id,
            to_user_id=request.to_user_id,
            amount=request.amount,
            memo=request.memo
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/burn")
async def burn_tokens(
    request: TokenBurnRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
):
    """Burn tokens from user's balance"""
    try:
        token_service = TokenService(db)
        result = await token_service.burn_tokens(
            user_id=current_user.id,
            amount=request.amount,
            reason=request.reason
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/mint")
async def mint_tokens(
    request: TokenMintRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
):
    """Mint new tokens (admin only)"""
    try:
        token_service = TokenService(db)
        result = await token_service.mint_tokens(
            to_user_id=request.to_user_id,
            amount=request.amount,
            reason=request.reason,
            admin_id=current_user.id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/stake")
async def stake_tokens(
    request: TokenStakeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
):
    """Stake tokens for rewards"""
    try:
        token_service = TokenService(db)
        result = await token_service.stake_tokens(
            user_id=current_user.id,
            amount=request.amount,
            duration=request.duration
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/stake/info")
async def get_stake_info(
    db: AsyncSession = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
):
    """Get staking information for current user"""
    try:
        token_service = TokenService(db)
        stake_info = await token_service.get_stake_info(current_user.id)
        return stake_info
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/unstake")
async def unstake_tokens(
    stake_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
):
    """Unstake tokens and claim rewards"""
    try:
        token_service = TokenService(db)
        result = await token_service.unstake_tokens(
            user_id=current_user.id,
            stake_id=stake_id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) 