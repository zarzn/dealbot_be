from typing import AsyncGenerator, Optional
from fastapi import Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt, ExpiredSignatureError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
import os
import logging
import uuid

from core.database import AsyncSessionLocal
from core.models.user import User
from core.services.auth import AuthService, get_jwt_secret_key, create_mock_user_for_test
from core.services.token import TokenService
from core.services.analytics import AnalyticsService
from core.services.market import MarketService
from core.services.deal import DealService
from core.services.goal import GoalService
from core.services.market_search import MarketSearchService
from core.services.deal_analysis import DealAnalysisService
from core.services.redis import get_redis_service
from core.config import settings, Settings
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

# Initialize logger
logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_PREFIX}/auth/login")

# Make sure OAuth2PasswordBearer is properly configured to make the token optional
oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_PREFIX}/auth/login", 
    auto_error=False
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def get_settings() -> Settings:
    """Get application settings."""
    return settings

async def get_token_service(db: AsyncSession = Depends(get_db)) -> TokenService:
    """Get token service instance."""
    return TokenService(TokenRepository(db))

async def get_auth_service(
    db: AsyncSession = Depends(get_db),
    redis_service = Depends(get_redis_service)
) -> AuthService:
    """Get authentication service instance."""
    return AuthService(db, redis_service)

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
    session: AsyncSession = Depends(get_db),
    redis_service = Depends(get_redis_service)
) -> GoalService:
    """Get goal service instance."""
    return GoalService(session=session, redis_service=redis_service)

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
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
) -> User:
    """Get the current user based on the JWT token.
    
    Args:
        token: The JWT token
        db: The database session
        auth_service: The authentication service
        settings: The application settings
        
    Returns:
        The current user
        
    Raises:
        HTTPException: If the token is invalid or the user is not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Handle emergency token for test environment
        if settings.TESTING and token == "test-environment-emergency-token":
            # Try to get the test user from the database first
            try:
                stmt = select(User).where(User.email == "test@test.com")
                result = await db.execute(stmt)
                test_user = result.scalar_one_or_none()
                
                if test_user:
                    logger.info("Using test user from database for emergency token")
                    return test_user
                else:
                    # Fallback to mock user if test user not found in database
                    logger.warning("Test user not found in database, creating mock user")
                    return await create_mock_user_for_test(db)
            except Exception as e:
                logger.error(f"Error getting test user from database: {e}")
                # Fallback to mock user if there's an error
                return await create_mock_user_for_test(db)
        
        # Normal token validation
        payload = await auth_service.verify_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user is None:
            raise credentials_exception
            
        return user
    except JWTError:
        raise credentials_exception
    except Exception as e:
        logger.error(f"Error in get_current_user: {e}")
        raise credentials_exception

async def get_optional_user(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
    settings: Settings = Depends(get_settings),
) -> Optional[User]:
    """Get the current user if a valid token is provided, otherwise return None.
    
    Args:
        token: The JWT token (optional)
        db: The database session
        auth_service: The authentication service
        settings: The application settings
        
    Returns:
        The current user or None if no valid token is provided
    """
    if not token:
        return None
        
    try:
        # Handle emergency token for test environment
        if settings.TESTING and token == "test-environment-emergency-token":
            # Try to get the test user from the database first
            try:
                stmt = select(User).where(User.email == "test@test.com")
                result = await db.execute(stmt)
                test_user = result.scalar_one_or_none()
                
                if test_user:
                    logger.info("Using test user from database for emergency token in optional user")
                    return test_user
                else:
                    # Fallback to mock user if test user not found in database
                    logger.warning("Test user not found in database, creating mock user for optional user")
                    return await create_mock_user_for_test(db)
            except Exception as e:
                logger.error(f"Error getting test user from database for optional user: {e}")
                # Fallback to mock user if there's an error
                return await create_mock_user_for_test(db)
        
        # Normal token validation
        payload = await auth_service.verify_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            return None
        
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        return user
    except Exception as e:
        logger.warning(f"Error in get_optional_user: {e}")
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