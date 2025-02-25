"""Deals API module."""

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta

from core.database import get_async_db_session as get_db
from core.models.deal import (
    DealResponse,
    DealAnalytics,
    DealFilter,
    DealRecommendation,
    DealHistory,
    DealPriceHistory,
    DealSearch,
    AIAnalysis,
    PriceHistory,
    PriceHistoryResponse
)
from core.models.user import User, UserInDB
from core.services.deal import DealService
from core.services.analytics import AnalyticsService
from core.services.recommendation import RecommendationService
from core.services.token import TokenService
from core.api.v1.dependencies import (
    get_deal_service,
    get_analytics_service,
    get_recommendation_service,
    get_token_service,
    get_current_user
)

router = APIRouter(tags=["deals"])

async def validate_tokens(
    token_service: TokenService,
    user_id: UUID,
    operation: str
):
    """Validate user has sufficient tokens for the operation"""
    try:
        await token_service.validate_operation(user_id, operation)
    except Exception as e:
        raise HTTPException(
            status_code=402,
            detail=f"Token validation failed: {str(e)}"
        )

async def process_deals_background(background_tasks: BackgroundTasks, deals: List[Any], deal_service: DealService):
    """Process deals in background."""
    for deal in deals:
        background_tasks.add_task(deal_service.process_deal_background, deal.id)

@router.get("/", response_model=List[DealResponse], response_model_exclude_none=True)
async def get_deals(
    background_tasks: BackgroundTasks,
    category: Optional[str] = None,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    sort_by: Optional[str] = "relevance",
    deal_service: DealService = Depends(get_deal_service),
    token_service: TokenService = Depends(get_token_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Get deals matching the specified criteria."""
    try:
        await validate_tokens(token_service, current_user.id, "get_deals")
        
        filters = DealFilter(
            category=category,
            price_min=price_min,
            price_max=price_max,
            sort_by=sort_by
        )
        
        # Get deals first
        deals = await deal_service.get_deals(current_user.id, filters)
        
        # Schedule background processing
        for deal in deals:
            background_tasks.add_task(deal_service.process_deal_background, deal.id)
        
        # Convert to response model and return
        response_deals = [DealResponse.model_validate(deal) for deal in deals]
        return response_deals
        
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to retrieve deals: {str(e)}"
        )

@router.get("/{deal_id}", response_model=DealResponse)
async def get_deal(
    deal_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserInDB = Depends(get_current_user)
):
    """Get a specific deal"""
    deal_service = DealService(db)
    return await deal_service.get_deal(current_user.id, deal_id)

@router.get("/{deal_id}/analytics", response_model=DealAnalytics)
async def get_deal_analytics(
    deal_id: UUID,
    time_range: Optional[str] = Query(
        "7d",
        description="Time range for analytics (1d, 7d, 30d, all)"
    ),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    token_service: TokenService = Depends(get_token_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Get analytics for a specific deal"""
    try:
        # Validate tokens before getting analytics
        await validate_tokens(token_service, current_user.id, "deal_analytics")
        
        # Convert time range to datetime
        now = datetime.utcnow()
        ranges = {
            "1d": now - timedelta(days=1),
            "7d": now - timedelta(days=7),
            "30d": now - timedelta(days=30),
            "all": None
        }
        start_date = ranges.get(time_range)
        
        analytics = await analytics_service.get_deal_analytics(
            deal_id=deal_id,
            user_id=current_user.id,
            start_date=start_date
        )
        
        # Deduct tokens for analytics request
        await token_service.deduct_tokens(
            current_user.id,
            "deal_analytics",
            deal_id=deal_id
        )
        
        return analytics
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/recommendations", response_model=List[DealRecommendation])
async def get_deal_recommendations(
    category: Optional[str] = None,
    limit: int = Query(10, ge=1, le=50),
    recommendation_service: RecommendationService = Depends(get_recommendation_service),
    token_service: TokenService = Depends(get_token_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Get personalized deal recommendations"""
    try:
        # Validate tokens before getting recommendations
        await validate_tokens(token_service, current_user.id, "deal_recommendations")
        
        recommendations = await recommendation_service.get_recommendations(
            user_id=current_user.id,
            category=category,
            limit=limit
        )
        
        # Deduct tokens for recommendations request
        await token_service.deduct_tokens(
            current_user.id,
            "deal_recommendations"
        )
        
        return recommendations
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/history", response_model=List[DealHistory])
async def get_deal_history(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    category: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    deal_service: DealService = Depends(get_deal_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Get user's deal history"""
    try:
        history = await deal_service.get_deal_history(
            user_id=current_user.id,
            start_date=start_date,
            end_date=end_date,
            category=category,
            page=page,
            page_size=page_size
        )
        return history
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{deal_id}/price-history", response_model=DealPriceHistory)
async def get_deal_price_history(
    deal_id: UUID,
    time_range: Optional[str] = Query(
        "30d",
        description="Time range for price history (7d, 30d, 90d, all)"
    ),
    deal_service: DealService = Depends(get_deal_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Get price history for a specific deal"""
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
        
        price_history = await deal_service.get_price_history(
            deal_id=deal_id,
            user_id=current_user.id,
            start_date=start_date
        )
        return price_history
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/stats", response_model=Dict[str, Any])
async def get_deal_stats(
    time_range: Optional[str] = Query(
        "30d",
        description="Time range for stats (7d, 30d, 90d, all)"
    ),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Get aggregated deal statistics"""
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
        
        stats = await analytics_service.get_deal_stats(
            user_id=current_user.id,
            start_date=start_date
        )
        return stats
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{deal_id}/bookmark")
async def bookmark_deal(
    deal_id: UUID,
    deal_service: DealService = Depends(get_deal_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Bookmark a deal for later reference"""
    try:
        await deal_service.bookmark_deal(
            user_id=current_user.id,
            deal_id=deal_id
        )
        return {"message": "Deal bookmarked successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{deal_id}/bookmark")
async def remove_bookmark(
    deal_id: UUID,
    deal_service: DealService = Depends(get_deal_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Remove a deal bookmark"""
    try:
        await deal_service.remove_bookmark(
            user_id=current_user.id,
            deal_id=deal_id
        )
        return {"message": "Bookmark removed successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/bookmarks", response_model=List[DealResponse])
async def get_bookmarked_deals(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    deal_service: DealService = Depends(get_deal_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Get user's bookmarked deals"""
    try:
        bookmarks = await deal_service.get_bookmarked_deals(
            user_id=current_user.id,
            page=page,
            page_size=page_size
        )
        return bookmarks
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{deal_id}/track")
async def track_deal(
    deal_id: UUID,
    deal_service: DealService = Depends(get_deal_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Start tracking a deal"""
    try:
        await deal_service.track_deal(
            user_id=current_user.id,
            deal_id=deal_id
        )
        return {"message": "Deal tracking started successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{deal_id}/track")
async def stop_tracking_deal(
    deal_id: UUID,
    deal_service: DealService = Depends(get_deal_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Stop tracking a deal"""
    try:
        await deal_service.stop_tracking_deal(
            user_id=current_user.id,
            deal_id=deal_id
        )
        return {"message": "Deal tracking stopped successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{deal_id}/analysis", response_model=AIAnalysis)
async def get_deal_analysis(
    deal_id: UUID,
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    token_service: TokenService = Depends(get_token_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Get AI analysis for a specific deal"""
    try:
        await validate_tokens(token_service, current_user.id, "deal_analysis")
        analysis = await analytics_service.get_deal_analysis(
            deal_id=deal_id,
            user_id=current_user.id
        )
        return analysis
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{deal_id}/similar", response_model=List[DealResponse])
async def get_similar_deals(
    deal_id: UUID,
    limit: int = Query(10, ge=1, le=50),
    recommendation_service: RecommendationService = Depends(get_recommendation_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Get similar deals to the specified deal"""
    try:
        similar_deals = await recommendation_service.get_similar_deals(
            deal_id=deal_id,
            user_id=current_user.id,
            limit=limit
        )
        return similar_deals
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{deal_id}/predictions", response_model=List[PriceHistoryResponse])
async def get_deal_predictions(
    deal_id: UUID,
    days: int = Query(30, ge=1, le=90),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    token_service: TokenService = Depends(get_token_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Get price predictions for a deal"""
    try:
        await validate_tokens(token_service, current_user.id, "deal_predictions")
        predictions = await analytics_service.get_price_predictions(
            deal_id=deal_id,
            user_id=current_user.id,
            days=days
        )
        return predictions
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{deal_id}/validate", response_model=Dict[str, Any])
async def validate_deal(
    deal_id: UUID,
    validation_data: Dict[str, Any],
    deal_service: DealService = Depends(get_deal_service),
    token_service: TokenService = Depends(get_token_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Validate a deal based on specified criteria"""
    try:
        # Validate tokens before validation
        await validate_tokens(token_service, current_user.id, "deal_validation")
        
        # Extract validation type from data or use default
        validation_type = validation_data.get("validation_type", "price")
        
        validation_result = await deal_service.validate_deal(
            deal_id=deal_id,
            user_id=current_user.id,
            validation_type=validation_type,
            criteria=validation_data.get("criteria", {})
        )
        
        # Deduct tokens for validation request
        await token_service.deduct_tokens(
            current_user.id,
            "deal_validation",
            deal_id=deal_id
        )
        
        return {"validation_result": validation_result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/compare", response_model=Dict[str, Any])
async def compare_deals(
    comparison_data: Dict[str, Any],
    deal_service: DealService = Depends(get_deal_service),
    token_service: TokenService = Depends(get_token_service),
    current_user: UserInDB = Depends(get_current_user)
):
    """Compare multiple deals based on specified criteria"""
    try:
        # Validate tokens before comparison
        await validate_tokens(token_service, current_user.id, "deal_comparison")
        
        # Extract comparison parameters
        deal_ids = [UUID(id_str) for id_str in comparison_data.get("deal_ids", [])]
        comparison_type = comparison_data.get("comparison_type", "price")
        criteria = comparison_data.get("criteria", {})
        
        if not deal_ids:
            raise HTTPException(
                status_code=400,
                detail="No deal IDs provided for comparison"
            )
        
        comparison_result = await deal_service.compare_deals(
            deal_ids=deal_ids,
            user_id=current_user.id,
            comparison_type=comparison_type,
            criteria=criteria
        )
        
        # Deduct tokens for comparison request
        await token_service.deduct_tokens(
            current_user.id,
            "deal_comparison"
        )
        
        return {"comparison_result": comparison_result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid deal ID: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/search", response_model=List[DealResponse])
async def search_deals(
    search: DealSearch,
    background_tasks: BackgroundTasks,
    deal_service: DealService = Depends(get_deal_service),
    token_service: TokenService = Depends(get_token_service),
    current_user: Optional[UserInDB] = Depends(get_current_user),
) -> List[DealResponse]:
    """
    Search for deals based on criteria
    """
    # Validate token usage if user is authenticated
    if current_user:
        await validate_tokens(token_service, current_user.id, "deal_search")
        
    # Set up background processing
    deal_service.set_background_tasks(background_tasks)
    
    # Perform search
    deals = await deal_service.search_deals(
        search,
        user_id=current_user.id if current_user else None
    )
    return deals 