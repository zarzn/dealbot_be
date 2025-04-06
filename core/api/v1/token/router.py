"""Token API module."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from uuid import uuid4
import logging

from core.database import get_db, get_session, get_async_db_context
from core.dependencies import get_current_user, get_token_service
from core.services.token_service import TokenServiceV2, TokenService
from core.services.analytics import AnalyticsService
from core.models.user import UserInDB
from core.models.token import (
    TokenBalanceResponse,
    WalletConnectRequest,
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
from core.models.token_transaction import TransactionResponse, TransactionHistoryResponse
from core.dependencies import get_analytics_service

router = APIRouter(tags=["token"])
logger = logging.getLogger(__name__)

# Create a dependency that uses the context manager approach
async def get_db_session():
    """Get database session using the new context manager pattern.
    
    This provides better connection management and prevents connection leaks.
    """
    async with get_async_db_context() as session:
        yield session

@router.get("/balance", response_model=TokenBalanceResponse)
async def get_balance(
    db: AsyncSession = Depends(get_db_session),
    token_service: TokenService = Depends(get_token_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Get token balance for current user"""
    try:
        # Get the user's ID as string
        user_id_str = str(current_user.id)
        
        # Get balance using injected token service
        balance_decimal = await token_service.get_balance(user_id_str)
        logger.info(f"Retrieved balance using TokenService: {balance_decimal}")
        
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
    except Exception as e:
        logger.error(f"Error getting balance: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting balance: {str(e)}"
        )

@router.post("/connect-wallet")
async def connect_wallet(
    request: WalletConnectRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: UserInDB = Depends(get_current_user)
):
    """Connect wallet to user account"""
    try:
        # Update user's wallet address in database
        # This is a placeholder - the real implementation would be more complex
        from core.models.user import User
        
        # Find user in database
        result = await db.execute(
            select(User).where(User.id == current_user.id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Update wallet address
        user.wallet_address = request.wallet_address
        await db.commit()
        
        return {"message": "Wallet connected successfully", "wallet_address": request.wallet_address}
    except Exception as e:
        logger.error(f"Error connecting wallet: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error connecting wallet: {str(e)}"
        )

@router.get("/transaction-history", response_model=TransactionHistoryResponse)
async def get_transaction_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
    token_service: TokenService = Depends(get_token_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Get transaction history for current user"""
    try:
        # Get transaction history using injected token service
        transactions = await token_service.get_transaction_history(
            str(current_user.id),
            limit=limit,
            offset=offset
        )
        
        # Convert to response format
        transaction_responses = []
        for tx in transactions:
            # Extract balance_before and balance_after from related TokenBalanceHistory if available
            balance_before = None
            balance_after = None
            
            if tx.balance_history and len(tx.balance_history) > 0:
                balance_history = tx.balance_history[0]
                balance_before = float(balance_history.balance_before) if balance_history.balance_before else 0.0
                balance_after = float(balance_history.balance_after) if balance_history.balance_after else 0.0
            
            transaction_responses.append(
                TransactionResponse(
                    id=tx.id,
                    user_id=tx.user_id,
                    amount=float(tx.amount),
                    type=tx.type,
                    status=tx.status,
                    created_at=tx.created_at,
                    updated_at=tx.updated_at,
                    completed_at=tx.completed_at,
                    balance_before=balance_before or 0.0,
                    balance_after=balance_after or 0.0,
                    details=tx.meta_data or {},
                    signature=tx.tx_hash
                )
            )
        
        # Get total count (for pagination)
        from sqlalchemy import func, select, text
        from core.models.token_transaction import TokenTransaction
        count_result = await db.execute(
            select(func.count(TokenTransaction.id)).where(
                TokenTransaction.user_id == current_user.id
            )
        )
        total_count = count_result.scalar_one()
        
        # Calculate total pages
        total_pages = (total_count + limit - 1) // limit if limit > 0 else 1
        current_page = (offset // limit) + 1 if limit > 0 else 1
        
        return TransactionHistoryResponse(
            transactions=transaction_responses,
            total_count=total_count,
            total_pages=total_pages,
            current_page=current_page,
            page_size=limit
        )
    except Exception as e:
        logger.error(f"Error getting transaction history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting transaction history: {str(e)}"
        )

@router.post("/transfer")
async def transfer_tokens(
    request: TokenTransferRequest,
    db: AsyncSession = Depends(get_db_session),
    token_service: TokenService = Depends(get_token_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Transfer tokens to another user"""
    try:
        # First check if sender has sufficient balance
        sender_balance = await token_service.get_balance(str(current_user.id))
        if sender_balance < request.amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Insufficient balance for transfer"
            )
        
        # Process sender transaction (deduction)
        sender_tx = await token_service.process_transaction(
            user_id=str(current_user.id),
            amount=-request.amount,
            transaction_type="transfer_out",
            details={
                "recipient": request.to_user_id,
                "memo": request.memo
            }
        )
        
        # Process recipient transaction (addition)
        recipient_tx = await token_service.process_transaction(
            user_id=request.to_user_id,
            amount=request.amount,
            transaction_type="transfer_in",
            details={
                "sender": str(current_user.id),
                "memo": request.memo
            }
        )
        
        return {
            "message": "Transfer successful",
            "transaction_id": str(sender_tx.id),
            "recipient_transaction_id": str(recipient_tx.id),
            "amount": request.amount,
            "new_balance": float(sender_balance - request.amount)
        }
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error transferring tokens: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error transferring tokens: {str(e)}"
        )

@router.post("/mint")
async def mint_tokens(
    request: TokenMintRequest,
    db: AsyncSession = Depends(get_db_session),
    token_service: TokenService = Depends(get_token_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Mint new tokens (admin only)"""
    try:
        # Check if user is admin
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can mint tokens"
            )
        
        # Process the mint transaction using injected service
        tx = await token_service.process_transaction(
            user_id=request.to_user_id,
            amount=request.amount,
            transaction_type="mint",
            details={
                "admin_id": str(current_user.id),
                "reason": request.reason
            }
        )
        
        # Get updated balance
        new_balance = await token_service.get_balance(request.to_user_id)
        
        return {
            "message": "Tokens minted successfully",
            "transaction_id": str(tx.id),
            "amount": request.amount,
            "to_user_id": request.to_user_id,
            "new_balance": float(new_balance)
        }
    except Exception as e:
        logger.error(f"Error minting tokens: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error minting tokens: {str(e)}"
        )

@router.get("/pricing", response_model=List[TokenPricingResponse])
async def get_token_pricing(
    service_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
    token_service: TokenService = Depends(get_token_service)
):
    """Get token pricing information"""
    try:
        return await token_service.get_pricing_info(service_type)
    except Exception as e:
        logger.error(f"Error getting token pricing: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to get token pricing: {str(e)}")

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
        now = datetime.now(timezone.utc)
        ranges = {
            "7d": now - timedelta(days=7),
            "30d": now - timedelta(days=30),
            "90d": now - timedelta(days=90),
            "all": None
        }
        start_date = ranges.get(time_range)
        
        # Use the injected analytics_service that's properly initialized with dependencies
        analytics = await analytics_service.get_token_analytics(
            user_id=current_user.id,
            start_date=start_date
        )
        return analytics
    except Exception as e:
        logger.error(f"Error in get_token_analytics: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to get token analytics: {str(e)}")

@router.get("/rewards", response_model=List[TokenReward])
async def get_token_rewards(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    reward_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
    token_service: TokenService = Depends(get_token_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Get token rewards history"""
    try:
        return await token_service.get_rewards(
            user_id=current_user.id,
            start_date=start_date,
            end_date=end_date,
            reward_type=reward_type,
            page=page,
            page_size=page_size
        )
    except Exception as e:
        logger.error(f"Error getting token rewards: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to get token rewards: {str(e)}")

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

@router.post("/burn")
async def burn_tokens(
    request: TokenBurnRequest,
    db: AsyncSession = Depends(get_db_session),
    token_service: TokenService = Depends(get_token_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Burn tokens from user's balance"""
    try:
        result = await token_service.burn_tokens(
            user_id=current_user.id,
            amount=request.amount,
            reason=request.reason
        )
        return result
    except Exception as e:
        logger.error(f"Error burning tokens: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to burn tokens: {str(e)}")

@router.post("/stake")
async def stake_tokens(
    request: TokenStakeRequest,
    db: AsyncSession = Depends(get_db_session),
    token_service: TokenService = Depends(get_token_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Stake tokens for rewards"""
    try:
        result = await token_service.stake_tokens(
            user_id=current_user.id,
            amount=request.amount,
            duration=request.duration
        )
        return result
    except Exception as e:
        logger.error(f"Error staking tokens: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to stake tokens: {str(e)}")

@router.get("/stake/info")
async def get_stake_info(
    db: AsyncSession = Depends(get_db_session),
    token_service: TokenService = Depends(get_token_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Get staking information for current user"""
    try:
        stake_info = await token_service.get_stake_info(current_user.id)
        return stake_info
    except Exception as e:
        logger.error(f"Error getting stake info: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to get stake info: {str(e)}")

@router.post("/unstake")
async def unstake_tokens(
    stake_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    token_service: TokenService = Depends(get_token_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Unstake tokens and claim rewards"""
    try:
        result = await token_service.unstake_tokens(
            user_id=current_user.id,
            stake_id=stake_id
        )
        return result
    except Exception as e:
        logger.error(f"Error unstaking tokens: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to unstake tokens: {str(e)}")

@router.get("/test-balance", response_model=Dict[str, Any])
async def test_balance(
    user_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
    token_service: TokenService = Depends(get_token_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Test endpoint to get token balance for current user or specified user (admin only)"""
    logger.info(f"Test balance endpoint called by user {current_user.id}")
    
    try:
        # Use the user ID from the request if provided (admin only) or fall back to current user
        target_user_id = user_id if user_id and current_user.role == "admin" else str(current_user.id)
        
        # Use the injected token service
        balance = await token_service.get_balance(target_user_id)
            
        # Get the database record for additional info
        from core.repositories.token import TokenRepository
        token_repo = TokenRepository(db)
        balance_record = await token_repo.get_user_balance(target_user_id)
        
        return {
            "user_id": target_user_id,
            "balance": float(balance),
            "record_exists": balance_record is not None,
            "record_id": str(balance_record.id) if balance_record else None,
            "updated_at": balance_record.updated_at if balance_record else None
        }
    except Exception as e:
        logger.error(f"Error in test balance endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error testing balance: {str(e)}"
        ) 
