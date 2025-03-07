from typing import AsyncGenerator, Optional
from fastapi import Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from core.database import AsyncSessionLocal
from core.models.user import User
from core.services.auth import AuthService
from core.services.token import TokenService
from core.services.analytics import AnalyticsService
from core.services.market import MarketService
from core.services.deal import DealService
from core.services.goal import GoalService
from core.services.market_search import MarketSearchService
from core.services.deal_analysis import DealAnalysisService
from core.config import settings
from core.exceptions import (
    AuthenticationError,
    TokenError,
    DatabaseError
)

from core.repositories.market import MarketRepository
from core.repositories.deal import DealRepository
from core.repositories.goal import GoalRepository
from core.repositories.token import TokenRepository
from core.repositories.analytics import AnalyticsRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_PREFIX}/auth/login")

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

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
    token_service: TokenService = Depends(get_token_service)
) -> GoalService:
    """Get goal service instance."""
    return GoalService(db=db, token_service=token_service)

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

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Decode JWT token
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
            
        # Get user directly from database
        from sqlalchemy import select
        from uuid import UUID
        stmt = select(User).where(User.id == UUID(user_id))
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user is None:
            raise credentials_exception
            
        return user
        
    except JWTError:
        raise credentials_exception
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

async def get_optional_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Get current user if authenticated, otherwise return None."""
    if not token:
        return None
        
    try:
        return await get_current_user(token, db)
    except HTTPException:
        return None

# Add an alias for backward compatibility
get_current_user_optional = get_optional_user

async def get_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current user and verify admin status."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges"
        )
    return current_user 