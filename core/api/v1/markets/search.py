"""Market search API module."""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Any, List
from uuid import UUID
from core.services.market_search import MarketSearchService
from core.services.token_service import TokenService
from core.api.v1.dependencies import get_current_user, get_market_search_service, get_token_service

router = APIRouter(tags=["market_search"])

@router.post("/search")
async def search_markets(
    query: str,
    market_search_service: MarketSearchService = Depends(get_market_search_service),
    token_service: TokenService = Depends(get_token_service),
    current_user=Depends(get_current_user)
) -> Any:
    """Search across all markets"""
    try:
        # Validate tokens before search
        await token_service.validate_operation(current_user.id, "global_market_search")
        
        results = await market_search_service.search_all_markets(query)
        
        # Deduct tokens for search request
        await token_service.deduct_tokens(
            current_user.id,
            "global_market_search"
        )
        
        return results
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{market_id}/search")
async def search_market(
    market_id: UUID,
    query: str,
    market_search_service: MarketSearchService = Depends(get_market_search_service),
    token_service: TokenService = Depends(get_token_service),
    current_user=Depends(get_current_user)
) -> Any:
    """Search specific market"""
    try:
        # Validate tokens before search
        await token_service.validate_operation(current_user.id, "market_search")
        
        results = await market_search_service.search(
            market_id=market_id,
            query=query
        )
        
        # Deduct tokens for search request
        await token_service.deduct_tokens(
            current_user.id,
            "market_search",
            market_id=market_id
        )
        
        return results
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/recent")
async def get_recent_searches(
    market_search_service: MarketSearchService = Depends(get_market_search_service),
    current_user=Depends(get_current_user)
) -> Any:
    """Get recent searches for the current user"""
    try:
        searches = await market_search_service.get_recent_searches(current_user.id)
        return searches
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) 