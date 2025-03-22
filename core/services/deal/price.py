"""Deal price module.

This module provides functionality for deal price tracking and analysis.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
from datetime import datetime, timedelta
from decimal import Decimal

from core.models.deal import Deal, PriceHistory
from core.exceptions import (
    DealNotFoundError,
    ExternalServiceError
)

from .utils import log_exceptions

logger = logging.getLogger(__name__)

@log_exceptions
async def add_price_point(
    self, 
    deal_id: UUID, 
    price: Decimal, 
    source: str = "manual", 
    timestamp: Optional[datetime] = None
) -> Optional[PriceHistory]:
    """Add a price point to the price history of a deal.
    
    Args:
        deal_id: The ID of the deal
        price: The price to add
        source: The source of the price data
        timestamp: The timestamp of the price point (default: current time)
        
    Returns:
        The created price history entry
        
    Raises:
        DealNotFoundError: If deal not found
    """
    try:
        # Get the deal to check if it exists and get market info
        deal = await self._repository.get_by_id(deal_id)
        if not deal:
            raise DealNotFoundError(f"Deal {deal_id} not found")
            
        # Create timestamp if not provided
        if not timestamp:
            timestamp = datetime.utcnow()
            
        # Create price history entry
        price_history = PriceHistory(
            deal_id=deal_id,
            price=price,
            source=source,
            timestamp=timestamp
        )
        
        # Add to database
        self.db.add(price_history)
        await self.db.commit()
        await self.db.refresh(price_history)
        
        # Update deal if this is a new current price
        if price != deal.price:
            # Store old price in original_price if not already set
            # Only do this for the first price change
            deal_updates = {"price": price}
            if deal.original_price is None:
                deal_updates["original_price"] = deal.price
                
            # Also update price_metadata
            if not deal.price_metadata:
                deal.price_metadata = {}
            deal.price_metadata["last_updated"] = timestamp.isoformat()
            deal.price_metadata["price_change"] = {
                "old_price": str(deal.price),
                "new_price": str(price),
                "change": str(price - deal.price),
                "source": source
            }
            deal_updates["price_metadata"] = deal.price_metadata
            
            # Update the deal
            await self._repository.update(deal_id, deal_updates)
            
            # Clear cache
            if self._redis:
                await self._redis.delete(f"deal:{deal_id}:full")
                await self._redis.delete(f"deal:{deal_id}:basic")
                
        logger.info(f"Added price point {price} to deal {deal_id}")
        return price_history
        
    except DealNotFoundError:
        raise
    except Exception as e:
        await self.db.rollback()
        logger.error(f"Failed to add price point to deal {deal_id}: {str(e)}")
        raise ExternalServiceError(
            service="deal_service",
            operation="add_price_point",
            message=f"Failed to add price point: {str(e)}"
        )

async def get_price_history(
    self,
    deal_id: UUID,
    user_id: Optional[UUID] = None,
    start_date: Optional[datetime] = None,
    limit: int = 100
) -> Dict[str, Any]:
    """Get price history for a deal with optional date filtering.
    
    Args:
        deal_id: The ID of the deal
        user_id: Optional user ID for authorization
        start_date: Optional start date to filter history
        limit: Maximum number of price points to return
        
    Returns:
        Dictionary with price history data and metadata
        
    Raises:
        DealNotFoundError: If deal not found
        ExternalServiceError: If retrieval fails
    """
    try:
        # Get the deal to check if it exists
        deal = await self._repository.get_by_id(deal_id)
        if not deal:
            raise DealNotFoundError(f"Deal {deal_id} not found")
            
        # Try to get from cache first
        if self._redis:
            cache_key = f"deal:{deal_id}:price_history"
            if start_date:
                cache_key += f":{start_date.isoformat()}"
            cached_history = await self._redis.get(cache_key)
            if cached_history:
                try:
                    import json
                    return json.loads(cached_history)
                except Exception:
                    # If cache parsing fails, continue with database query
                    pass
                    
        # Build query for price history
        from sqlalchemy import select, desc
        
        query = select(PriceHistory).where(PriceHistory.deal_id == deal_id)
        
        # Apply date filter if provided
        if start_date:
            query = query.where(PriceHistory.timestamp >= start_date)
            
        # Apply ordering (newest first) and limit
        query = query.order_by(desc(PriceHistory.timestamp)).limit(limit)
        
        # Execute query
        result = await self.db.execute(query)
        price_points = result.scalars().all()
        
        # Convert to response format
        history = []
        for point in price_points:
            history.append({
                "id": str(point.id),
                "deal_id": str(point.deal_id),
                "price": str(point.price),
                "source": point.source,
                "timestamp": point.timestamp.isoformat() if point.timestamp else None
            })
            
        # Calculate some statistics
        stats = {}
        if history:
            prices = [Decimal(point["price"]) for point in history]
            stats["min_price"] = str(min(prices))
            stats["max_price"] = str(max(prices))
            stats["avg_price"] = str(sum(prices) / len(prices))
            stats["current_price"] = str(deal.price)
            
            if deal.original_price:
                stats["original_price"] = str(deal.original_price)
                # Calculate discount from original price
                if deal.price < deal.original_price:
                    discount = ((deal.original_price - deal.price) / deal.original_price) * 100
                    stats["discount_percentage"] = f"{discount:.2f}%"
            
            # Calculate price trend
            stats["trend"] = self._calculate_price_trend(history)
            
        # Prepare response
        response = {
            "deal_id": str(deal_id),
            "title": deal.title,
            "currency": deal.currency,
            "history": history,
            "stats": stats,
            "count": len(history),
            "filtered_from": start_date.isoformat() if start_date else None
        }
        
        # Cache the result
        if self._redis and response["history"]:
            try:
                import json
                cache_key = f"deal:{deal_id}:price_history"
                if start_date:
                    cache_key += f":{start_date.isoformat()}"
                    
                # Cache for 1 hour (3600 seconds)
                await self._redis.set(
                    cache_key, 
                    json.dumps(response), 
                    ex=3600
                )
            except Exception as e:
                logger.warning(f"Failed to cache price history: {str(e)}")
        
        return response
        
    except DealNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Failed to get price history for deal {deal_id}: {str(e)}")
        raise ExternalServiceError(
            service="deal_service",
            operation="get_price_history",
            message=f"Failed to get price history: {str(e)}"
        )

def _calculate_price_trend(self, price_history: List[Dict]) -> str:
    """Calculate price trend from price history.
    
    Args:
        price_history: List of price points
        
    Returns:
        String indicating trend: "rising", "falling", "stable", or "volatile"
    """
    if not price_history or len(price_history) < 2:
        return "unknown"  # Not enough data
        
    # Sort by timestamp (ascending)
    sorted_history = sorted(
        price_history,
        key=lambda x: x["timestamp"] if isinstance(x, dict) else x.timestamp
    )
    
    # Extract prices, ensuring they're Decimal objects
    prices = []
    for point in sorted_history:
        if isinstance(point, dict):
            try:
                prices.append(Decimal(point["price"]))
            except (KeyError, TypeError, ValueError):
                continue
        else:
            prices.append(point.price)
    
    if len(prices) < 2:
        return "unknown"
        
    # Calculate difference between consecutive prices
    diffs = [prices[i+1] - prices[i] for i in range(len(prices)-1)]
    
    # Calculate average price
    avg_price = sum(prices) / len(prices)
    
    # Calculate percentage changes
    pct_changes = [(diff / prices[i]) * 100 for i, diff in enumerate(diffs)]
    
    # Determine if changes are significant
    significant_changes = [abs(pct) > 1.0 for pct in pct_changes]  # >1% change is significant
    
    # Calculate directional consistency
    positive_changes = sum(1 for diff in diffs if diff > 0)
    negative_changes = sum(1 for diff in diffs if diff < 0)
    total_changes = len(diffs)
    
    # Criteria for trends
    if total_changes == 0:
        return "unknown"
    
    # If most changes are in the same direction
    if positive_changes / total_changes > 0.7:
        return "rising"
    if negative_changes / total_changes > 0.7:
        return "falling"
    
    # If price is relatively stable (small changes)
    if not any(significant_changes):
        return "stable"
        
    # Otherwise, the price is volatile
    return "volatile"

async def analyze_price_trends(self, deal_id: UUID) -> Dict[str, Any]:
    """Analyze price trends for a deal in depth.
    
    Args:
        deal_id: The ID of the deal to analyze
        
    Returns:
        Dictionary with trend analysis
        
    Raises:
        DealNotFoundError: If deal not found
        ExternalServiceError: If analysis fails
    """
    try:
        # Get price history for the deal
        history_response = await self.get_price_history(
            deal_id=deal_id,
            start_date=datetime.utcnow() - timedelta(days=90),  # Last 90 days
            limit=1000  # Get more data for better analysis
        )
        
        history = history_response.get("history", [])
        
        if not history or len(history) < 2:
            return {
                "deal_id": str(deal_id),
                "status": "insufficient_data",
                "message": "Not enough price history for trend analysis",
                "trends": {"trend": "unknown"}
            }
            
        # Sort by timestamp (ascending)
        sorted_history = sorted(history, key=lambda x: x["timestamp"])
        
        # Get basic trend
        trend = self._calculate_price_trend(sorted_history)
        
        # Extract prices and timestamps
        prices = []
        timestamps = []
        for point in sorted_history:
            try:
                prices.append(Decimal(point["price"]))
                timestamps.append(datetime.fromisoformat(point["timestamp"]))
            except (KeyError, TypeError, ValueError):
                continue
                
        # Calculate volatility (standard deviation as percentage of mean)
        from statistics import stdev, mean
        if len(prices) > 1:
            try:
                price_floats = [float(p) for p in prices]
                mean_price = mean(price_floats)
                std_dev = stdev(price_floats)
                volatility = (std_dev / mean_price) * 100 if mean_price > 0 else 0
            except Exception:
                volatility = 0
        else:
            volatility = 0
            
        # Calculate total percentage change
        if prices and len(prices) > 1:
            first_price = prices[0]
            last_price = prices[-1]
            if first_price > 0:
                total_change_pct = ((last_price - first_price) / first_price) * 100
            else:
                total_change_pct = 0
        else:
            total_change_pct = 0
            
        # Identify significant price drops (>5% drop from previous point)
        significant_drops = []
        for i in range(1, len(prices)):
            if prices[i-1] > 0 and ((prices[i-1] - prices[i]) / prices[i-1]) * 100 > 5:
                significant_drops.append({
                    "timestamp": timestamps[i].isoformat(),
                    "previous_price": str(prices[i-1]),
                    "new_price": str(prices[i]),
                    "drop_percentage": f"{((prices[i-1] - prices[i]) / prices[i-1]) * 100:.2f}%"
                })
                
        # Calculate price stability rating (0-10, higher is more stable)
        stability_rating = max(0, min(10, 10 - volatility))
                
        # Prepare trend analysis
        analysis = {
            "deal_id": str(deal_id),
            "status": "success",
            "data_points": len(prices),
            "period": {
                "start": timestamps[0].isoformat() if timestamps else None,
                "end": timestamps[-1].isoformat() if timestamps else None,
                "days": (timestamps[-1] - timestamps[0]).days if len(timestamps) > 1 else 0
            },
            "trends": {
                "trend": trend,
                "volatility": f"{volatility:.2f}%",
                "stability_rating": stability_rating,
                "total_change": f"{total_change_pct:.2f}%",
                "significant_drops": significant_drops
            },
            "statistics": history_response.get("stats", {})
        }
        
        # Add deal information
        deal = await self._repository.get_by_id(deal_id)
        if deal:
            analysis["deal"] = {
                "title": deal.title,
                "current_price": str(deal.price),
                "original_price": str(deal.original_price) if deal.original_price else None,
                "currency": deal.currency
            }
        
        return analysis
        
    except DealNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Failed to analyze price trends for deal {deal_id}: {str(e)}")
        raise ExternalServiceError(
            service="deal_service",
            operation="analyze_price_trends",
            message=f"Failed to analyze price trends: {str(e)}"
        ) 