"""Market metrics service module.

This module provides functionality for tracking and recording market metrics
such as request counts, success rates, and response times.
"""

import logging
import time
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.enums import MarketType
from core.repositories.market import MarketRepository
from core.utils.logger import get_logger

logger = get_logger(__name__)

class MarketMetricsService:
    """Service for tracking and recording market metrics."""

    def __init__(self, db: AsyncSession):
        """Initialize the market metrics service.
        
        Args:
            db: Database session for database operations
        """
        self.db = db
        self.market_repository = MarketRepository(db)
        
    async def record_market_request(
        self, 
        market_type: MarketType,
        success: bool = True,
        response_time: Optional[float] = None,
        error: Optional[str] = None
    ) -> bool:
        """Record metrics for a market request.
        
        Args:
            market_type: Type of the market (e.g., AMAZON, WALMART)
            success: Whether the request was successful
            response_time: Response time in seconds
            error: Error message if the request failed
            
        Returns:
            bool: True if the metric was recorded successfully, False otherwise
        """
        try:
            # Log the metrics
            log_prefix = f"Market request metrics [{market_type.value}]:"
            logger.debug(
                f"{log_prefix} success={success}, "
                f"response_time={response_time:.4f}s" if response_time else "N/A"
            )
            
            # Get the market entity
            markets = await self.market_repository.get_by_type(market_type)
            
            # Check if markets is a list or a single Market object
            if isinstance(markets, list):
                if not markets:
                    logger.warning(f"Cannot record metrics: Market with type {market_type.value} not found")
                    return False
                # Use the first market of this type
                market = markets[0]
            else:
                # Single market object was returned
                market = markets
                
            # Record the request on the market entity
            await market.record_request(
                db=self.db,
                success=success,
                response_time=response_time,
                error=error
            )
            
            # No need to commit changes here as the record_request method already does this
            return True
            
        except Exception as e:
            logger.error(f"Error recording market metrics: {str(e)}")
            # No need to rollback here as the record_request method handles transaction
            return False
    
    @classmethod
    async def create_and_record(
        cls,
        db: AsyncSession,
        market_type: MarketType,
        success: bool = True,
        response_time: Optional[float] = None,
        error: Optional[str] = None
    ) -> bool:
        """Create a service instance and record metrics in one call.
        
        This is a convenience method for one-off recording of metrics
        without maintaining a service instance.
        
        Args:
            db: Database session
            market_type: Type of the market
            success: Whether the request was successful
            response_time: Response time in seconds
            error: Error message if the request failed
            
        Returns:
            bool: True if the metric was recorded successfully, False otherwise
        """
        service = cls(db)
        return await service.record_market_request(
            market_type=market_type,
            success=success,
            response_time=response_time,
            error=error
        ) 