"""API v1 module."""

from fastapi import APIRouter

from .auth import router as auth_router
from .users import router as users_router
from .deals import router as deals_router
from .goals import router as goals_router, test_router as goals_test_router
from .analytics import router as analytics_router
from .health import router as health_router
from .price_tracking import router as price_tracking_router
from .price_prediction import router as price_prediction_router
from .notifications import router as notifications_router
from .token import router as token_router
from .chat import router as chat_router
from .markets import router as markets_router
from .ai import router as ai_router

__all__ = ["router"]

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router, prefix="/auth")
router.include_router(users_router, prefix="/users")
router.include_router(deals_router, prefix="/deals")
router.include_router(goals_router, prefix="/goals")
router.include_router(goals_test_router, prefix="/goals")
router.include_router(analytics_router, prefix="/analytics")
router.include_router(health_router, prefix="/health")
router.include_router(price_tracking_router, prefix="/price-tracking")
router.include_router(price_prediction_router, prefix="/price-prediction")
router.include_router(notifications_router, prefix="/notifications")
router.include_router(token_router, prefix="/token")
router.include_router(chat_router, prefix="/chat")
router.include_router(markets_router, prefix="/markets")
router.include_router(ai_router, prefix="/ai") 