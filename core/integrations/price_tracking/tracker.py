"""Price tracking service for real-time price monitoring."""

from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
import asyncio
from uuid import UUID

from core.exceptions import PriceTrackingError
from core.utils.logger import get_logger
from core.utils.metrics import MetricsCollector
from core.models.deal import Deal
from core.services.notifications import NotificationService
from core.database.redis import RedisClient

logger = get_logger(__name__)

class PriceTracker:
    """Real-time price tracking service."""
    
    def __init__(
        self,
        notification_service: NotificationService,
        redis_client: RedisClient
    ):
        self.notification_service = notification_service
        self.redis_client = redis_client
        self.active_trackers: Dict[str, Dict[str, Any]] = {}
        self.price_thresholds: Dict[str, float] = {}
        self.tracking_task = None
        
    async def start_tracking(
        self,
        deal: Deal,
        threshold_price: Optional[float] = None,
        check_interval: int = 300  # 5 minutes
    ) -> Dict[str, Any]:
        """Start tracking price for a deal."""
        try:
            deal_id = str(deal.id)
            
            # Store tracking configuration
            tracking_config = {
                'deal_id': deal_id,
                'initial_price': float(deal.price),
                'threshold_price': threshold_price,
                'check_interval': check_interval,
                'last_check': datetime.utcnow(),
                'market': deal.source,
                'status': 'active'
            }
            
            # Save to Redis for persistence
            await self.redis_client.set(
                f"price_tracker:{deal_id}",
                tracking_config,
                ex=86400  # 24 hours
            )
            
            # Add to active trackers
            self.active_trackers[deal_id] = tracking_config
            
            if threshold_price:
                self.price_thresholds[deal_id] = threshold_price
                
            # Start tracking task if not running
            if not self.tracking_task:
                self.tracking_task = asyncio.create_task(
                    self._run_price_tracking()
                )
                
            logger.info(f"Started price tracking for deal {deal_id}")
            return tracking_config
            
        except Exception as e:
            logger.error(f"Error starting price tracking: {str(e)}")
            raise PriceTrackingError(f"Failed to start tracking: {str(e)}")
            
    async def stop_tracking(
        self,
        deal_id: str
    ) -> Dict[str, Any]:
        """Stop tracking price for a deal."""
        try:
            if deal_id not in self.active_trackers:
                raise PriceTrackingError(f"No active tracking for deal {deal_id}")
                
            # Update status
            self.active_trackers[deal_id]['status'] = 'stopped'
            
            # Remove from active tracking
            tracking_config = self.active_trackers.pop(deal_id)
            
            # Remove from Redis
            await self.redis_client.delete(f"price_tracker:{deal_id}")
            
            # Remove threshold if exists
            self.price_thresholds.pop(deal_id, None)
            
            logger.info(f"Stopped price tracking for deal {deal_id}")
            return tracking_config
            
        except Exception as e:
            logger.error(f"Error stopping price tracking: {str(e)}")
            raise PriceTrackingError(f"Failed to stop tracking: {str(e)}")
            
    async def update_threshold(
        self,
        deal_id: str,
        new_threshold: float
    ) -> Dict[str, Any]:
        """Update price threshold for a deal."""
        try:
            if deal_id not in self.active_trackers:
                raise PriceTrackingError(f"No active tracking for deal {deal_id}")
                
            # Update threshold
            self.price_thresholds[deal_id] = new_threshold
            self.active_trackers[deal_id]['threshold_price'] = new_threshold
            
            # Update in Redis
            await self.redis_client.set(
                f"price_tracker:{deal_id}",
                self.active_trackers[deal_id],
                ex=86400  # 24 hours
            )
            
            logger.info(
                f"Updated price threshold for deal {deal_id}: {new_threshold}"
            )
            return self.active_trackers[deal_id]
            
        except Exception as e:
            logger.error(f"Error updating threshold: {str(e)}")
            raise PriceTrackingError(f"Failed to update threshold: {str(e)}")
            
    async def get_tracking_status(
        self,
        deal_id: str
    ) -> Dict[str, Any]:
        """Get current tracking status for a deal."""
        try:
            if deal_id not in self.active_trackers:
                # Try to get from Redis
                config = await self.redis_client.get(f"price_tracker:{deal_id}")
                if not config:
                    raise PriceTrackingError(
                        f"No tracking information for deal {deal_id}"
                    )
                return config
                
            return self.active_trackers[deal_id]
            
        except Exception as e:
            logger.error(f"Error getting tracking status: {str(e)}")
            raise PriceTrackingError(
                f"Failed to get tracking status: {str(e)}"
            )
            
    async def _run_price_tracking(self):
        """Background task for price tracking."""
        try:
            while True:
                current_time = datetime.utcnow()
                
                # Get all active trackers
                for deal_id, config in self.active_trackers.items():
                    if config['status'] != 'active':
                        continue
                        
                    # Check if it's time to check price
                    last_check = config['last_check']
                    if (current_time - last_check).total_seconds() < config['check_interval']:
                        continue
                        
                    try:
                        # Get current price
                        current_price = await self._get_current_price(
                            deal_id,
                            config['market']
                        )
                        
                        # Check price changes
                        await self._handle_price_change(
                            deal_id,
                            config['initial_price'],
                            current_price,
                            config.get('threshold_price')
                        )
                        
                        # Update last check time
                        config['last_check'] = current_time
                        
                    except Exception as e:
                        logger.error(
                            f"Error checking price for deal {deal_id}: {str(e)}"
                        )
                        
                # Sleep for a short interval
                await asyncio.sleep(60)  # Check every minute
                
        except Exception as e:
            logger.error(f"Price tracking task error: {str(e)}")
            # Restart the task
            self.tracking_task = asyncio.create_task(
                self._run_price_tracking()
            )
            
    async def _get_current_price(
        self,
        deal_id: str,
        market: str
    ) -> float:
        """Get current price from the market."""
        try:
            # Implementation depends on market integration
            # This is a placeholder
            return 0.0
            
        except Exception as e:
            logger.error(f"Error getting current price: {str(e)}")
            raise PriceTrackingError(
                f"Failed to get current price: {str(e)}"
            )
            
    async def _handle_price_change(
        self,
        deal_id: str,
        initial_price: float,
        current_price: float,
        threshold_price: Optional[float]
    ):
        """Handle price changes and notifications."""
        try:
            price_change = current_price - initial_price
            price_change_percent = (price_change / initial_price) * 100
            
            # Record price change
            await self._record_price_change(
                deal_id,
                current_price,
                price_change_percent
            )
            
            # Check threshold
            if threshold_price and current_price <= threshold_price:
                await self._notify_threshold_reached(
                    deal_id,
                    current_price,
                    threshold_price
                )
                
            # Check significant changes (more than 5%)
            if abs(price_change_percent) >= 5:
                await self._notify_significant_change(
                    deal_id,
                    current_price,
                    price_change_percent
                )
                
        except Exception as e:
            logger.error(f"Error handling price change: {str(e)}")
            
    async def _record_price_change(
        self,
        deal_id: str,
        price: float,
        change_percent: float
    ):
        """Record price change in history."""
        try:
            price_point = {
                'price': price,
                'change_percent': change_percent,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Store in Redis with TTL
            await self.redis_client.rpush(
                f"price_history:{deal_id}",
                price_point
            )
            await self.redis_client.expire(
                f"price_history:{deal_id}",
                86400 * 30  # 30 days
            )
            
        except Exception as e:
            logger.error(f"Error recording price change: {str(e)}")
            
    async def _notify_threshold_reached(
        self,
        deal_id: str,
        current_price: float,
        threshold_price: float
    ):
        """Send notification when price threshold is reached."""
        try:
            notification_data = {
                'type': 'price_threshold_reached',
                'deal_id': deal_id,
                'current_price': current_price,
                'threshold_price': threshold_price,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            await self.notification_service.send_notification(
                notification_data
            )
            
        except Exception as e:
            logger.error(f"Error sending threshold notification: {str(e)}")
            
    async def _notify_significant_change(
        self,
        deal_id: str,
        current_price: float,
        change_percent: float
    ):
        """Send notification for significant price changes."""
        try:
            notification_data = {
                'type': 'significant_price_change',
                'deal_id': deal_id,
                'current_price': current_price,
                'change_percent': change_percent,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            await self.notification_service.send_notification(
                notification_data
            )
            
        except Exception as e:
            logger.error(f"Error sending change notification: {str(e)}") 