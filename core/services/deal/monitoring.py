"""Deal monitoring module.

This module provides functionality for monitoring deal health, metrics, and trends.
"""

import logging
import time
import copy
from typing import Dict, Any, List, Optional, Set, Tuple
from uuid import UUID
from decimal import Decimal
from datetime import datetime, timedelta
import json
import statistics
from collections import Counter
import asyncio

from core.exceptions import (
    ServiceError,
    ExternalServiceError,
    DealNotFoundError,
    InvalidDealDataError
)
from core.models.enums import DealStatus

logger = logging.getLogger(__name__)

# Constants
HEALTH_CHECK_INTERVAL = 3600  # 1 hour in seconds
METRICS_RETENTION_DAYS = 90  # Store metrics for 90 days
PRICE_DROP_THRESHOLD = 0.05  # 5% price drop to trigger notification
PRICE_CHECK_INTERVAL = 1800  # 30 minutes in seconds

async def get_deal_metrics(
    self,
    deal_id: Optional[UUID] = None,
    user_id: Optional[UUID] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """Get metrics for deals or a specific deal.
    
    Args:
        deal_id: Optional specific deal to get metrics for
        user_id: Optional user ID to filter metrics
        start_date: Optional start date for metrics range
        end_date: Optional end date for metrics range
        
    Returns:
        Dictionary with deal metrics
        
    Raises:
        MonitoringServiceError: If metrics retrieval fails
    """
    try:
        # Set default date range if not provided
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=30)  # Default to last 30 days
            
        # Calculate date range
        date_range = (end_date - start_date).days
        
        # Build Redis key based on parameters
        if deal_id:
            # For specific deal
            metrics_key = f"metrics:deal:{deal_id}"
            
            # Get metrics from Redis
            metrics_json = await self._redis_client.get(metrics_key)
            if not metrics_json:
                # No metrics found, get from database and calculate
                return await self._calculate_deal_metrics(deal_id, start_date, end_date)
                
            metrics = json.loads(metrics_json)
            
            # Filter by date range
            filtered_metrics = {
                k: v for k, v in metrics.items()
                if k == "id" or k == "title" or (
                    "date" in v and 
                    start_date <= datetime.fromisoformat(v["date"]) <= end_date
                )
            }
            
            return {
                "id": str(deal_id),
                "metrics": filtered_metrics,
                "date_range": date_range
            }
            
        else:
            # For all deals or user deals
            aggregated_metrics = {
                "view_count": 0,
                "unique_viewer_count": 0,
                "save_count": 0,
                "click_count": 0,
                "conversion_rate": 0,
                "avg_price": 0,
                "new_deals_count": 0,
                "expired_deals_count": 0,
                "by_category": {},
                "by_price_range": {},
                "by_status": {},
                "date_range": date_range
            }
            
            # Get deals to analyze
            query_params = {}
            if user_id:
                query_params["user_id"] = user_id
                
            deals = await self._repository.get_deals(**query_params)
            
            # Process each deal
            prices = []
            categories = Counter()
            statuses = Counter()
            price_ranges = {
                "0-10": 0,
                "10-50": 0,
                "50-100": 0,
                "100-500": 0,
                "500+": 0
            }
            
            for deal in deals:
                # Get deal metrics
                deal_metrics = await self._calculate_deal_metrics(deal.id, start_date, end_date)
                
                # Aggregate metrics
                aggregated_metrics["view_count"] += deal_metrics.get("view_count", 0)
                aggregated_metrics["unique_viewer_count"] += deal_metrics.get("unique_viewer_count", 0)
                aggregated_metrics["save_count"] += deal_metrics.get("save_count", 0)
                aggregated_metrics["click_count"] += deal_metrics.get("click_count", 0)
                
                # Track price for average calculation
                if deal.price:
                    prices.append(float(deal.price))
                    
                # Track category
                if deal.category:
                    categories[deal.category] += 1
                    
                # Track status
                if deal.status:
                    statuses[deal.status] += 1
                    
                # Track price range
                price_float = float(deal.price) if deal.price else 0
                if price_float < 10:
                    price_ranges["0-10"] += 1
                elif price_float < 50:
                    price_ranges["10-50"] += 1
                elif price_float < 100:
                    price_ranges["50-100"] += 1
                elif price_float < 500:
                    price_ranges["100-500"] += 1
                else:
                    price_ranges["500+"] += 1
                    
                # Check if deal was created in date range
                if deal.created_at and start_date <= deal.created_at <= end_date:
                    aggregated_metrics["new_deals_count"] += 1
                    
                # Check if deal expired in date range
                if deal.expires_at and start_date <= deal.expires_at <= end_date:
                    aggregated_metrics["expired_deals_count"] += 1
                    
            # Calculate averages and percentages
            if prices:
                aggregated_metrics["avg_price"] = sum(prices) / len(prices)
                
            if aggregated_metrics["view_count"] > 0:
                aggregated_metrics["conversion_rate"] = (aggregated_metrics["click_count"] / aggregated_metrics["view_count"]) * 100
                
            # Add category, status, and price range breakdowns
            aggregated_metrics["by_category"] = dict(categories)
            aggregated_metrics["by_status"] = dict(statuses)
            aggregated_metrics["by_price_range"] = price_ranges
            
            return aggregated_metrics
            
    except Exception as e:
        logger.error(f"Error getting deal metrics: {str(e)}")
        raise ServiceError(f"Failed to get deal metrics: {str(e)}")

async def track_deal_event(
    self, 
    deal_id: UUID,
    event_type: str,
    user_id: Optional[UUID] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Track a deal-related event.
    
    Args:
        deal_id: The deal ID
        event_type: Type of event (view, click, save, etc.)
        user_id: Optional user ID who performed the action
        metadata: Optional additional event data
        
    Returns:
        Dictionary with event tracking result
        
    Raises:
        MonitoringServiceError: If event tracking fails
    """
    try:
        # Get deal to ensure it exists
        deal = await self._repository.get_by_id(deal_id)
        if not deal:
            logger.warning(f"Attempted to track event for non-existent deal {deal_id}")
            return {"status": "error", "reason": "Deal not found"}
            
        # Create event data
        event_data = {
            "deal_id": str(deal_id),
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": str(user_id) if user_id else None,
            "metadata": metadata or {}
        }
        
        # Store in Redis
        event_key = f"event:{deal_id}:{int(time.time())}"
        await self._redis_client.set(event_key, json.dumps(event_data), ex=METRICS_RETENTION_DAYS * 86400)
        
        # Add to time series if applicable
        if event_type == "view":
            await self._redis_client.hincrby(f"metrics:deal:{deal_id}", "view_count", 1)
            
            # Track unique viewers
            if user_id:
                await self._redis_client.sadd(f"metrics:deal:{deal_id}:viewers", str(user_id))
                
        elif event_type == "click":
            await self._redis_client.hincrby(f"metrics:deal:{deal_id}", "click_count", 1)
            
        elif event_type == "save":
            await self._redis_client.hincrby(f"metrics:deal:{deal_id}", "save_count", 1)
            
        # Update global metrics
        today = datetime.utcnow().date().isoformat()
        await self._redis_client.hincrby(f"metrics:daily:{today}", f"count:{event_type}", 1)
        
        # Update category metrics if available
        if deal.category:
            await self._redis_client.hincrby(f"metrics:category:{deal.category}", f"count:{event_type}", 1)
            
        # Trigger deal health check if certain conditions met
        if event_type in ["view", "click"] and not await self._redis_client.get(f"health_check:{deal_id}:lock"):
            await self._redis_client.set(f"health_check:{deal_id}:lock", "1", ex=HEALTH_CHECK_INTERVAL)
            asyncio.create_task(self._check_deal_health(deal_id))
            
        return {
            "status": "tracked",
            "deal_id": str(deal_id),
            "event_type": event_type,
            "timestamp": event_data["timestamp"]
        }
        
    except Exception as e:
        logger.error(f"Error tracking deal event {event_type} for {deal_id}: {str(e)}")
        raise ServiceError(f"Failed to track deal event: {str(e)}")

async def get_deal_health(
    self,
    deal_id: UUID
) -> Dict[str, Any]:
    """Get health status of a deal.
    
    Args:
        deal_id: The deal ID
        
    Returns:
        Dictionary with deal health status
        
    Raises:
        MonitoringServiceError: If health check fails
    """
    try:
        # Get deal to ensure it exists
        deal = await self._repository.get_by_id(deal_id)
        if not deal:
            raise ServiceError(f"Deal {deal_id} not found")
            
        # Check if health data exists in Redis
        health_key = f"health:deal:{deal_id}"
        health_json = await self._redis_client.get(health_key)
        
        if health_json:
            # Return cached health data
            health_data = json.loads(health_json)
            return health_data
            
        # If no cached data, perform health check
        return await self._check_deal_health(deal_id)
        
    except ServiceError:
        raise
    except Exception as e:
        logger.error(f"Error getting deal health for {deal_id}: {str(e)}")
        raise ServiceError(f"Failed to get deal health: {str(e)}")

async def get_system_health(self) -> Dict[str, Any]:
    """Get overall system health metrics.
    
    Returns:
        Dictionary with system health metrics
        
    Raises:
        MonitoringServiceError: If system health check fails
    """
    try:
        # Get current time
        now = datetime.utcnow()
        today = now.date().isoformat()
        yesterday = (now - timedelta(days=1)).date().isoformat()
        
        # Get today's metrics
        today_metrics = await self._redis_client.hgetall(f"metrics:daily:{today}")
        if not today_metrics:
            today_metrics = {}
            
        # Get yesterday's metrics for comparison
        yesterday_metrics = await self._redis_client.hgetall(f"metrics:daily:{yesterday}")
        if not yesterday_metrics:
            yesterday_metrics = {}
            
        # Get active deals count
        active_deals_count = await self._repository.count_deals(status=DealStatus.ACTIVE.value)
        
        # Get total deals count
        total_deals_count = await self._repository.count_deals()
        
        # Get expired deals in last 24 hours
        expired_deals_count = await self._repository.count_deals(
            status=DealStatus.EXPIRED.value,
            modified_after=now - timedelta(days=1)
        )
        
        # Get new deals in last 24 hours
        new_deals_count = await self._repository.count_deals(
            created_after=now - timedelta(days=1)
        )
        
        # Calculate metrics
        view_count_today = int(today_metrics.get("count:view", 0))
        view_count_yesterday = int(yesterday_metrics.get("count:view", 0))
        view_count_change = 0
        if view_count_yesterday > 0:
            view_count_change = ((view_count_today - view_count_yesterday) / view_count_yesterday) * 100
            
        click_count_today = int(today_metrics.get("count:click", 0))
        click_count_yesterday = int(yesterday_metrics.get("count:click", 0))
        click_count_change = 0
        if click_count_yesterday > 0:
            click_count_change = ((click_count_today - click_count_yesterday) / click_count_yesterday) * 100
            
        # Build health data
        health_data = {
            "timestamp": now.isoformat(),
            "deals": {
                "total": total_deals_count,
                "active": active_deals_count,
                "new_last_24h": new_deals_count,
                "expired_last_24h": expired_deals_count
            },
            "metrics": {
                "views_today": view_count_today,
                "views_change": round(view_count_change, 2),
                "clicks_today": click_count_today,
                "clicks_change": round(click_count_change, 2),
                "conversion_rate": round(click_count_today / view_count_today * 100, 2) if view_count_today > 0 else 0
            },
            "status": "healthy",  # Default
            "issues": []
        }
        
        # Check for issues
        if active_deals_count < 10:
            health_data["status"] = "warning"
            health_data["issues"].append("Low number of active deals")
            
        if new_deals_count == 0:
            health_data["status"] = "warning"
            health_data["issues"].append("No new deals in last 24 hours")
            
        if view_count_change < -20:
            health_data["status"] = "warning"
            health_data["issues"].append("Significant drop in view count")
            
        if click_count_change < -20:
            health_data["status"] = "warning"
            health_data["issues"].append("Significant drop in click count")
            
        # Check Redis health
        try:
            redis_health = await self._redis_client.ping()
            health_data["services"] = {
                "redis": "healthy" if redis_health else "unhealthy"
            }
            
            if not redis_health:
                health_data["status"] = "unhealthy"
                health_data["issues"].append("Redis service is not responding")
        except Exception as e:
            health_data["services"] = {"redis": "unhealthy"}
            health_data["status"] = "unhealthy"
            health_data["issues"].append(f"Redis service error: {str(e)}")
            
        return health_data
        
    except Exception as e:
        logger.error(f"Error getting system health: {str(e)}")
        raise ServiceError(f"Failed to get system health: {str(e)}")

async def _check_deal_health(self, deal_id: UUID) -> Dict[str, Any]:
    """Check health of a specific deal.
    
    Args:
        deal_id: The deal ID
        
    Returns:
        Dictionary with deal health status
    """
    try:
        # Get deal from repository
        deal = await self._repository.get_by_id(deal_id)
        if not deal:
            logger.warning(f"Attempted to check health for non-existent deal {deal_id}")
            return {"status": "error", "reason": "Deal not found"}
            
        # Initialize health data
        health_data = {
            "deal_id": str(deal_id),
            "timestamp": datetime.utcnow().isoformat(),
            "status": "healthy",  # Default
            "issues": [],
            "metrics": {},
            "checks": {}
        }
        
        # Check URL availability
        url_valid = await self._validate_url(deal.url)
        health_data["checks"]["url_available"] = url_valid
        
        if not url_valid:
            health_data["status"] = "unhealthy"
            health_data["issues"].append("URL is unavailable")
            
        # Check expiration
        if deal.expires_at and deal.expires_at < datetime.utcnow():
            health_data["status"] = "expired"
            health_data["issues"].append("Deal has expired")
            health_data["checks"]["expired"] = True
        else:
            health_data["checks"]["expired"] = False
            
        # Check price consistency
        if deal.price and deal.original_price:
            if deal.price > deal.original_price:
                health_data["status"] = "warning"
                health_data["issues"].append("Current price is higher than original price")
                health_data["checks"]["price_consistent"] = False
            else:
                health_data["checks"]["price_consistent"] = True
                
        # Get metrics data
        view_count = int(await self._redis_client.hget(f"metrics:deal:{deal_id}", "view_count") or 0)
        click_count = int(await self._redis_client.hget(f"metrics:deal:{deal_id}", "click_count") or 0)
        save_count = int(await self._redis_client.hget(f"metrics:deal:{deal_id}", "save_count") or 0)
        
        # Get unique viewers count
        unique_viewers = await self._redis_client.scard(f"metrics:deal:{deal_id}:viewers") or 0
        
        # Calculate conversion rate
        conversion_rate = 0
        if view_count > 0:
            conversion_rate = (click_count / view_count) * 100
            
        # Add metrics to health data
        health_data["metrics"]["view_count"] = view_count
        health_data["metrics"]["unique_viewer_count"] = unique_viewers
        health_data["metrics"]["click_count"] = click_count
        health_data["metrics"]["save_count"] = save_count
        health_data["metrics"]["conversion_rate"] = round(conversion_rate, 2)
        
        # Check engagement metrics
        if view_count > 10 and conversion_rate < 1.0:
            health_data["status"] = "warning"
            health_data["issues"].append("Low conversion rate")
            
        # Check price changes
        price_history = await self.get_price_history(deal_id)
        if price_history and len(price_history["price_points"]) > 1:
            current_price = float(deal.price)
            price_points = [float(p["price"]) for p in price_history["price_points"]]
            
            # Check for price volatility
            if len(price_points) >= 3:
                price_std = statistics.stdev(price_points)
                price_mean = statistics.mean(price_points)
                price_volatility = price_std / price_mean if price_mean > 0 else 0
                
                health_data["metrics"]["price_volatility"] = round(price_volatility, 3)
                
                if price_volatility > 0.2:  # 20% volatility
                    health_data["status"] = "warning"
                    health_data["issues"].append("High price volatility detected")
                    
            # Check for price increases
            initial_price = price_points[0]
            if current_price > initial_price * 1.2:  # 20% increase
                health_data["status"] = "warning"
                health_data["issues"].append("Price has increased significantly since initial tracking")
                
        # Store health data in Redis with expiry
        health_key = f"health:deal:{deal_id}"
        await self._redis_client.set(health_key, json.dumps(health_data), ex=HEALTH_CHECK_INTERVAL)
        
        return health_data
        
    except Exception as e:
        logger.error(f"Error checking deal health for {deal_id}: {str(e)}")
        return {
            "deal_id": str(deal_id),
            "timestamp": datetime.utcnow().isoformat(),
            "status": "error",
            "issues": [f"Failed to check deal health: {str(e)}"]
        }

async def _calculate_deal_metrics(
    self,
    deal_id: UUID,
    start_date: datetime,
    end_date: datetime
) -> Dict[str, Any]:
    """Calculate metrics for a specific deal.
    
    Args:
        deal_id: The deal ID
        start_date: Start date for metrics range
        end_date: End date for metrics range
        
    Returns:
        Dictionary with calculated metrics
    """
    try:
        # Get deal from repository
        deal = await self._repository.get_by_id(deal_id)
        if not deal:
            logger.warning(f"Attempted to calculate metrics for non-existent deal {deal_id}")
            return {}
            
        # Get metrics from Redis
        view_count = int(await self._redis_client.hget(f"metrics:deal:{deal_id}", "view_count") or 0)
        click_count = int(await self._redis_client.hget(f"metrics:deal:{deal_id}", "click_count") or 0)
        save_count = int(await self._redis_client.hget(f"metrics:deal:{deal_id}", "save_count") or 0)
        
        # Get unique viewers count
        unique_viewers = await self._redis_client.scard(f"metrics:deal:{deal_id}:viewers") or 0
        
        # Get events within date range
        events = []
        keys = await self._redis_client.keys(f"event:{deal_id}:*")
        
        for key in keys:
            event_json = await self._redis_client.get(key)
            if event_json:
                event = json.loads(event_json)
                event_time = datetime.fromisoformat(event["timestamp"])
                
                if start_date <= event_time <= end_date:
                    events.append(event)
                    
        # Count events by type within date range
        event_counts = Counter([e["event_type"] for e in events])
        
        # Calculate metrics
        metrics = {
            "id": str(deal_id),
            "title": deal.title,
            "total_view_count": view_count,
            "total_click_count": click_count,
            "total_save_count": save_count,
            "unique_viewer_count": unique_viewers,
            "period_view_count": event_counts.get("view", 0),
            "period_click_count": event_counts.get("click", 0),
            "period_save_count": event_counts.get("save", 0),
            "conversion_rate": round((click_count / view_count * 100), 2) if view_count > 0 else 0,
            "date_range": (end_date - start_date).days
        }
        
        # Get price changes in period
        price_history = await self.get_price_history(
            deal_id, 
            start_date=start_date,
            end_date=end_date
        )
        
        if price_history and price_history["price_points"]:
            metrics["price_changes"] = len(price_history["price_points"])
            
            # Calculate price volatility if enough data points
            if len(price_history["price_points"]) >= 3:
                price_points = [float(p["price"]) for p in price_history["price_points"]]
                price_std = statistics.stdev(price_points)
                price_mean = statistics.mean(price_points)
                price_volatility = price_std / price_mean if price_mean > 0 else 0
                
                metrics["price_volatility"] = round(price_volatility, 3)
                metrics["avg_price"] = round(price_mean, 2)
                
        return metrics
        
    except Exception as e:
        logger.error(f"Error calculating deal metrics for {deal_id}: {str(e)}")
        return {}

async def refresh_deal(
    self,
    deal_id: UUID,
    update_price: bool = True,
    update_availability: bool = True,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """Refresh a deal's information from its source.
    
    Args:
        deal_id: The ID of the deal to refresh
        update_price: Whether to update price information
        update_availability: Whether to check if deal is still available
        force_refresh: Whether to force refresh even if recently refreshed
        
    Returns:
        Dictionary with refresh results
        
    Raises:
        DealNotFoundError: If deal not found
    """
    try:
        # Get deal from repository
        deal = await self._repository.get_by_id(deal_id)
        if not deal:
            raise DealNotFoundError(f"Deal {deal_id} not found")
            
        # Check if recently refreshed
        if not force_refresh:
            refresh_key = f"refresh:deal:{deal_id}"
            last_refresh = await self._redis_client.get(refresh_key)
            
            if last_refresh:
                return {
                    "deal_id": str(deal_id),
                    "status": "skipped",
                    "reason": "Recently refreshed"
                }
                
        # Convert deal to dictionary for easier manipulation
        deal_dict = self._deal_to_dict(deal)
        
        # Track what was updated
        updates = {}
        
        # Refresh based on source
        if deal.source == "amazon":
            # Refresh from Amazon API
            if hasattr(self, "amazon_api") and deal.source_id:
                try:
                    # Get product data
                    product_data = await self.amazon_api.get_product(deal.source_id)
                    
                    if product_data:
                        # Update price if needed
                        if update_price and product_data.get("price"):
                            new_price = Decimal(str(product_data["price"]))
                            old_price = deal.price
                            
                            if new_price != old_price:
                                updates["price"] = str(new_price)
                                deal_dict["price"] = new_price
                                
                                # Add price point to history
                                await self.add_price_point(deal_id, new_price, "amazon", datetime.utcnow())
                                
                                # Check if it was a price drop
                                if new_price < old_price:
                                    price_drop_pct = (old_price - new_price) / old_price
                                    if price_drop_pct >= PRICE_DROP_THRESHOLD:
                                        # Significant price drop, create notification
                                        asyncio.create_task(self._notify_price_drop(
                                            deal_id, 
                                            old_price, 
                                            new_price
                                        ))
                                        
                        # Update availability
                        if update_availability and "availability" in product_data:
                            available = product_data["availability"] == "IN_STOCK"
                            
                            if not available and deal.status == DealStatus.ACTIVE.value:
                                updates["status"] = DealStatus.UNAVAILABLE.value
                                deal_dict["status"] = DealStatus.UNAVAILABLE.value
                                
                except Exception as e:
                    logger.error(f"Error refreshing Amazon deal {deal_id}: {str(e)}")
                    return {
                        "deal_id": str(deal_id),
                        "status": "error",
                        "reason": f"Amazon API error: {str(e)}"
                    }
                    
        elif deal.source == "walmart":
            # Refresh from Walmart API
            if hasattr(self, "walmart_api") and deal.source_id:
                try:
                    # Get product data
                    product_data = await self.walmart_api.get_product(deal.source_id)
                    
                    if product_data:
                        # Update price if needed
                        if update_price and product_data.get("price"):
                            new_price = Decimal(str(product_data["price"]))
                            old_price = deal.price
                            
                            if new_price != old_price:
                                updates["price"] = str(new_price)
                                deal_dict["price"] = new_price
                                
                                # Add price point to history
                                await self.add_price_point(deal_id, new_price, "walmart", datetime.utcnow())
                                
                                # Check if it was a price drop
                                if new_price < old_price:
                                    price_drop_pct = (old_price - new_price) / old_price
                                    if price_drop_pct >= PRICE_DROP_THRESHOLD:
                                        # Significant price drop, create notification
                                        asyncio.create_task(self._notify_price_drop(
                                            deal_id, 
                                            old_price, 
                                            new_price
                                        ))
                                        
                        # Update availability
                        if update_availability and "availability" in product_data:
                            available = product_data["availability"]
                            
                            if not available and deal.status == DealStatus.ACTIVE.value:
                                updates["status"] = DealStatus.UNAVAILABLE.value
                                deal_dict["status"] = DealStatus.UNAVAILABLE.value
                                
                except Exception as e:
                    logger.error(f"Error refreshing Walmart deal {deal_id}: {str(e)}")
                    return {
                        "deal_id": str(deal_id),
                        "status": "error",
                        "reason": f"Walmart API error: {str(e)}"
                    }
                    
        elif deal.url:
            # Refresh by crawling URL
            if hasattr(self, "crawler") and deal.url:
                try:
                    # Crawl the page
                    crawl_result = await self.crawler.crawl_product_page(deal.url)
                    
                    if crawl_result:
                        # Update price if needed
                        if update_price and crawl_result.get("price"):
                            new_price = Decimal(str(crawl_result["price"]))
                            old_price = deal.price
                            
                            if new_price != old_price:
                                updates["price"] = str(new_price)
                                deal_dict["price"] = new_price
                                
                                # Add price point to history
                                await self.add_price_point(deal_id, new_price, "crawler", datetime.utcnow())
                                
                                # Check if it was a price drop
                                if new_price < old_price:
                                    price_drop_pct = (old_price - new_price) / old_price
                                    if price_drop_pct >= PRICE_DROP_THRESHOLD:
                                        # Significant price drop, create notification
                                        asyncio.create_task(self._notify_price_drop(
                                            deal_id, 
                                            old_price, 
                                            new_price
                                        ))
                                        
                        # Update availability
                        if update_availability and "availability" in crawl_result:
                            available = crawl_result["availability"]
                            
                            if not available and deal.status == DealStatus.ACTIVE.value:
                                updates["status"] = DealStatus.UNAVAILABLE.value
                                deal_dict["status"] = DealStatus.UNAVAILABLE.value
                                
                except Exception as e:
                    logger.error(f"Error crawling deal URL {deal.url}: {str(e)}")
                    return {
                        "deal_id": str(deal_id),
                        "status": "error",
                        "reason": f"Crawling error: {str(e)}"
                    }
                    
        # Update health status
        await self._check_deal_health(deal_id)
        
        # If there are updates, update the deal
        if updates:
            # Only update the fields that changed
            await self._repository.update(deal_id, updates)
            
            # Update cache
            await self._cache_deal(deal_id, deal_dict)
            
        # Set refresh timestamp
        refresh_key = f"refresh:deal:{deal_id}"
        await self._redis_client.set(refresh_key, datetime.utcnow().isoformat(), ex=PRICE_CHECK_INTERVAL)
        
        return {
            "deal_id": str(deal_id),
            "status": "refreshed" if updates else "unchanged",
            "updates": updates,
            "refresh_time": datetime.utcnow().isoformat()
        }
        
    except DealNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Error refreshing deal {deal_id}: {str(e)}")
        raise ServiceError(f"Failed to refresh deal: {str(e)}")

async def check_expired_deals(
    self,
    days_threshold: int = 30,
    limit: int = 100
) -> Dict[str, Any]:
    """Check and update expired deals.
    
    Args:
        days_threshold: Number of days to consider a deal old
        limit: Maximum number of deals to process
        
    Returns:
        Dictionary with expired deal count and IDs
    """
    try:
        now = datetime.utcnow()
        threshold_date = now - timedelta(days=days_threshold)
        
        # Find active deals with expiration dates in the past
        expired_deals = await self._repository.get_deals(
            status=DealStatus.ACTIVE.value,
            expires_before=now,
            limit=limit
        )
        
        # Find active deals older than threshold without explicit expiration
        old_deals = await self._repository.get_deals(
            status=DealStatus.ACTIVE.value,
            created_before=threshold_date,
            expires_at=None,  # No expiration date set
            limit=limit
        )
        
        # Combine the lists
        deals_to_check = expired_deals + old_deals
        
        # Process each deal
        expired_count = 0
        expired_deal_ids = []
        
        for deal in deals_to_check:
            # For deals with explicit expiration
            if deal.expires_at and deal.expires_at < now:
                # Update to expired status
                await self._repository.update(deal.id, {"status": DealStatus.EXPIRED.value})
                expired_count += 1
                expired_deal_ids.append(str(deal.id))
                continue
                
            # For old deals, check if still available
            if deal in old_deals:
                # Refresh the deal to check availability
                refresh_result = await self.refresh_deal(
                    deal.id,
                    update_price=True,
                    update_availability=True
                )
                
                # If the deal is no longer available, mark as expired
                if refresh_result.get("status") == "refreshed" and "status" in refresh_result.get("updates", {}):
                    if refresh_result["updates"]["status"] == DealStatus.UNAVAILABLE.value:
                        # Update to expired status
                        await self._repository.update(deal.id, {"status": DealStatus.EXPIRED.value})
                        expired_count += 1
                        expired_deal_ids.append(str(deal.id))
                        
        # Log the results
        if expired_count > 0:
            logger.info(f"Marked {expired_count} deals as expired")
            
        return {
            "expired_count": expired_count,
            "expired_deal_ids": expired_deal_ids
        }
        
    except Exception as e:
        logger.error(f"Error checking expired deals: {str(e)}")
        return {
            "expired_count": 0,
            "expired_deal_ids": [],
            "error": str(e)
        }

def _deal_to_dict(self, deal) -> Dict[str, Any]:
    """Convert a deal object to dictionary.
    
    Args:
        deal: Deal object
        
    Returns:
        Dictionary representation of the deal
    """
    if hasattr(deal, "__dict__"):
        return self._convert_deal_to_dict(deal)
    return deal  # Already a dict

def _convert_deal_to_dict(self, deal) -> Dict[str, Any]:
    """Convert a deal ORM object to a dictionary.
    
    Args:
        deal: Deal ORM object
        
    Returns:
        Dictionary with deal data
    """
    result = {}
    
    # Get all attributes
    for key in dir(deal):
        # Skip private and special attributes
        if key.startswith('_') or key in ('metadata', 'registry'):
            continue
            
        # Get the value
        value = getattr(deal, key)
        
        # Skip methods and callables
        if callable(value):
            continue
            
        # Handle special types
        if isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, UUID):
            result[key] = str(value)
        elif isinstance(value, Decimal):
            result[key] = str(value)
        else:
            result[key] = value
            
    return result

def _safe_copy_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a safe copy of a dictionary, handling special types.
    
    Args:
        data: Dictionary to copy
        
    Returns:
        Deep copy of the dictionary
    """
    # Handle special types during copy
    if not data:
        return {}
        
    # First, create a simple deep copy
    result = copy.deepcopy(data)
    
    # Handle special types
    for key, value in result.items():
        if isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, UUID):
            result[key] = str(value)
        elif isinstance(value, Decimal):
            result[key] = str(value)
            
    return result

async def _notify_price_drop(
    self,
    deal_id: UUID,
    old_price: Decimal,
    new_price: Decimal
) -> None:
    """Notify users about a significant price drop.
    
    Args:
        deal_id: The deal ID
        old_price: The previous price
        new_price: The new lower price
    """
    try:
        # Get deal details
        deal = await self._repository.get_by_id(deal_id)
        if not deal:
            logger.warning(f"Cannot notify price drop: deal {deal_id} not found")
            return
            
        # Calculate price drop percentage
        price_drop_pct = ((old_price - new_price) / old_price) * 100
        
        # Find interested users
        interested_users = await self._find_interested_users(deal)
        
        if not interested_users:
            logger.info(f"No users to notify about price drop for deal {deal_id}")
            return
            
        # Create notification data
        notification_data = {
            "type": "price_drop",
            "deal_id": str(deal_id),
            "title": deal.title,
            "old_price": str(old_price),
            "new_price": str(new_price),
            "price_drop_percent": round(price_drop_pct, 1),
            "image_url": deal.image_url,
            "url": deal.url
        }
        
        # Send notifications
        for user_id in interested_users:
            # Check if already notified recently
            notified_key = f"notified:user:{user_id}:price_drop:{deal_id}"
            already_notified = await self._redis_client.get(notified_key)
            
            if not already_notified:
                # Send notification
                if hasattr(self, "_notification_service"):
                    await self._notification_service.send_notification(
                        user_id=user_id,
                        notification_type="price_drop",
                        data=notification_data
                    )
                    
                # Set as notified with 1-day TTL
                await self._redis_client.set(notified_key, "1", ex=86400)
                
        logger.info(f"Notified {len(interested_users)} users about price drop for deal {deal_id}")
        
    except Exception as e:
        logger.error(f"Error notifying price drop for deal {deal_id}: {str(e)}") 