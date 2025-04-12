"""API dependencies."""

from typing import AsyncGenerator, Optional
from fastapi import Depends, BackgroundTasks, Request, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from core.database import get_async_db_session as get_db
from core.database import get_async_db_context
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
from core.services.redis import get_redis_service
from core.models.user import User
from core.dependencies import get_optional_user, oauth2_scheme
# Import get_optional_user as get_current_user_optional for compatibility
from core.dependencies import get_optional_user as get_current_user_optional

from core.repositories.market import MarketRepository
from core.repositories.deal import DealRepository
from core.repositories.goal import GoalRepository
from core.repositories.token import TokenRepository
from core.repositories.analytics import AnalyticsRepository
from core.config import settings

# Initialize logger
logger = logging.getLogger(__name__)

# Define get_db_session function before it's used
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get a database session using the async context manager.
    This properly manages connections and prevents leaks.
    """
    async with get_async_db_context() as session:
        yield session

# Make OAuth2 scheme with auto_error=False to make token optional
oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_PREFIX}/auth/login",
    auto_error=False
)

async def get_auth_service(
    db: AsyncSession = Depends(get_db_session),
    redis_service = Depends(get_redis_service)
) -> 'AuthService':
    """Get authentication service instance."""
    from core.services.auth import AuthService
    return AuthService(db, redis_service)

async def get_token_service(db: AsyncSession = Depends(get_db_session)) -> TokenService:
    """Get token service instance."""
    return SolanaTokenService(db)

async def get_goal_service(
    db: AsyncSession = Depends(get_db_session),
    token_service: TokenService = Depends(get_token_service),
    redis_service = Depends(get_redis_service)
) -> GoalService:
    """Get goal service instance."""
    return GoalService(session=db, redis_service=redis_service)

async def get_analytics_repository(
    db: AsyncSession = Depends(get_db_session)
) -> AnalyticsRepository:
    """Get analytics repository."""
    from core.repositories.analytics import AnalyticsRepository
    return AnalyticsRepository(db)

async def get_market_repository(
    db: AsyncSession = Depends(get_db_session)
) -> MarketRepository:
    """Get market repository."""
    from core.repositories.market import MarketRepository
    return MarketRepository(db)

async def get_deal_repository(
    db: AsyncSession = Depends(get_db_session)
) -> DealRepository:
    """Get deal repository."""
    from core.repositories.deal import DealRepository
    return DealRepository(db)

async def get_analytics_service(
    analytics_repository: AnalyticsRepository = Depends(get_analytics_repository),
    market_repository: MarketRepository = Depends(get_market_repository),
    deal_repository: DealRepository = Depends(get_deal_repository),
    goal_service: GoalService = Depends(get_goal_service)
) -> AnalyticsService:
    """Get analytics service."""
    return AnalyticsService(
        analytics_repository=analytics_repository,
        market_repository=market_repository,
        deal_repository=deal_repository,
        goal_service=goal_service
    )

async def get_market_service(db: AsyncSession = Depends(get_db_session)) -> MarketService:
    """Get market service instance."""
    return MarketService(MarketRepository(db))

async def get_deal_service(
    db: AsyncSession = Depends(get_db_session),
    current_user: Optional[User] = Depends(get_optional_user)
) -> DealService:
    """Get deal service instance."""
    service = DealService(session=db)
    await service.initialize()
    if current_user:
        service.set_current_user_id(current_user.id)
    return service

async def get_market_search_service(
    db: AsyncSession = Depends(get_db_session)
) -> MarketSearchService:
    """Get market search service instance."""
    from core.integrations.market_factory import MarketIntegrationFactory
    market_repository = MarketRepository(db)
    integration_factory = MarketIntegrationFactory(scraper_type="oxylabs", db=db)
    return MarketSearchService(market_repository=market_repository, integration_factory=integration_factory, db=db)

async def get_deal_analysis_service(
    db: AsyncSession = Depends(get_db_session),
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
    db: AsyncSession = Depends(get_db_session),
    deal_repository: DealRepository = Depends(lambda db=Depends(get_db_session): DealRepository(db)),
    goal_repository: GoalRepository = Depends(lambda db=Depends(get_db_session): GoalRepository(db))
) -> RecommendationService:
    """Get recommendation service instance."""
    return RecommendationService(
        db=db,
        deal_repository=deal_repository,
        goal_repository=goal_repository
    )

async def get_agent_service(
    db: AsyncSession = Depends(get_db_session),
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

# For backward compatibility, we keep get_db for now
from core.database import get_async_db_session as get_db
