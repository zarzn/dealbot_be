"""Background tasks for price monitoring and prediction updates."""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from uuid import UUID
import asyncio
from decimal import Decimal

from celery import shared_task
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.session import async_session
from core.models.price_tracking import PriceTracker, PricePoint
from core.models.price_prediction import PricePrediction
from core.services.price_tracking import PriceTrackingService
from core.services.price_prediction import PricePredictionService
from core.services.notifications import NotificationService
from core.integrations.markets.base.market_base import MarketBase
from core.utils.logger import get_logger
from core.exceptions.price import PriceTrackingError

logger = get_logger(__name__)

@shared_task(
    name="monitor_prices",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
    soft_time_limit=600
)
async def monitor_prices(self) -> None:
    """Monitor prices for all active trackers."""
    try:
        async with async_session() as session:
            # Get active trackers
            query = (
                select(PriceTracker)
                .where(PriceTracker.is_active == True)
                .where(
                    PriceTracker.last_check <= 
                    datetime.utcnow() - timedelta(seconds=PriceTracker.check_interval)
                )
            )
            
            result = await session.execute(query)
            trackers = result.scalars().all()
            
            if not trackers:
                logger.info("No active trackers need updating")
                return
                
            # Process trackers in batches
            batch_size = 20
            for i in range(0, len(trackers), batch_size):
                batch = trackers[i:i + batch_size]
                await process_tracker_batch(session, batch)
                
    except Exception as e:
        logger.error(f"Error in price monitoring task: {str(e)}")
        raise self.retry(exc=e)

@shared_task(
    name="update_predictions",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
    soft_time_limit=900
)
async def update_predictions(self) -> None:
    """Update price predictions for all active deals."""
    try:
        async with async_session() as session:
            # Get deals with predictions older than 24 hours
            cutoff = datetime.utcnow() - timedelta(hours=24)
            query = (
                select(PricePrediction)
                .where(PricePrediction.created_at <= cutoff)
                .order_by(PricePrediction.created_at.asc())
            )
            
            result = await session.execute(query)
            predictions = result.scalars().all()
            
            if not predictions:
                logger.info("No predictions need updating")
                return
                
            # Process predictions in batches
            batch_size = 10
            for i in range(0, len(predictions), batch_size):
                batch = predictions[i:i + batch_size]
                await process_prediction_batch(session, batch)
                
    except Exception as e:
        logger.error(f"Error in prediction update task: {str(e)}")
        raise self.retry(exc=e)

async def process_tracker_batch(
    session: AsyncSession,
    trackers: List[PriceTracker]
) -> None:
    """Process a batch of price trackers."""
    try:
        tracking_service = PriceTrackingService(session)
        notification_service = NotificationService()
        market_integrations: Dict[str, MarketBase] = {}  # Initialize with actual market integrations
        
        for tracker in trackers:
            try:
                # Get current price from market
                market = tracker.deal.source
                if market not in market_integrations:
                    # Initialize market integration
                    pass
                    
                market_client = market_integrations[market]
                current_price = await market_client.get_current_price(tracker.deal.url)
                
                if not current_price:
                    logger.warning(f"Could not get price for tracker {tracker.id}")
                    continue
                    
                # Create price point
                price_point = PricePoint(
                    deal_id=tracker.deal_id,
                    price=current_price,
                    source=market,
                    meta_data={
                        'tracker_id': tracker.id,
                        'check_time': datetime.utcnow().isoformat()
                    }
                )
                
                session.add(price_point)
                
                # Update tracker
                tracker.last_check = datetime.utcnow()
                
                # Check thresholds
                if tracker.threshold_price and current_price <= tracker.threshold_price:
                    await notification_service.send_notification({
                        'type': 'price_threshold_reached',
                        'user_id': tracker.user_id,
                        'deal_id': tracker.deal_id,
                        'tracker_id': tracker.id,
                        'threshold_price': float(tracker.threshold_price),
                        'current_price': float(current_price),
                        'timestamp': datetime.utcnow().isoformat()
                    })
                    
            except Exception as e:
                logger.error(f"Error processing tracker {tracker.id}: {str(e)}")
                continue
                
        await session.commit()
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Error processing tracker batch: {str(e)}")
        raise PriceTrackingError(f"Failed to process tracker batch: {str(e)}")

async def process_prediction_batch(
    session: AsyncSession,
    predictions: List[PricePrediction]
) -> None:
    """Process a batch of predictions that need updating."""
    try:
        prediction_service = PricePredictionService(session)
        notification_service = NotificationService()
        
        for prediction in predictions:
            try:
                # Generate new prediction
                new_prediction = await prediction_service.create_prediction(
                    prediction_data=PricePredictionCreate(
                        deal_id=prediction.deal_id,
                        prediction_days=prediction.prediction_days,
                        confidence_threshold=prediction.confidence_threshold,
                        model_params=prediction.model_params,
                        meta_data={
                            'previous_prediction_id': prediction.id,
                            'update_time': datetime.utcnow().isoformat()
                        }
                    ),
                    user_id=prediction.user_id
                )
                
                # Compare with previous prediction
                if should_notify_changes(prediction, new_prediction):
                    await notification_service.send_notification({
                        'type': 'prediction_update',
                        'user_id': prediction.user_id,
                        'deal_id': prediction.deal_id,
                        'prediction_id': new_prediction.id,
                        'changes': calculate_prediction_changes(prediction, new_prediction),
                        'timestamp': datetime.utcnow().isoformat()
                    })
                    
            except Exception as e:
                logger.error(f"Error updating prediction {prediction.id}: {str(e)}")
                continue
                
        await session.commit()
        
    except Exception as e:
        await session.rollback()
        logger.error(f"Error processing prediction batch: {str(e)}")
        raise PriceTrackingError(f"Failed to process prediction batch: {str(e)}")

def should_notify_changes(
    old_prediction: PricePrediction,
    new_prediction: PricePrediction,
    threshold: float = 0.1
) -> bool:
    """Determine if prediction changes are significant enough to notify."""
    try:
        # Compare trend direction
        if old_prediction.trend_direction != new_prediction.trend_direction:
            return True
            
        # Compare confidence
        if abs(old_prediction.overall_confidence - new_prediction.overall_confidence) > threshold:
            return True
            
        # Compare price predictions
        old_prices = [p['price'] for p in old_prediction.predictions]
        new_prices = [p['price'] for p in new_prediction.predictions]
        
        if len(old_prices) != len(new_prices):
            return True
            
        price_changes = [
            abs(old - new) / old
            for old, new in zip(old_prices, new_prices)
        ]
        
        return any(change > threshold for change in price_changes)
        
    except Exception as e:
        logger.error(f"Error checking prediction changes: {str(e)}")
        return False

def calculate_prediction_changes(
    old_prediction: PricePrediction,
    new_prediction: PricePrediction
) -> Dict[str, Any]:
    """Calculate changes between old and new predictions."""
    try:
        changes = {
            'trend_direction': {
                'old': old_prediction.trend_direction,
                'new': new_prediction.trend_direction,
                'changed': old_prediction.trend_direction != new_prediction.trend_direction
            },
            'confidence': {
                'old': float(old_prediction.overall_confidence),
                'new': float(new_prediction.overall_confidence),
                'change': float(
                    new_prediction.overall_confidence - old_prediction.overall_confidence
                )
            },
            'price_changes': []
        }
        
        # Compare individual predictions
        old_prices = old_prediction.predictions
        new_prices = new_prediction.predictions
        
        for i, (old, new) in enumerate(zip(old_prices, new_prices)):
            if old['date'] == new['date']:
                price_change = (new['price'] - old['price']) / old['price']
                changes['price_changes'].append({
                    'date': new['date'],
                    'old_price': float(old['price']),
                    'new_price': float(new['price']),
                    'change_percent': float(price_change * 100)
                })
                
        return changes
        
    except Exception as e:
        logger.error(f"Error calculating prediction changes: {str(e)}")
        return {
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }

# Schedule configuration (to be added to celery beat schedule)
SCHEDULE = {
    'monitor_prices': {
        'task': 'monitor_prices',
        'schedule': 60.0,  # Every minute
    },
    'update_predictions': {
        'task': 'update_predictions',
        'schedule': 3600.0,  # Every hour
    },
    'cleanup_old_data': {
        'task': 'cleanup_old_data',
        'schedule': 86400.0,  # Every day
    },
    'analyze_price_anomalies': {
        'task': 'analyze_price_anomalies',
        'schedule': 3600.0,  # Every hour
    },
} 