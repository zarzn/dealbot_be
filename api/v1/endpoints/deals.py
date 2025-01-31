from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from backend.core.database import get_db
from backend.core.models.deal import DealResponse
from backend.core.services import DealService, get_current_user
from backend.core.models.user import UserInDB

router = APIRouter()

@router.get("/", response_model=List[DealResponse])
async def get_deals(
    db: AsyncSession = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
):
    """Get all deals for current user"""
    deal_service = DealService(db)
    return await deal_service.get_deals(current_user.id)

@router.get("/{deal_id}", response_model=DealResponse)
async def get_deal(
    deal_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
):
    """Get a specific deal"""
    deal_service = DealService(db)
    return await deal_service.get_deal(current_user.id, deal_id) 