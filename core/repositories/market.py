from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_

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