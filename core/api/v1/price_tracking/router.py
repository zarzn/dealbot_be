"""Price tracking API endpoints."""

from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db, get_async_db_context
from core.models.price_tracking import (
    PricePointBase,
    PricePointCreate,
    PricePointResponse,
    PriceTrackerCreate,
    PriceTrackerResponse
)
from core.services.price_tracking import PriceTrackingService
from core.exceptions.price import (
    PriceTrackingError,
    InsufficientDataError
)
from core.api.v1.dependencies import get_current_user
from core.models.user import User

router = APIRouter(prefix="/price-tracking", tags=["price-tracking"])

# Helper dependency to get db session using the improved context manager
async def get_db_session() -> AsyncSession:
    """Get a database session using the improved context manager.
    
    This dependency provides better connection management and prevents connection leaks.
    """
    async with get_async_db_context() as session:
        yield session

@router.post(
    "/trackers",
    response_model=PriceTrackerResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_price_tracker(
    tracker: PriceTrackerCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
) -> PriceTrackerResponse:
    """Create a new price tracker."""
    try:
        service = PriceTrackingService(session)
        return await service.create_tracker(tracker, current_user.id)
    except PriceTrackingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get(
    "/trackers/{tracker_id}",
    response_model=PriceTrackerResponse
)
async def get_price_tracker(
    tracker_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
) -> PriceTrackerResponse:
    """Get price tracker details."""
    try:
        service = PriceTrackingService(session)
        tracker = await service.get_tracker(tracker_id, current_user.id)
        if not tracker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Price tracker not found"
            )
        return tracker
    except PriceTrackingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get(
    "/trackers",
    response_model=List[PriceTrackerResponse]
)
async def list_price_trackers(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    skip: int = 0,
    limit: int = 100
) -> List[PriceTrackerResponse]:
    """List all price trackers for the current user."""
    try:
        service = PriceTrackingService(session)
        return await service.list_trackers(current_user.id, skip, limit)
    except PriceTrackingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.put(
    "/trackers/{tracker_id}",
    response_model=PriceTrackerResponse
)
async def update_price_tracker(
    tracker_id: int,
    update_data: PriceTrackerCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
) -> PriceTrackerResponse:
    """Update price tracker settings."""
    try:
        service = PriceTrackingService(session)
        updated = await service.update_tracker(tracker_id, current_user.id, update_data)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Price tracker not found"
            )
        return updated
    except PriceTrackingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.delete(
    "/trackers/{tracker_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
async def delete_price_tracker(
    tracker_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Delete a price tracker."""
    try:
        service = PriceTrackingService(session)
        deleted = await service.delete_tracker(tracker_id, current_user.id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Price tracker not found"
            )
    except PriceTrackingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get(
    "/trackers/{tracker_id}/history",
    response_model=List[PricePointResponse]
)
async def get_price_history(
    tracker_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    limit: int = 100
) -> List[PricePointResponse]:
    """Get price history for a tracker."""
    try:
        service = PriceTrackingService(session)
        history = await service.get_price_history(tracker_id, current_user.id, limit)
        if not history:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No price history found"
            )
        return history
    except InsufficientDataError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except PriceTrackingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post(
    "/trackers/{tracker_id}/points",
    response_model=PricePointResponse,
    status_code=status.HTTP_201_CREATED
)
async def add_price_point(
    tracker_id: int,
    price_point: PricePointCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
) -> PricePointResponse:
    """Add a new price point for a tracker."""
    try:
        service = PriceTrackingService(session)
        return await service.add_price_point(tracker_id, current_user.id, price_point)
    except PriceTrackingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/trackers/{tracker_id}/stats")
async def get_price_stats(
    tracker_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Get price statistics for a tracker."""
    try:
        service = PriceTrackingService(session)
        stats = await service.get_price_stats(tracker_id, current_user.id)
        if not stats:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No price statistics found"
            )
        return stats
    except InsufficientDataError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except PriceTrackingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/deals/{deal_id}/history")
async def get_deal_price_history(
    deal_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    days: int = 30
):
    """Get price history for a deal."""
    try:
        service = PriceTrackingService(session)
        return await service.get_deal_price_history(deal_id, current_user.id, days)
    except PriceTrackingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) 