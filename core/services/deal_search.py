"""Deal search service.

This module provides functionality for searching deals based on
various criteria and filters.
"""

from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID
from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, asc
from sqlalchemy.sql import text
from sqlalchemy.sql.expression import null

from core.models.deal import Deal, DealSearch
from core.models.enums import DealStatus, DealSource, MarketCategory, MarketType
from core.repositories.deal import DealRepository
from core.models.market import Market
from core.logger import logger

class DealSearchService:
    """Service for searching deals."""

    def __init__(self, db: AsyncSession):
        """Initialize deal search service.
        
        Args:
            db: Database session
        """
        self.db = db
        self.repository = DealRepository(db)
    
    async def search_deals(
        self, 
        search_params: DealSearch,
        user_id: Optional[UUID] = None
    ) -> List[Deal]:
        """Search deals based on search parameters.
        
        Args:
            search_params: Search parameters
            user_id: Optional user ID to filter deals by user
            
        Returns:
            List of deals matching the search criteria
        """
        # Build query based on search parameters
        query = select(Deal)
        
        # Apply filters
        if search_params.query:
            # Perform text search on title and description
            search_term = f"%{search_params.query}%"
            query = query.filter(
                or_(
                    Deal.title.ilike(search_term),
                    Deal.description.ilike(search_term)
                )
            )
        
        if search_params.category:
            query = query.filter(Deal.category == search_params.category)
            
        if search_params.min_price is not None:
            query = query.filter(Deal.price >= Decimal(str(search_params.min_price)))
            
        if search_params.max_price is not None:
            query = query.filter(Deal.price <= Decimal(str(search_params.max_price)))
            
        if search_params.source:
            query = query.filter(Deal.source == search_params.source)
            
        if user_id:
            query = query.filter(Deal.user_id == user_id)
        
        # Only return active deals
        query = query.filter(Deal.status == DealStatus.ACTIVE.value)
        
        # Apply sorting
        if search_params.sort_by == "price":
            if search_params.sort_order == "asc":
                query = query.order_by(asc(Deal.price))
            else:
                query = query.order_by(desc(Deal.price))
        elif search_params.sort_by == "date":
            if search_params.sort_order == "asc":
                query = query.order_by(asc(Deal.found_at))
            else:
                query = query.order_by(desc(Deal.found_at))
        
        # Apply pagination
        query = query.offset(search_params.offset).limit(search_params.limit)
        
        # Execute query
        result = await self.db.execute(query)
        deals = result.scalars().all()
        
        return deals

    async def search(self, **kwargs) -> Dict[str, Any]:
        """Search deals based on the provided parameters.
        
        Args:
            **kwargs: Search parameters including:
                - query: Text to search for in deal title and description
                - category: Category to filter by
                - min_price: Minimum price
                - max_price: Maximum price
                - market_types: List of market types to include
                - sort_by: Field to sort by
                - sort_order: Sort order (asc or desc)
                - offset: Pagination offset
                - limit: Pagination limit
                
        Returns:
            Dict containing total count and matching deals
        """
        query, query_params = self._construct_search_query(**kwargs)
        
        # Execute search
        deals, total = await self._execute_search_query(
            query, 
            offset=kwargs.get('offset', 0),
            limit=kwargs.get('limit', 20)
        )
        
        return {
            "total": total,
            "deals": deals
        }

    def _construct_search_query(self, **kwargs) -> Tuple[Any, Dict[str, Any]]:
        """Construct the search query based on the provided parameters.
        
        Args:
            **kwargs: Search parameters
                
        Returns:
            Tuple of (query, query_params)
        """
        query = select(Deal)
        query_params = {}
        
        # Text search
        if query_text := kwargs.get('query'):
            query = query.where(
                or_(
                    Deal.title.ilike(f"%{query_text}%"),
                    Deal.description.ilike(f"%{query_text}%")
                )
            )
        
        # Category filter
        if category := kwargs.get('category'):
            query = query.where(Deal.category == category)
        
        # Price range
        if min_price := kwargs.get('min_price'):
            query = query.where(Deal.price >= min_price)
            query_params['min_price'] = min_price
            
        if max_price := kwargs.get('max_price'):
            query = query.where(Deal.price <= max_price)
            query_params['max_price'] = max_price
        
        # Market types
        if market_types := kwargs.get('market_types'):
            # Use a join to filter by market_id for the given market types
            query = query.join(Market, Deal.market_id == Market.id).where(Market.type.in_(market_types))
            query_params['market_types'] = market_types
        
        # Deal status
        if status := kwargs.get('status'):
            query = query.where(Deal.status == status)
        
        # Sorting
        sort_by = kwargs.get('sort_by', 'created_at')
        sort_order = kwargs.get('sort_order', 'desc')
        
        if sort_order.lower() == 'asc':
            query = query.order_by(asc(getattr(Deal, sort_by)))
        else:
            query = query.order_by(desc(getattr(Deal, sort_by)))
        
        return query, query_params
        
    async def _execute_search_query(self, query, offset=0, limit=20) -> Tuple[List[Dict[str, Any]], int]:
        """Execute the search query with pagination.
        
        Args:
            query: The query to execute
            offset: Pagination offset
            limit: Pagination limit
                
        Returns:
            Tuple of (deals, total_count)
        """
        # Count query - use a direct select count approach
        count_subquery = query.subquery()
        count_query = select(text("count(*)")).select_from(count_subquery)
        total = await self.db.scalar(count_query) or 0
        
        # Paginated result query
        result_query = query.offset(offset).limit(limit)
        result = await self.db.execute(result_query)
        
        # Convert results to dictionaries
        deals = []
        for deal in result.scalars().all():
            # Convert Deal object to dictionary
            deal_dict = {
                "id": str(deal.id),
                "title": deal.title,
                "description": deal.description,
                "price": float(deal.price) if deal.price else None,
                "category": deal.category,
                "source": deal.source,
                "status": deal.status,
                "market_id": str(deal.market_id) if deal.market_id else None,
                "user_id": str(deal.user_id) if deal.user_id else None,
                "created_at": deal.created_at.isoformat() if deal.created_at else None,
                "updated_at": deal.updated_at.isoformat() if deal.updated_at else None
            }
            deals.append(deal_dict)
        
        return deals, total
        
    async def save_search_history(self, user_id: str, query: str, **kwargs) -> None:
        """Save search history for a user.
        
        Args:
            user_id: User ID
            query: Search query text
            **kwargs: Additional search parameters
        """
        # Implementation for saving search history
        search_history = {
            "user_id": user_id,
            "query": query,
            "timestamp": datetime.utcnow(),
            "parameters": kwargs
        }
        
        # In a real implementation, we would save this to the database
        # For now, just log it
        return None

def get_deal_search_service(db: AsyncSession) -> DealSearchService:
    """Get deal search service instance.
    
    Args:
        db: Database session
        
    Returns:
        DealSearchService instance
    """
    return DealSearchService(db) 