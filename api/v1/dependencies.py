from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.services.goal import GoalService
from backend.core.services.user import UserService
from backend.core.services.token import TokenService
from backend.core.services.auth import get_current_user

async def get_goal_service(
    db: AsyncSession = Depends(get_db)
) -> GoalService:
    """Dependency that provides GoalService instance"""
    return GoalService(db)

async def get_user_service(
    db: AsyncSession = Depends(get_db)
) -> UserService:
    """Dependency that provides UserService instance"""
    return UserService(db)

async def get_token_service(
    db: AsyncSession = Depends(get_db)
) -> TokenService:
    """Dependency that provides TokenService instance"""
    return TokenService(db)

async def get_current_active_user(
    current_user: dict = Depends(get_current_user)
):
    """Dependency that returns current active user"""
    return current_user
