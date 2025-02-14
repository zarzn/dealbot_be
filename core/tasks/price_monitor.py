from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import asyncio
from celery.decorators import task
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from enum import Enum

from core.database import get_db
from core.models.deal import Deal
from core.models.goal import Goal
from core.services.market_search import MarketSearchService
from core.repositories.market import MarketRepository
from core.repositories.goal import GoalRepository
from core.utils.redis import RedisClient
from core.exceptions.base_exceptions import BaseException
from core.exceptions.deal_exceptions import DealValidationError
from core.utils.logger import get_logger

class DealStatus(str, Enum):
    """Deal status enum"""
    ACTIVE = "active"
    EXPIRED = "expired"
    INVALID = "invalid"

logger = get_logger(__name__)

@task(
    name="monitor_prices",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    rate_limit="100/h"
)
async def monitor_prices(self) -> None:
    """Monitor prices for all active goals and update deals accordingly"""
    try:
        async with get_db() as session:
            market_service = MarketSearchService(MarketRepository(session))
            goal_repo = GoalRepository(session)
            redis = RedisClient()

            # Get all active goals
            active_goals = await goal_repo.get_active_goals()
            
            for goal in active_goals:
                # Check if we've monitored this goal recently
                cache_key = f"price_monitor:goal:{goal.id}"
                if await redis.get(cache_key):
                    continue

                try:
                    # Search for current prices
                    current_deals = await market_service.search_products(
                        query=goal.search_query,
                        market_types=goal.market_types,
                        min_price=goal.min_price,
                        max_price=goal.max_price,
                        limit=10
                    )

                    # Process each deal
                    for deal_data in current_deals:
                        await process_deal(session, goal, deal_data)

                    # Update goal's last checked timestamp
                    await goal_repo.update_last_checked(goal.id)
                    
                    # Cache the monitoring timestamp
                    await redis.set(
                        cache_key,
                        datetime.utcnow().isoformat(),
                        ex=300  # 5 minutes
                    )

                except DealValidationError as e:
                    # Log the error but continue with other goals
                    logger.error(f"Error monitoring goal {goal.id}: {str(e)}")

    except (DealValidationError, BaseException) as e:
        # Retry the task with exponential backoff
        self.retry(exc=e)

async def process_deal(
    session: AsyncSession,
    goal: Goal,
    deal_data: Dict[str, Any]
) -> None:
    """Process a single deal for a goal"""
    try:
        # Check if deal already exists
        existing_deal = await session.execute(
            select(Deal).where(
                and_(
                    Deal.goal_id == goal.id,
                    Deal.external_id == deal_data["id"],
                    Deal.marketplace == deal_data["marketplace"]
                )
            )
        )
        deal = existing_deal.scalar_one_or_none()

        if deal:
            # Update existing deal
            old_price = deal.price
            new_price = float(deal_data["price"])
            
            # Calculate price change percentage
            price_change = ((new_price - old_price) / old_price) * 100
            
            # Update deal
            deal.price = new_price
            deal.price_history.append({
                "price": new_price,
                "timestamp": datetime.utcnow().isoformat()
            })
            deal.last_checked = datetime.utcnow()
            
            # Check if price meets notification criteria
            if abs(price_change) >= goal.price_alert_threshold:
                await create_price_alert(goal, deal, price_change)

        else:
            # Create new deal
            new_deal = Deal(
                goal_id=goal.id,
                external_id=deal_data["id"],
                marketplace=deal_data["marketplace"],
                title=deal_data["title"],
                description=deal_data.get("description", ""),
                price=float(deal_data["price"]),
                original_price=deal_data.get("original_price"),
                currency=deal_data.get("currency", "USD"),
                source=deal_data["source"],
                url=deal_data["url"],
                image_url=deal_data.get("image_url"),
                deal_metadata=deal_data.get("deal_metadata", {}),
                price_metadata=deal_data.get("price_metadata", {}),
                expires_at=deal_data.get("expires_at"),
                status=DealStatus.ACTIVE,
                price_history=[{
                    "price": float(deal_data["price"]),
                    "timestamp": datetime.utcnow().isoformat()
                }],
                created_at=datetime.utcnow(),
                last_checked=datetime.utcnow()
            )
            session.add(new_deal)

        await session.commit()

    except Exception as e:
        await session.rollback()
        raise DealValidationError(f"Error processing deal: {str(e)}")

async def create_price_alert(goal: Goal, deal: Deal, price_change: float) -> None:
    """Create a price alert notification"""
    from core.services.notification import NotificationService
    
    notification_service = NotificationService(session=None)  # Session not needed for notifications
    
    message = (
        f"Price {('increased' if price_change > 0 else 'decreased')} by "
        f"{abs(price_change):.2f}% for {deal.title}\n"
        f"New price: {deal.price} {deal.currency}\n"
        f"URL: {deal.url}"
    )
    
    await notification_service.send_notification(
        user_id=goal.user_id,
        title=f"Price Alert for {goal.title}",
        message=message,
        data={
            "goal_id": str(goal.id),
            "deal_id": str(deal.id),
            "price_change": price_change,
            "type": "price_alert"
        }
    )
