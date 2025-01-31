from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.database import get_session
from ....core.models.market import MarketCreate, MarketUpdate, MarketResponse, MarketType
from ....core.services.market import MarketService
from ....core.repositories.market import MarketRepository
from ....core.exceptions import NotFoundException, ValidationError
from ..dependencies import get_current_user

router = APIRouter(prefix="/markets", tags=["markets"])

async def get_market_service(session: AsyncSession = Depends(get_session)) -> MarketService:
    return MarketService(MarketRepository(session))

@router.post("", response_model=MarketResponse, status_code=status.HTTP_201_CREATED)
async def create_market(
    market_data: MarketCreate,
    market_service: MarketService = Depends(get_market_service),
    _=Depends(get_current_user)
):
    """
    Create a new market.
    Requires admin privileges.
    """
    try:
        return await market_service.create_market(market_data)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("", response_model=List[MarketResponse])
async def get_markets(
    market_service: MarketService = Depends(get_market_service),
    _=Depends(get_current_user)
):
    """
    Get all markets.
    """
    return await market_service.get_all_markets()

@router.get("/active", response_model=List[MarketResponse])
async def get_active_markets(
    market_service: MarketService = Depends(get_market_service),
    _=Depends(get_current_user)
):
    """
    Get all active markets.
    """
    return await market_service.get_active_markets()

@router.get("/{market_id}", response_model=MarketResponse)
async def get_market(
    market_id: UUID,
    market_service: MarketService = Depends(get_market_service),
    _=Depends(get_current_user)
):
    """
    Get a specific market by ID.
    """
    try:
        return await market_service.get_market(market_id)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.get("/type/{market_type}", response_model=MarketResponse)
async def get_market_by_type(
    market_type: MarketType,
    market_service: MarketService = Depends(get_market_service),
    _=Depends(get_current_user)
):
    """
    Get a specific market by type.
    """
    try:
        return await market_service.get_market_by_type(market_type)
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.put("/{market_id}", response_model=MarketResponse)
async def update_market(
    market_id: UUID,
    market_data: MarketUpdate,
    market_service: MarketService = Depends(get_market_service),
    _=Depends(get_current_user)
):
    """
    Update a market.
    Requires admin privileges.
    """
    try:
        return await market_service.update_market(market_id, market_data)
    except (NotFoundException, ValidationError) as e:
        status_code = status.HTTP_404_NOT_FOUND if isinstance(e, NotFoundException) else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(e))

@router.delete("/{market_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_market(
    market_id: UUID,
    market_service: MarketService = Depends(get_market_service),
    _=Depends(get_current_user)
):
    """
    Delete a market.
    Requires admin privileges.
    """
    try:
        if not await market_service.delete_market(market_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Market not found")
    except NotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) 