from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from backend.core.database import get_db
from backend.core.services.auth import get_current_user
from backend.core.services.token import TokenService
from backend.core.models.user import UserInDB
from backend.core.models.token import (
    TokenBalanceResponse,
    WalletConnectRequest,
    TransactionHistoryResponse,
    TokenPricingResponse
)

router = APIRouter()

@router.get("/balance", response_model=TokenBalanceResponse)
async def get_balance(
    db: AsyncSession = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
):
    """Get token balance for current user"""
    token_service = TokenService(db)
    return await token_service.get_balance(current_user.id)

@router.post("/connect-wallet")
async def connect_wallet(
    request: WalletConnectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
):
    """Connect wallet to user account"""
    token_service = TokenService(db)
    return await token_service.connect_wallet(current_user.id, request.wallet_address)

@router.get("/transactions", response_model=List[TransactionHistoryResponse])
async def get_transactions(
    db: AsyncSession = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
):
    """Get transaction history for current user"""
    token_service = TokenService(db)
    return await token_service.get_transactions(current_user.id)

@router.get("/pricing", response_model=List[TokenPricingResponse])
async def get_token_pricing(
    service_type: str,
    db: AsyncSession = Depends(get_db)
):
    """Get token pricing information"""
    token_service = TokenService(db)
    return await token_service.get_pricing_info(service_type)
