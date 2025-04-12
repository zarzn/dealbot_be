"""Market metrics service module.

This module provides functionality for tracking and recording market metrics
such as request counts, success rates, and response times.
"""

import logging
import time
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from core.models.enums import MarketType, MarketStatus
from core.repositories.market import MarketRepository
from core.utils.logger import get_logger

# Try to import settings from correct location
try:
    from core.config import get_settings
    settings = get_settings()
except ImportError:
    # Define fallback settings for MARKET_ERROR_THRESHOLD
    logger = get_logger(__name__)
    logger.warning("Could not import settings, using default values")
    class DefaultSettings:
        MARKET_ERROR_THRESHOLD = 10
    settings = DefaultSettings()

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

    async def record_market_metrics_batch(
        self, 
        metrics_batch: List[Dict[str, Any]]
    ) -> bool:
        """Record multiple market metrics in a single database transaction.
        
        Args:
            metrics_batch: List of metric data dictionaries with keys:
                - market_type: Type of the market (string)
                - success: Whether the request was successful (boolean)
                - response_time: Response time in seconds (float)
                - error: Error message if the request failed (string)
                
        Returns:
            bool: True if all metrics were recorded successfully, False otherwise
        """
        if not metrics_batch:
            return True
            
        try:
            # Group metrics by market type to reduce lookups
            metrics_by_market = {}
            for metric in metrics_batch:
                market_type = metric.get('market_type', 'unknown')
                if market_type not in metrics_by_market:
                    metrics_by_market[market_type] = []
                metrics_by_market[market_type].append(metric)
            
            # Process each market type in a single transaction
            for market_type_str, market_metrics in metrics_by_market.items():
                # Convert string market_type to MarketType enum
                try:
                    # Direct match attempt
                    market_enum = MarketType(market_type_str.lower())
                except ValueError:
                    # Try to find a matching enum by value
                    market_enum = None
                    for mt in MarketType:
                        if mt.value.lower() == market_type_str.lower():
                            market_enum = mt
                            break
                    
                    # If still not found, use a default
                    if market_enum is None:
                        logger.warning(f"Unknown market type: {market_type_str}, using AMAZON as fallback")
                        market_enum = MarketType.AMAZON
                
                # Get the market entity (just once per market type)
                markets = await self.market_repository.get_by_type(market_enum)
                
                # Check if markets is a list or a single Market object
                if isinstance(markets, list):
                    if not markets:
                        logger.warning(f"Cannot record metrics: Market with type {market_enum.value} not found")
                        continue
                    # Use the first market of this type
                    market = markets[0]
                else:
                    # Single market object was returned
                    market = markets
                
                # Calculate aggregated metrics for this market
                total_metrics = len(market_metrics)
                success_count = sum(1 for m in market_metrics if m.get('success', False))
                total_response_time = sum(m.get('response_time', 0) or 0 for m in market_metrics)
                avg_response_time = total_response_time / total_metrics if total_metrics > 0 else 0
                
                # Get the most recent error if any
                last_error = None
                for m in reversed(market_metrics):
                    if not m.get('success', True) and m.get('error'):
                        last_error = m.get('error')
                        break
                
                # Update market stats in a single operation
                try:
                    market.total_requests += total_metrics
                    market.requests_today += total_metrics
                    
                    if success_count > 0:
                        market.last_successful_request = datetime.now()
                    
                    # Update error stats if there were failures
                    error_count = total_metrics - success_count
                    if error_count > 0:
                        market.error_count += error_count
                        market.last_error = last_error
                        market.last_error_at = datetime.now()
                        
                        error_threshold = getattr(settings, 'MARKET_ERROR_THRESHOLD', 10)
                        if market.error_count >= error_threshold:
                            market.status = MarketStatus.ERROR.value
                            # Keep is_active true despite error status
                            market.is_active = True
                    
                    # Update average response time
                    if avg_response_time > 0:
                        # Recalculate the weighted average across all requests
                        market.avg_response_time = round(
                            ((market.avg_response_time * (market.total_requests - total_metrics) + 
                            total_response_time) / market.total_requests),
                            2
                        )
                    
                    # Update success rate
                    if market.total_requests > 0:
                        valid_error_count = max(0, min(market.error_count, market.total_requests))
                        success_rate_value = (market.total_requests - valid_error_count) / market.total_requests
                        market.success_rate = round(max(0.0, min(1.0, success_rate_value)), 2)
                    
                    # Check if rate limited
                    if market.requests_today >= market.rate_limit:
                        market.status = MarketStatus.RATE_LIMITED.value
                        # Keep is_active true despite rate limiting
                        market.is_active = True
                except Exception as e:
                    logger.error(f"Error updating market stats: {str(e)}")
            
            # Commit all changes in a single transaction
            await self.db.commit()
            logger.info(f"Successfully recorded batch of {len(metrics_batch)} market metrics")
            return True
            
        except Exception as e:
            logger.error(f"Error recording market metrics batch: {str(e)}")
            await self.db.rollback()
            return False 