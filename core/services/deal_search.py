"""Deal search service.

This module provides functionality for searching deals based on
various criteria and filters.
"""

from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, asc
from sqlalchemy.sql import text
from sqlalchemy.sql.expression import null

from core.models.deal import Deal, DealSearch
from core.models.enums import DealStatus, DealSource, MarketCategory
from core.repositories.deal import DealRepository

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

def get_deal_search_service(db: AsyncSession) -> DealSearchService:
    """Get deal search service instance.
    
    Args:
        db: Database session
        
    Returns:
        DealSearchService instance
    """
    return DealSearchService(db) 