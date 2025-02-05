"""API dependencies."""

from typing import AsyncGenerator, Optional
from fastapi import Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db_session as get_db
from core.services.token_service import TokenService
from core.services.analytics import AnalyticsService
from core.services.market import MarketService
from core.services.deal import DealService
from core.services.goal import GoalService
from core.services.market_search import MarketSearchService
from core.services.deal_analysis import DealAnalysisService
from core.services.auth import get_current_user, get_current_active_user

from core.repositories.market import MarketRepository
from core.repositories.deal import DealRepository
from core.repositories.goal import GoalRepository
from core.repositories.token import TokenRepository
from core.repositories.analytics import AnalyticsRepository

async def get_token_service(db: AsyncSession = Depends(get_db)) -> TokenService:
    """Get token service instance."""
    return TokenService(TokenRepository(db))

async def get_analytics_service(
    db: AsyncSession = Depends(get_db),
    market_repository: MarketRepository = Depends(lambda db=Depends(get_db): MarketRepository(db)),
    deal_repository: DealRepository = Depends(lambda db=Depends(get_db): DealRepository(db))
) -> AnalyticsService:
    """Get analytics service instance."""
    return AnalyticsService(
        AnalyticsRepository(db),
        market_repository,
        deal_repository
    )

async def get_market_service(db: AsyncSession = Depends(get_db)) -> MarketService:
    """Get market service instance."""
    return MarketService(MarketRepository(db))

async def get_deal_service(db: AsyncSession = Depends(get_db)) -> DealService:
    """Get deal service instance."""
    return DealService(DealRepository(db))

async def get_goal_service(
    db: AsyncSession = Depends(get_db),
    token_service: TokenService = Depends(get_token_service),
    background_tasks: Optional[BackgroundTasks] = None
) -> GoalService:
    """Get goal service instance."""
    return GoalService(
        db=db,
        token_service=token_service,
        background_tasks=background_tasks
    )

async def get_market_search_service(
    db: AsyncSession = Depends(get_db)
) -> MarketSearchService:
    """Get market search service instance."""
    return MarketSearchService(market_repository=MarketRepository(db))

async def get_deal_analysis_service(
    db: AsyncSession = Depends(get_db),
    market_service: MarketService = Depends(get_market_service),
    deal_service: DealService = Depends(get_deal_service)
) -> DealAnalysisService:
    """Get deal analysis service instance."""
    return DealAnalysisService(
        session=db,
        market_service=market_service,
        deal_service=deal_service
    )

__all__ = [
    'get_token_service',
    'get_analytics_service',
    'get_market_service',
    'get_deal_service',
    'get_goal_service',
    'get_market_search_service',
    'get_deal_analysis_service',
    'get_current_user',
    'get_current_active_user'
]
