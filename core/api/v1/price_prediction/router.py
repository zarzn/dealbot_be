"""Price prediction router."""

from typing import List, Dict
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_async_db_session as get_db, get_async_db_context
from core.models.price_prediction import (
    PricePrediction,
    PricePredictionCreate,
    PricePredictionResponse
)
from core.services.price_prediction import PricePredictionService
from core.exceptions import (
    PriceTrackingError,
    ValidationError,
    NotFoundError,
    DatabaseError,
    PricePredictionError,
    InsufficientDataError,
    ModelError
)
from core.dependencies import get_current_user
from core.models.user import User

router = APIRouter(prefix="/price-prediction", tags=["price-prediction"])

# Helper dependency to get db session using the new context manager
async def get_db_session() -> AsyncSession:
    """Get a database session using the improved context manager.
    
    This dependency provides better connection management and prevents connection leaks.
    """
    async with get_async_db_context() as session:
        yield session

@router.post(
    "/predictions",
    response_model=PricePredictionResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_prediction(
    prediction: PricePredictionCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
) -> PricePredictionResponse:
    """Create a new price prediction."""
    try:
        service = PricePredictionService(session)
        return await service.create_prediction(prediction, current_user.id)
    except InsufficientDataError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except PricePredictionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get(
    "/predictions/{prediction_id}",
    response_model=PricePredictionResponse
)
async def get_prediction(
    prediction_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
) -> PricePredictionResponse:
    """Get a price prediction by ID."""
    try:
        service = PricePredictionService(session)
        prediction = await service.get_prediction(prediction_id, current_user.id)
        if not prediction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Price prediction not found"
            )
        return prediction
    except PricePredictionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get(
    "/predictions",
    response_model=List[PricePredictionResponse]
)
async def list_predictions(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    skip: int = 0,
    limit: int = 100
) -> List[PricePredictionResponse]:
    """List all price predictions for the current user."""
    try:
        service = PricePredictionService(session)
        return await service.list_predictions(current_user.id, skip, limit)
    except PricePredictionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get(
    "/deals/{deal_id}/predictions",
    response_model=List[PricePredictionResponse]
)
async def get_deal_predictions(
    deal_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    days_ahead: int = 30
) -> List[PricePredictionResponse]:
    """Get price predictions for a deal."""
    try:
        service = PricePredictionService(session)
        predictions = await service.get_deal_predictions(deal_id, current_user.id, days_ahead)
        if not predictions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No predictions found for this deal"
            )
        return predictions
    except InsufficientDataError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except PricePredictionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get(
    "/deals/{deal_id}/analysis",
    response_model=Dict
)
async def analyze_deal_price(
    deal_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
) -> Dict:
    """Get detailed price analysis for a deal."""
    try:
        service = PricePredictionService(session)
        analysis = await service.analyze_deal_price(deal_id, current_user.id)
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Could not analyze deal price"
            )
        return analysis
    except InsufficientDataError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except PricePredictionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get(
    "/deals/{deal_id}/trends",
    response_model=Dict
)
async def get_price_trends(
    deal_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    timeframe: str = "1m"
) -> Dict:
    """Get price trends for a deal."""
    try:
        service = PricePredictionService(session)
        trends = await service.get_price_trends(deal_id, current_user.id, timeframe)
        if not trends:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No price trends found"
            )
        return trends
    except InsufficientDataError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except PricePredictionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get(
    "/models/performance",
    response_model=Dict
)
async def get_model_performance(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
) -> Dict:
    """Get performance metrics for prediction models."""
    try:
        service = PricePredictionService(session)
        metrics = await service.get_model_performance(current_user.id)
        if not metrics:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No model performance metrics found"
            )
        return metrics
    except ModelError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except PricePredictionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) 