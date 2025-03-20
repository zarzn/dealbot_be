"""Markets API module."""

from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from core.database import get_async_db_session as get_db
from core.models.market import (
    MarketCreate,
    MarketUpdate,
    MarketResponse,
    MarketType,
    MarketStatus,
    MarketAnalytics,
    MarketComparison,
    MarketPriceHistory,
    MarketAvailability,
    MarketTrends,
    MarketPerformance,
    MarketCategory
)
from core.services.market import MarketService
from core.services.analytics import AnalyticsService
from core.services.token_service import TokenService
from core.services.market_search import MarketSearchService
from core.services.deal_analysis import DealAnalysisService
from core.repositories.market import MarketRepository
from core.exceptions import (
    NotFoundException,
    ValidationError,
    InsufficientTokensError,
    RateLimitError,
    MarketError
)
from core.api.v1.dependencies import (
    get_current_user,
    get_analytics_service,
    get_token_service,
    get_market_search_service,
    get_deal_analysis_service,
    get_market_service
)

router = APIRouter(tags=["markets"])

# Token cost constants
MARKET_ANALYSIS_COST = 5
MARKET_COMPARISON_COST = 10
MARKET_HISTORY_COST = 3

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

@router.get("/list", response_model=List[MarketResponse])
async def list_markets(
    market_service: MarketService = Depends(get_market_service),
    _=Depends(get_current_user)
):
    """
    Get all markets.
    """
    return await market_service.get_all_markets()

@router.get("/active", response_model=List[MarketResponse])
async def get_active_markets(
    market_service: MarketService = Depends(get_market_service)
):
    """
    Get all active markets.
    """
    markets = await market_service.get_active_markets()
    
    # Ensure all required fields are present in the response
    response_markets = []
    for market in markets:
        # Create a dict with all required fields, ensuring proper types
        market_dict = {
            "id": market.id,
            "name": market.name,
            "type": market.type,
            "description": market.description or "",
            "api_endpoint": market.api_endpoint or "",
            "rate_limit": int(market.rate_limit or 100),
            "config": market.config or {},
            "status": market.status,
            "is_active": bool(market.is_active),
            "success_rate": float(market.success_rate or 0.0),
            "avg_response_time": float(market.avg_response_time or 0.0),
            "total_requests": int(market.total_requests or 0),
            "error_count": int(market.error_count or 0),
            "requests_today": int(market.requests_today or 0),
            "last_error": market.last_error,
            "last_error_at": market.last_error_at,
            "last_successful_request": market.last_successful_request,
            "created_at": market.created_at,
            "updated_at": market.updated_at
        }
        response_markets.append(market_dict)
    
    return response_markets

@router.get("/supported", response_model=List[dict])
async def get_supported_markets() -> Any:
    """Get list of supported markets"""
    return [
        {"id": "amazon", "name": "Amazon", "status": "active"},
        {"id": "walmart", "name": "Walmart", "status": "active"}
    ]

@router.get("/{market_id}", response_model=MarketResponse)
async def get_market_by_id(
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

@router.get("/{market_id}/categories")
async def get_market_categories(
    market_id: UUID,
    market_service: MarketService = Depends(get_market_service),
    _=Depends(get_current_user)
):
    """Get market categories"""
    try:
        categories = await market_service.get_categories(market_id)
        return categories
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{market_id}/analytics", response_model=MarketAnalytics)
async def get_market_analytics(
    market_id: UUID,
    time_range: Optional[str] = Query(
        "30d",
        description="Time range for analytics (7d, 30d, 90d, all)"
    ),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    token_service: TokenService = Depends(get_token_service),
    current_user=Depends(get_current_user)
):
    """Get analytics for a specific market"""
    try:
        # Validate tokens before getting analytics
        await token_service.validate_operation(current_user.id, "market_analytics")
        
        # Convert time range to datetime
        now = datetime.utcnow()
        ranges = {
            "7d": now - timedelta(days=7),
            "30d": now - timedelta(days=30),
            "90d": now - timedelta(days=90),
            "all": None
        }
        start_date = ranges.get(time_range)
        
        analytics = await analytics_service.get_market_analytics(
            market_id=market_id,
            start_date=start_date
        )
        
        # Deduct tokens for analytics request
        await token_service.deduct_tokens(
            current_user.id,
            "market_analytics",
            market_id=market_id
        )
        
        return analytics
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/compare", response_model=MarketComparison)
async def compare_markets(
    market_ids: List[UUID],
    category: Optional[str] = None,
    price_range: Optional[str] = None,
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    token_service: TokenService = Depends(get_token_service),
    current_user=Depends(get_current_user)
):
    """Compare multiple markets"""
    try:
        # Validate tokens before comparison
        await token_service.validate_operation(current_user.id, "market_comparison")
        
        comparison = await analytics_service.compare_markets(
            market_ids=market_ids,
            category=category,
            price_range=price_range
        )
        
        # Deduct tokens for comparison request
        await token_service.deduct_tokens(
            current_user.id,
            "market_comparison"
        )
        
        return comparison
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{market_id}/price-history", response_model=MarketPriceHistory)
async def get_market_price_history(
    market_id: UUID,
    category: Optional[str] = None,
    product_id: Optional[str] = None,
    time_range: Optional[str] = Query(
        "30d",
        description="Time range for price history (7d, 30d, 90d, all)"
    ),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    token_service: TokenService = Depends(get_token_service),
    current_user=Depends(get_current_user)
):
    """Get price history for a market"""
    try:
        # Validate tokens before getting price history
        await token_service.validate_operation(current_user.id, "market_price_history")
        
        # Convert time range to datetime
        now = datetime.utcnow()
        ranges = {
            "7d": now - timedelta(days=7),
            "30d": now - timedelta(days=30),
            "90d": now - timedelta(days=90),
            "all": None
        }
        start_date = ranges.get(time_range)
        
        history = await analytics_service.get_price_history(
            market_id=market_id,
            category=category,
            product_id=product_id,
            start_date=start_date
        )
        
        # Deduct tokens for price history request
        await token_service.deduct_tokens(
            current_user.id,
            "market_price_history",
            market_id=market_id
        )
        
        return history
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{market_id}/availability", response_model=MarketAvailability)
async def get_market_availability(
    market_id: UUID,
    category: Optional[str] = None,
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    token_service: TokenService = Depends(get_token_service),
    current_user=Depends(get_current_user)
):
    """Get availability metrics for a market"""
    try:
        # Validate tokens before getting availability
        await token_service.validate_operation(current_user.id, "market_availability")
        
        availability = await analytics_service.get_availability(
            market_id=market_id,
            category=category
        )
        
        # Deduct tokens for availability request
        await token_service.deduct_tokens(
            current_user.id,
            "market_availability",
            market_id=market_id
        )
        
        return availability
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{market_id}/trends", response_model=MarketTrends)
async def get_market_trends(
    market_id: UUID,
    category: Optional[str] = None,
    trend_period: Optional[str] = Query(
        "24h",
        description="Trend period (1h, 24h, 7d, 30d)"
    ),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    token_service: TokenService = Depends(get_token_service),
    current_user=Depends(get_current_user)
):
    """Get market trends"""
    try:
        # Validate tokens before getting trends
        await token_service.validate_operation(current_user.id, "market_trends")
        
        # Convert trend period to timedelta
        now = datetime.utcnow()
        periods = {
            "1h": timedelta(hours=1),
            "24h": timedelta(days=1),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30)
        }
        period = periods.get(trend_period)
        
        trends = await analytics_service.get_trends(
            market_id=market_id,
            category=category,
            period=period
        )
        
        # Deduct tokens for trends request
        await token_service.deduct_tokens(
            current_user.id,
            "market_trends",
            market_id=market_id
        )
        
        return trends
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{market_id}/performance", response_model=MarketPerformance)
async def get_market_performance(
    market_id: UUID,
    time_range: Optional[str] = Query(
        "24h",
        description="Time range for performance metrics (1h, 24h, 7d, 30d)"
    ),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    token_service: TokenService = Depends(get_token_service),
    current_user=Depends(get_current_user)
):
    """Get market performance metrics"""
    try:
        # Validate tokens before getting performance metrics
        await token_service.validate_operation(current_user.id, "market_performance")
        
        # Convert time range to timedelta
        now = datetime.utcnow()
        ranges = {
            "1h": timedelta(hours=1),
            "24h": timedelta(days=1),
            "7d": timedelta(days=7),
            "30d": timedelta(days=30)
        }
        time_delta = ranges.get(time_range)
        
        performance = await analytics_service.get_performance(
            market_id=market_id,
            time_delta=time_delta
        )
        
        # Deduct tokens for performance request
        await token_service.deduct_tokens(
            current_user.id,
            "market_performance",
            market_id=market_id
        )
        
        return performance
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{market_id}/search")
async def search_market(
    market_id: UUID,
    query: str = Query(..., description="Search query"),
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    limit: Optional[int] = Query(10, ge=1, le=100),
    market_search_service: MarketSearchService = Depends(get_market_search_service),
    token_service: TokenService = Depends(get_token_service),
    current_user=Depends(get_current_user)
):
    """Search products in a market"""
    try:
        # Validate tokens before search
        await token_service.validate_operation(current_user.id, "market_search")
        
        results = await market_search_service.search(
            market_id=market_id,
            query=query,
            category=category,
            min_price=min_price,
            max_price=max_price,
            limit=limit
        )
        
        # Check if pricing exists before deducting tokens
        pricing = await token_service.get_pricing_info("market_search")
        if pricing:
            # Deduct tokens for search request only if pricing exists
            await token_service.deduct_tokens_for_operation(
                current_user.id,
                "market_search",
                market_id=market_id
            )
        
        return results
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{market_id}/product/{product_id}")
async def get_product_details(
    market_id: UUID,
    product_id: str,
    market_search_service: MarketSearchService = Depends(get_market_search_service),
    token_service: TokenService = Depends(get_token_service),
    current_user=Depends(get_current_user)
):
    """Get detailed product information"""
    try:
        # Validate tokens before getting product details
        await token_service.validate_operation(current_user.id, "product_details")
        
        details = await market_search_service.get_product_details(
            market_id=market_id,
            product_id=product_id
        )
        
        # Deduct tokens for product details request
        await token_service.deduct_tokens(
            current_user.id,
            "product_details",
            market_id=market_id
        )
        
        return details
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{market_id}/stats", response_model=Dict[str, Any])
async def get_market_stats(
    market_id: UUID,
    time_range: Optional[str] = Query(
        "30d",
        description="Time range for stats (7d, 30d, 90d, all)"
    ),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    current_user=Depends(get_current_user)
):
    """Get market statistics"""
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
        
        stats = await analytics_service.get_market_stats(
            market_id=market_id,
            start_date=start_date
        )
        
        return stats
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) 