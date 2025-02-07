from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime

from core.models.deal import (
    Deal,
    DealCreate,
    DealResponse,
    DealSearchFilters,
    DealStatus
)
from core.services.deal import DealService
from core.services.token import TokenService
from core.dependencies import get_db, get_current_user
from core.exceptions import (
    DealError,
    TokenError,
    RateLimitExceededError,
    ValidationError
)
from core.config import settings

router = APIRouter()

@router.get("/search", response_model=List[DealResponse])
async def search_deals(
    query: str = Query(..., min_length=3),
    limit: int = Query(10, ge=1, le=100),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    categories: Optional[List[str]] = Query(None),
    brands: Optional[List[str]] = Query(None),
    condition: Optional[List[str]] = Query(None),
    sort_by: Optional[str] = Query(None, pattern="^(price_asc|price_desc|rating|expiry|relevance)$"),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Search for deals with advanced filtering and sorting.
    Requires token balance for search operation.
    
    - **query**: Search query string (min 3 characters)
    - **limit**: Maximum number of results (1-100)
    - **min_price**: Minimum price filter
    - **max_price**: Maximum price filter
    - **categories**: List of categories to filter by
    - **brands**: List of brands to filter by
    - **condition**: List of conditions to filter by
    - **sort_by**: Sort order (price_asc, price_desc, rating, expiry, relevance)
    """
    try:
        # Initialize services
        deal_service = DealService(db)
        token_service = TokenService(db)
        
        # Check token balance and deduct search cost
        await token_service.check_and_deduct_tokens(
            user_id=current_user.id,
            amount=settings.TOKEN_SEARCH_COST,
            reason="deal_search"
        )
        
        # Build search filters
        filters = DealSearchFilters(
            min_price=min_price,
            max_price=max_price,
            categories=categories,
            brands=brands,
            condition=condition,
            sort_by=sort_by
        )
        
        # Perform search with caching and rate limiting
        deals = await deal_service.search_deals(
            query=query,
            limit=limit,
            filters=filters
        )
        
        return deals
        
    except TokenError as e:
        raise HTTPException(
            status_code=402,
            detail={"error": "Insufficient tokens", "message": str(e)}
        )
    except RateLimitExceededError as e:
        raise HTTPException(
            status_code=429,
            detail={"error": "Rate limit exceeded", "message": str(e)}
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "Invalid request", "message": str(e)}
        )
    except DealError as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "Deal search failed", "message": str(e)}
        )
    except Exception as e:
        logger.error(f"Unexpected error in search_deals: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={"error": "Internal server error", "message": "An unexpected error occurred"}
        )

@router.get("/{deal_id}", response_model=DealResponse)
async def get_deal(
    deal_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific deal.
    """
    try:
        deal_service = DealService(db)
        deal = await deal_service.get_deal(deal_id)
        
        if not deal:
            raise HTTPException(status_code=404, detail="Deal not found")
            
        return deal
        
    except DealError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/batch", response_model=List[DealResponse])
async def process_deals_batch(
    deals: List[DealCreate],
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Process multiple deals in batch with background tasks.
    """
    try:
        deal_service = DealService(db)
        processed_deals = await deal_service.process_deals_batch(deals, background_tasks)
        return processed_deals
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 