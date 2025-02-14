"""Main API router module."""

from fastapi import APIRouter

from .auth.router import router as auth_router
from .users.router import router as users_router
from .goals.router import router as goals_router
from .deals.router import router as deals_router
from .markets.router import router as markets_router
from .chat.router import router as chat_router
from .token.router import router as token_router
from .notifications.router import router as notifications_router
from .health.router import router as health_router
from .price_tracking.router import router as price_tracking_router
from .price_prediction.router import router as price_prediction_router

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
router.include_router(price_tracking_router, prefix="/price-tracking", tags=["Price Tracking"])
router.include_router(price_prediction_router, prefix="/price-prediction", tags=["Price Prediction"])

# System routes
router.include_router(health_router, prefix="/health", tags=["System"])