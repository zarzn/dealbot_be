from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_, func
from datetime import datetime, timedelta

from ..models.market import Market, MarketCreate, MarketUpdate, MarketType, MarketStatus

class MarketRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, market_data: MarketCreate) -> Market:
        market = Market(**market_data.model_dump())
        self.session.add(market)
        await self.session.commit()
        await self.session.refresh(market)
        return market

    async def get_by_id(self, market_id: UUID) -> Optional[Market]:
        result = await self.session.execute(
            select(Market).where(
                and_(
                    Market.id == market_id,
                    Market.is_active == True
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_by_type(self, market_type: MarketType) -> Optional[Market]:
        result = await self.session.execute(
            select(Market).where(
                and_(
                    Market.type == market_type,
                    Market.is_active == True
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_all_active(self) -> List[Market]:
        result = await self.session.execute(
            select(Market).where(
                and_(
                    Market.is_active == True,
                    Market.status == MarketStatus.ACTIVE
                )
            )
        )
        return list(result.scalars().all())

    async def update(self, market_id: UUID, market_data: MarketUpdate) -> Optional[Market]:
        update_data = {k: v for k, v in market_data.model_dump().items() if v is not None}
        if not update_data:
            return await self.get_by_id(market_id)

        await self.session.execute(
            update(Market)
            .where(Market.id == market_id)
            .values(**update_data)
        )
        await self.session.commit()
        return await self.get_by_id(market_id)

    async def delete(self, market_id: UUID) -> bool:
        market = await self.get_by_id(market_id)
        if not market:
            return False
        
        await self.session.execute(
            update(Market)
            .where(Market.id == market_id)
            .values(is_active=False)
        )
        await self.session.commit()
        return True

    async def get_all(self) -> List[Market]:
        result = await self.session.execute(
            select(Market).where(Market.is_active == True)
        )
        return list(result.scalars().all())

    async def update_market_stats(self, market_id: UUID, success: bool, response_time: float) -> None:
        """Update market statistics after a request."""
        market = await self.get_by_id(market_id)
        if not market:
            return

        # Calculate new success rate
        total_requests = market.total_requests + 1
        success_count = int(market.success_rate * market.total_requests) + (1 if success else 0)
        new_success_rate = success_count / total_requests

        # Calculate new average response time
        new_avg_response_time = (
            (market.avg_response_time * market.total_requests + response_time) / total_requests
        )

        update_data = {
            "total_requests": total_requests,
            "requests_today": market.requests_today + 1,
            "success_rate": new_success_rate,
            "avg_response_time": new_avg_response_time,
            "last_successful_request": None if not success else func.now()
        }

        if not success:
            update_data.update({
                "error_count": market.error_count + 1,
                "last_error_at": func.now()
            })

        await self.session.execute(
            update(Market)
            .where(Market.id == market_id)
            .values(**update_data)
        )
        await self.session.commit()

    async def reset_daily_stats(self) -> None:
        """Reset daily statistics for all markets."""
        await self.session.execute(
            update(Market)
            .where(Market.is_active == True)
            .values(
                requests_today=0,
                error_count=0,
                last_reset_at=func.now()
            )
        )
        await self.session.commit()

    async def get_market_stats(self, market_id: UUID) -> Optional[Market]:
        """Get detailed statistics for a specific market."""
        result = await self.session.execute(
            select(Market)
            .where(
                and_(
                    Market.id == market_id,
                    Market.is_active == True
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_markets_by_performance(self, limit: int = 10) -> List[Market]:
        """Get top performing markets based on success rate and response time."""
        result = await self.session.execute(
            select(Market)
            .where(Market.is_active == True)
            .order_by(
                Market.success_rate.desc(),
                Market.avg_response_time.asc()
            )
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_markets_by_status(self, status: MarketStatus) -> List[Market]:
        """Get markets by their operational status."""
        result = await self.session.execute(
            select(Market)
            .where(
                and_(
                    Market.status == status,
                    Market.is_active == True
                )
            )
        )
        return list(result.scalars().all())

    async def update_market_status(self, market_id: UUID, status: MarketStatus) -> Optional[Market]:
        """Update market operational status."""
        await self.session.execute(
            update(Market)
            .where(Market.id == market_id)
            .values(status=status)
        )
        await self.session.commit()
        return await self.get_by_id(market_id)

    async def get_markets_with_high_error_rate(self, threshold: float = 0.1) -> List[Market]:
        """Get markets with error rate above threshold."""
        result = await self.session.execute(
            select(Market)
            .where(
                and_(
                    Market.is_active == True,
                    Market.success_rate < (1 - threshold)
                )
            )
        )
        return list(result.scalars().all())

    async def get_markets_by_request_volume(self, min_requests: int = 1000) -> List[Market]:
        """Get markets with high request volume."""
        result = await self.session.execute(
            select(Market)
            .where(
                and_(
                    Market.is_active == True,
                    Market.total_requests >= min_requests
                )
            )
            .order_by(Market.total_requests.desc())
        )
        return list(result.scalars().all()) 