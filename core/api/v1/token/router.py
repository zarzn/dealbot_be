"""Token API module."""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Header, Request, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func, text
from uuid import uuid4
import logging
from tenacity import RetryError

from core.database import get_db, get_session, get_async_db_context
from core.dependencies import get_current_user, get_token_service, get_stripe_service
from core.services.token import TokenService
from core.services.stripe_service import StripeService
from core.services.analytics import AnalyticsService
from core.models.user import UserInDB
from core.exceptions import TokenValidationError, TokenError, InsufficientBalanceError, TokenBalanceError, TokenTransactionError
from core.exceptions.wallet_exceptions import WalletConnectionError
from core.exceptions.payment_exceptions import PaymentError, PaymentValidationError
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
    TokenBalance,
    TokenPurchaseRequest,
    TokenPurchaseResponse,
    TokenPurchaseVerifyRequest,
    TokenPurchaseVerifyResponse,
    StripePaymentRequest,
    StripePaymentResponse,
    StripePaymentVerifyRequest
)
from core.models.token_transaction import TransactionResponse, TransactionHistoryResponse
from core.dependencies import get_analytics_service
from core.models.token_wallet import TokenWalletResponse

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
    except TokenBalanceError as e:
        logger.error(f"Token balance error: {str(e)}")
        # Return a default balance of 0 instead of an error
        return TokenBalanceResponse(
            id=uuid4(),
            user_id=current_user.id,
            balance=0.0,
            last_updated=datetime.utcnow(),
            data={"source": "error", "error": str(e.reason)}
        )
    except RetryError as e:
        logger.error(f"Retry error getting balance: {str(e)}")
        # If it's a retry error, return a default balance
        return TokenBalanceResponse(
            id=uuid4(),
            user_id=current_user.id,
            balance=0.0,
            last_updated=datetime.utcnow(),
            data={"source": "error", "error": "Service temporarily unavailable"}
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
    token_service: TokenService = Depends(get_token_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Connect wallet to user account"""
    try:
        # Use the token service to connect wallet
        result = await token_service.connect_wallet(
            user_id=str(current_user.id), 
            wallet_address=request.address
        )
        
        if result:
            return {
                "message": "Wallet connected successfully", 
                "wallet_address": request.address,
                "network": request.network
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to connect wallet"
            )
    except TokenValidationError as e:
        logger.error(f"Wallet validation error: {e.reason}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.reason
        )
    except WalletConnectionError as e:
        # Handle wallet connection errors specifically
        logger.error(f"Wallet connection error: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message
        )
    except TokenError as e:
        logger.error(f"Token error connecting wallet: {e.message}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=e.message
        )
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
        from sqlalchemy import select, text
        from core.models.token_transaction import TokenTransaction
        
        # Using text-based SQL count which avoids the linter error
        count_query = text("SELECT COUNT(*) FROM token_transactions WHERE user_id = :user_id")
        result = await db.execute(count_query, {"user_id": str(current_user.id)})
        total_count = result.scalar() or 0
        
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
    except TokenTransactionError as e:
        # Handle specific TokenTransactionError with appropriate status code
        logger.error(f"Token transaction error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error retrieving transaction history: {str(e.reason)}"
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

# Purchase endpoints
@router.post("/purchase/create", response_model=TokenPurchaseResponse)
async def create_purchase_transaction(
    request: TokenPurchaseRequest,
    db: AsyncSession = Depends(get_db_session),
    token_service: TokenService = Depends(get_token_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Create a token purchase transaction"""
    try:
        logger.info(f"Creating purchase transaction for user {current_user.id}: {request.amount} tokens")
        
        # Check payment method
        if request.payment_method == "phantom":
            # Call token service to create the purchase transaction with Phantom
            result = await token_service.create_purchase_transaction(
                user_id=str(current_user.id),
                amount=request.amount,
                price_in_sol=request.price_in_sol,
                network=request.network,
                memo=request.memo,
                metadata=request.metadata
            )
            
            return TokenPurchaseResponse(
                transaction=result["transaction"],
                signature=result["signature"]
            )
        else:
            # For other payment methods, return an error - they should use the specific endpoint
            raise TokenValidationError(
                field="payment_method",
                reason=f"For {request.payment_method} payments, use the specific payment endpoint"
            )
            
    except TokenValidationError as e:
        logger.error(f"Validation error creating purchase transaction: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message
        )
    except Exception as e:
        logger.error(f"Error creating purchase transaction: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating purchase transaction: {str(e)}"
        )

# Stripe payment endpoints
@router.post("/purchase/stripe/create", response_model=StripePaymentResponse)
async def create_stripe_payment(
    request: TokenPurchaseRequest,
    stripe_service: StripeService = Depends(get_stripe_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Create a Stripe payment intent for token purchase"""
    try:
        logger.info(f"Creating Stripe payment intent for user {current_user.id}: {request.amount} tokens")
        
        # Calculate price in USD (10 cents per token)
        amount_usd = request.amount * 0.1
        
        # Create metadata for the payment
        metadata = {
            "user_id": str(current_user.id),
            "token_amount": request.amount,
            "purpose": "token_purchase",
            "memo": request.memo or "Token purchase"
        }
        
        # Add any custom metadata from the request
        if request.metadata:
            metadata.update({f"custom_{k}": v for k, v in request.metadata.items()})
        
        # Create payment intent with Stripe
        payment_intent = await stripe_service.create_payment_intent(
            amount=amount_usd,
            currency="usd",
            payment_method_types=["card"],
            metadata=metadata
        )
        
        return StripePaymentResponse(
            client_secret=payment_intent["client_secret"],
            payment_intent_id=payment_intent["payment_intent_id"],
            amount=payment_intent["amount"],
            currency=payment_intent["currency"],
            status=payment_intent["status"]
        )
        
    except PaymentError as e:
        logger.error(f"Payment error creating Stripe payment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message
        )
    except Exception as e:
        logger.error(f"Error creating Stripe payment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating Stripe payment: {str(e)}"
        )

@router.post("/purchase/stripe/verify", response_model=TokenPurchaseVerifyResponse)
async def verify_stripe_payment(
    request: StripePaymentVerifyRequest,
    db: AsyncSession = Depends(get_db_session),
    stripe_service: StripeService = Depends(get_stripe_service),
    token_service: TokenService = Depends(get_token_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Verify a Stripe payment and credit tokens to user"""
    try:
        logger.info(f"Verifying Stripe payment for user {current_user.id}: {request.payment_intent_id}")
        
        # Verify payment with Stripe
        payment_result = await stripe_service.verify_payment_intent(request.payment_intent_id)
        
        if not payment_result["success"]:
            logger.warning(f"Payment not successful: {payment_result['status']}")
            raise PaymentError(
                message=f"Payment is not successful: {payment_result['status']}",
                payment_id=request.payment_intent_id
            )
        
        # Extract token amount from payment metadata
        token_amount = float(payment_result["metadata"].get("token_amount", 0))
        
        if token_amount <= 0:
            logger.error(f"Invalid token amount in payment metadata: {token_amount}")
            raise PaymentValidationError(
                field="token_amount",
                reason="Invalid token amount in payment"
            )
        
        # Create token purchase transaction
        transaction = await token_service.process_transaction(
            db=db,
            user_id=str(current_user.id),
            amount=token_amount,
            transaction_type="credit",
            details={
                "payment_method": "stripe",
                "payment_id": payment_result["payment_intent_id"],
                "amount_paid": payment_result["amount"],
                "currency": payment_result["currency"],
                "status": payment_result["status"],
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        
        # Get updated balance
        new_balance = await token_service.get_balance(str(current_user.id))
        
        return TokenPurchaseVerifyResponse(
            success=True,
            transaction_id=transaction.id,
            amount=token_amount,
            new_balance=float(new_balance)
        )
        
    except PaymentError as e:
        logger.error(f"Payment error verifying Stripe payment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message
        )
    except TokenError as e:
        logger.error(f"Token error processing Stripe payment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message
        )
    except Exception as e:
        logger.error(f"Error verifying Stripe payment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error verifying Stripe payment: {str(e)}"
        )

@router.post("/webhook/stripe")
async def stripe_webhook(
    request: Request,
    stripe_service: StripeService = Depends(get_stripe_service),
    db: AsyncSession = Depends(get_db_session),
    token_service: TokenService = Depends(get_token_service),
    stripe_signature: str = Header(None)
):
    """Handle Stripe webhook events"""
    try:
        logger.info("Received Stripe webhook")
        
        if not stripe_signature:
            logger.warning("Missing Stripe signature header")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing Stripe signature"
            )
        
        # Read request body as bytes
        payload = await request.body()
        
        # Process webhook
        result = await stripe_service.handle_webhook(payload, stripe_signature)
        
        logger.info(f"Processed webhook: {result['event_type']}")
        
        if result["event_type"] == "payment_intent.succeeded":
            # Process successful payment if needed (this is a backup to the verify endpoint)
            payment_intent_id = result["payment_intent_id"]
            metadata = result.get("metadata", {})
            
            if metadata.get("purpose") == "token_purchase":
                user_id = metadata.get("user_id")
                token_amount = float(metadata.get("token_amount", 0))
                
                if user_id and token_amount > 0:
                    # Check if we've already processed this payment
                    # (this would require implementing a check in token service)
                    # For now, just log it
                    logger.info(f"Webhook: Successful token purchase of {token_amount} tokens for user {user_id}")
            
        return {"success": True, "event_type": result["event_type"]}
        
    except PaymentError as e:
        logger.error(f"Payment error processing webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.message
        )
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing webhook: {str(e)}"
        )

@router.get("/info")
async def get_wallet_info(
    db: AsyncSession = Depends(get_db_session),
    token_service: TokenService = Depends(get_token_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Get user's wallet information"""
    try:
        # Get the user's wallet using the token service
        user_wallet = await token_service._get_user_wallet(str(current_user.id))
        
        # Get the user's balance
        balance = await token_service.get_balance(str(current_user.id))
        
        # Prepare the response
        if user_wallet:
            return {
                "address": user_wallet.address,
                "balance": float(balance),
                "isConnected": user_wallet.is_active,
                "network": user_wallet.network
            }
        else:
            # Return default info if no wallet is connected
            return {
                "address": "",
                "balance": float(balance),
                "isConnected": False,
                "network": "mainnet-beta"
            }
    except Exception as e:
        logger.error(f"Error getting wallet info: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting wallet info: {str(e)}"
        )

@router.post("/disconnect-wallet")
async def disconnect_wallet(
    db: AsyncSession = Depends(get_db_session),
    token_service: TokenService = Depends(get_token_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Disconnect user's wallet"""
    try:
        # Check if user has an active wallet
        user_wallet = await token_service._get_user_wallet(str(current_user.id))
        
        if not user_wallet:
            return {"message": "No wallet connected"}
        
        # Call repository to disconnect the wallet (set is_active to False)
        result = await token_service.repository.disconnect_wallet(str(current_user.id))
        
        if result:
            return {"message": "Wallet disconnected successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to disconnect wallet"
            )
    except Exception as e:
        logger.error(f"Error disconnecting wallet: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error disconnecting wallet: {str(e)}"
        ) 
