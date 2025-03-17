"""API dependencies."""

from typing import AsyncGenerator, Optional
from fastapi import Depends, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from core.database import get_async_db_session as get_db
from core.services.token import TokenService, SolanaTokenService
from core.services.analytics import AnalyticsService
from core.services.market import MarketService
from core.services.deal import DealService
from core.services.goal import GoalService
from core.services.market_search import MarketSearchService
from core.services.deal_analysis import DealAnalysisService
from core.services.auth import get_current_user, get_current_active_user
from core.services.agent import AgentService
from core.services.recommendation import RecommendationService
from core.models.user import User
from core.dependencies import get_optional_user, oauth2_scheme

from core.repositories.market import MarketRepository
from core.repositories.deal import DealRepository
from core.repositories.goal import GoalRepository
from core.repositories.token import TokenRepository
from core.repositories.analytics import AnalyticsRepository

# Initialize logger
logger = logging.getLogger(__name__)

async def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Get current user if authenticated, otherwise return None."""
    logger.debug(f"get_current_user_optional called with token: {'Present' if token else 'None'}")
    
    # Handle the case where token is None (no Authorization header)
    if not token:
        return None
    
    # Pass the token to get_optional_user
    return await get_optional_user(token, db)

async def get_token_service(db: AsyncSession = Depends(get_db)) -> TokenService:
    """Get token service instance."""
    return SolanaTokenService(db)

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
    service = DealService(session=db)
    await service.initialize()
    return service

async def get_goal_service(
    db: AsyncSession = Depends(get_db),
    token_service: TokenService = Depends(get_token_service)
) -> GoalService:
    """Get goal service instance."""
    return GoalService(session=db)

async def get_market_search_service(
    db: AsyncSession = Depends(get_db)
) -> MarketSearchService:
    """Get market search service instance."""
    return MarketSearchService(db)

async def get_deal_analysis_service(
    db: AsyncSession = Depends(get_db),
    market_service: MarketService = Depends(get_market_service),
    deal_service: DealService = Depends(get_deal_service)
) -> DealAnalysisService:
    """Get deal analysis service instance."""
    return DealAnalysisService(
        db,
        market_service,
        deal_service
    )

async def get_recommendation_service(
    db: AsyncSession = Depends(get_db),
    deal_repository: DealRepository = Depends(lambda db=Depends(get_db): DealRepository(db)),
    goal_repository: GoalRepository = Depends(lambda db=Depends(get_db): GoalRepository(db))
) -> RecommendationService:
    """Get recommendation service instance."""
    return RecommendationService(
        db=db,
        deal_repository=deal_repository,
        goal_repository=goal_repository
    )

async def get_agent_service(
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = None
) -> AgentService:
    """Get agent service instance.
    
    Args:
        db: Database session
        background_tasks: FastAPI background tasks
        
    Returns:
        AgentService: Agent service instance
    """
    service = AgentService(db)
    if background_tasks:
        service.set_background_tasks(background_tasks)
    return service 