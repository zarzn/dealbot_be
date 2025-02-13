"""Main API router module."""

from fastapi import APIRouter

from core.api.v1.auth.router import router as auth_router
from core.api.v1.users.router import router as users_router
from core.api.v1.goals.router import router as goals_router
from core.api.v1.deals.router import router as deals_router
from core.api.v1.markets.router import router as markets_router
from core.api.v1.chat.router import router as chat_router
from core.api.v1.token.router import router as token_router
from core.api.v1.notifications.router import router as notifications_router
from core.api.v1.health.router import router as health_router

router = APIRouter()

# Core routes
router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
router.include_router(users_router, prefix="/users", tags=["Users"])
router.include_router(goals_router, prefix="/goals", tags=["Goals"])
router.include_router(deals_router, prefix="/deals", tags=["Deals"])
router.include_router(markets_router, prefix="/markets", tags=["Markets"])
router.include_router(chat_router, prefix="/chat", tags=["Chat"])
router.include_router(token_router, prefix="/token", tags=["Token"])
router.include_router(notifications_router, prefix="/notifications", tags=["Notifications"])

# System routes
router.include_router(health_router, prefix="/health", tags=["System"])