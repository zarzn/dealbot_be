"""Price monitoring tasks."""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
import logging
from enum import Enum

from core.config import get_settings
from core.models.deal import Deal
from core.models.goal import Goal
from core.models.price_tracking import PricePoint
from core.services.market_search import MarketSearchService, get_current_price
from core.repositories.market import MarketRepository
from core.repositories.goal import GoalRepository
from core.utils.redis import RedisClient
from core.exceptions.base_exceptions import BaseError
from core.exceptions.deal_exceptions import DealValidationError
from core.utils.logger import get_logger
from core.celery import celery_app
from core.services.notification import NotificationService

class PriceMonitorError(BaseError):
    """Base error for price monitoring operations."""
    pass

class NetworkError(PriceMonitorError):
    """Error for network-related issues during price monitoring."""
    pass

class RateLimitError(PriceMonitorError):
    """Error when rate limits are exceeded."""
    pass

class DealStatus(str, Enum):
    """Deal status enum"""
    ACTIVE = "active"
    EXPIRED = "expired"
    INVALID = "invalid"

logger = get_logger(__name__)

# Create async engine and session factory
settings = get_settings()
engine = create_async_engine(str(settings.SQLALCHEMY_DATABASE_URI))
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_async_db() -> AsyncSession:
    """Get async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

@celery_app.task(name="monitor_prices_task")
def monitor_prices_task():
    """Celery task to monitor prices for all active deals."""
    try:
        # Create async session
        session = AsyncSessionLocal()
        
        # Get all active deals
        stmt = select(Deal).where(Deal.status == DealStatus.ACTIVE)
        deals = session.execute(stmt).scalars().all()
        
        if not deals:
            logger.info("No active deals to monitor")
            return
        
        # Monitor prices in batches
        deal_ids = [str(deal.id) for deal in deals]
        changes = monitor_price_changes(session, deal_ids)
        
        # Process price changes
        if changes:
            trigger_price_alerts(session, changes)
            
        logger.info(f"Price monitoring completed for {len(deal_ids)} deals")
        
    except Exception as e:
        logger.error(f"Error in price monitoring task: {str(e)}")
        raise PriceMonitorError(f"Price monitoring task failed: {str(e)}")
    finally:
        session.close()

async def monitor_price_changes(session: AsyncSession, deal_ids: List[str]) -> List[Dict[str, Any]]:
    """Monitor prices for specified deals and return price changes."""
    changes = []
    
    for deal_id in deal_ids:
        # Get deal
        stmt = select(Deal).where(Deal.id == deal_id)
        result = await session.execute(stmt)
        deal = result.scalar_one_or_none()
        
        if not deal:
            continue
        
        # Get current price
        try:
            current_price = await get_current_price(deal.url)
            old_price = deal.price
            
            if current_price != old_price:
                # Calculate price change
                price_change = current_price - old_price
                change_percentage = (price_change / old_price) * 100
                
                # Create price point
                price_point = PricePoint(
                    deal_id=deal_id,
                    price=current_price,
                    source=deal.source,
                    timestamp=datetime.utcnow()
                )
                session.add(price_point)
                
                # Update deal price
                deal.price = current_price
                deal.last_checked = datetime.utcnow()
                
                changes.append({
                    "deal_id": deal_id,
                    "old_price": old_price,
                    "new_price": current_price,
                    "price_change": price_change,
                    "change_percentage": change_percentage,
                    "is_increase": price_change > 0
                })
        
        except Exception as e:
            logger.error(f"Error monitoring deal {deal_id}: {str(e)}")
            continue
    
    await session.commit()
    return changes

async def update_price_history(
    session: AsyncSession,
    deal_id: str,
    new_price: Decimal,
    source: str
) -> PricePoint:
    """Update price history for a deal."""
    # Create new price point
    price_point = PricePoint(
        deal_id=deal_id,
        price=new_price,
        source=source,
        timestamp=datetime.utcnow()
    )
    session.add(price_point)
    await session.commit()
    return price_point

async def analyze_price_trends(session: AsyncSession, deal_id: str) -> Dict[str, Any]:
    """Analyze price trends for a deal."""
    # Get price history
    stmt = select(PricePoint).where(
        and_(
            PricePoint.deal_id == deal_id,
            PricePoint.timestamp >= datetime.utcnow() - timedelta(days=30)
        )
    ).order_by(PricePoint.timestamp)
    
    result = await session.execute(stmt)
    price_points = result.scalars().all()
    
    if not price_points:
        return {
            "deal_id": deal_id,
            "price_trend": "unknown",
            "total_drop": Decimal("0"),
            "drop_percentage": Decimal("0")
        }
    
    prices = [pp.price for pp in price_points]
    total_change = prices[-1] - prices[0]
    change_percentage = (total_change / prices[0]) * 100
    
    trend = "stable"
    if change_percentage <= -5:
        trend = "decreasing"
    elif change_percentage >= 5:
        trend = "increasing"
    
    return {
        "deal_id": deal_id,
        "price_trend": trend,
        "total_drop": abs(total_change) if total_change < 0 else Decimal("0"),
        "drop_percentage": abs(change_percentage) if total_change < 0 else Decimal("0")
    }

async def trigger_price_alerts(session: AsyncSession, price_changes: List[Dict[str, Any]]) -> None:
    """Trigger price alerts for price changes."""
    notification_service = NotificationService(session)
    
    for change in price_changes:
        # Get deal and goal
        stmt = select(Deal).where(Deal.id == change["deal_id"])
        result = await session.execute(stmt)
        deal = result.scalar_one_or_none()
        
        if not deal or not deal.goal_id:
            continue
        
        stmt = select(Goal).where(Goal.id == deal.goal_id)
        result = await session.execute(stmt)
        goal = result.scalar_one_or_none()
        
        if not goal:
            continue
        
        # Check if change exceeds notification threshold
        if abs(change["change_percentage"]) >= goal.notification_threshold:
            message = (
                f"Price {('increased' if change['is_increase'] else 'decreased')} by "
                f"{abs(change['change_percentage']):.2f}% for {deal.title}\n"
                f"New price: {change['new_price']} {deal.currency}\n"
                f"URL: {deal.url}"
            )
            
            await notification_service.create_notification(
                user_id=goal.user_id,
                title=f"Price Alert for {goal.title}",
                message=message,
                notification_type="price_alert",
                priority="high" if abs(change["change_percentage"]) >= 20 else "medium",
                metadata={
                    "goal_id": str(goal.id),
                    "deal_id": str(deal.id),
                    "price_change": float(change["change_percentage"]),
                    "type": "price_alert"
                }
            )
            
            # Check for auto-buy trigger
            if (
                goal.auto_buy_threshold and 
                not change["is_increase"] and 
                abs(change["change_percentage"]) >= goal.auto_buy_threshold
            ):
                await trigger_auto_buy(session, deal.id, str(goal.id))

async def trigger_auto_buy(session: AsyncSession, deal_id: str, goal_id: str) -> None:
    """Trigger auto-buy for a deal."""
    # This is a placeholder for the actual auto-buy implementation
    logger.info(f"Auto-buy triggered for deal {deal_id} from goal {goal_id}")
    # Implement actual auto-buy logic here

async def process_deal(session: AsyncSession, deal_id: str) -> Dict[str, Any]:
    """Process a single deal for price monitoring and analysis.
    
    Args:
        session: Database session
        deal_id: Deal ID to process
        
    Returns:
        Dict containing processing results
    """
    try:
        # Get deal
        stmt = select(Deal).where(Deal.id == deal_id)
        result = await session.execute(stmt)
        deal = result.scalar_one_or_none()
        
        if not deal:
            raise DealValidationError(f"Deal not found: {deal_id}")
            
        # Get current price
        current_price = await get_current_price(deal.url)
        old_price = deal.price
        
        # Update price history
        await update_price_history(
            session=session,
            deal_id=deal_id,
            new_price=current_price,
            source=deal.source
        )
        
        # Analyze price trends
        trends = await analyze_price_trends(session, deal_id)
        
        # Calculate changes
        price_change = current_price - old_price
        change_percentage = (price_change / old_price) * 100 if old_price else 0
        
        # Update deal
        deal.price = current_price
        deal.last_checked = datetime.utcnow()
        await session.commit()
        
        return {
            "deal_id": deal_id,
            "old_price": old_price,
            "new_price": current_price,
            "price_change": price_change,
            "change_percentage": change_percentage,
            "is_increase": price_change > 0,
            "trends": trends
        }
        
    except Exception as e:
        logger.error(f"Error processing deal {deal_id}: {str(e)}")
        raise PriceMonitorError(f"Deal processing failed: {str(e)}")

async def create_price_alert(
    session: AsyncSession,
    deal_id: str,
    price_change: Dict[str, Any]
) -> None:
    """Create a price alert for significant price changes.
    
    Args:
        session: Database session
        deal_id: Deal ID
        price_change: Price change information
    """
    try:
        # Get deal and goal
        stmt = select(Deal).where(Deal.id == deal_id)
        result = await session.execute(stmt)
        deal = result.scalar_one_or_none()
        
        if not deal or not deal.goal_id:
            return
            
        stmt = select(Goal).where(Goal.id == deal.goal_id)
        result = await session.execute(stmt)
        goal = result.scalar_one_or_none()
        
        if not goal:
            return
            
        # Check notification threshold
        if abs(price_change["change_percentage"]) >= goal.notification_threshold:
            notification_service = NotificationService(session)
            
            message = (
                f"Price {('increased' if price_change['is_increase'] else 'decreased')} by "
                f"{abs(price_change['change_percentage']):.2f}% for {deal.title}\n"
                f"New price: {price_change['new_price']} {deal.currency}\n"
                f"URL: {deal.url}"
            )
            
            await notification_service.create_notification(
                user_id=goal.user_id,
                title=f"Price Alert for {goal.title}",
                message=message,
                notification_type="price_alert",
                priority="high" if abs(price_change["change_percentage"]) >= 20 else "medium",
                metadata={
                    "goal_id": str(goal.id),
                    "deal_id": str(deal.id),
                    "price_change": float(price_change["change_percentage"]),
                    "type": "price_alert"
                }
            )
            
            # Check auto-buy threshold
            if (
                goal.auto_buy_threshold and 
                not price_change["is_increase"] and 
                abs(price_change["change_percentage"]) >= goal.auto_buy_threshold
            ):
                await trigger_auto_buy(session, deal_id, str(goal.id))
                
    except Exception as e:
        logger.error(f"Error creating price alert for deal {deal_id}: {str(e)}")
        raise PriceMonitorError(f"Failed to create price alert: {str(e)}")
