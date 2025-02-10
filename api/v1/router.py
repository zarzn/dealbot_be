from fastapi import APIRouter
from api.v1.endpoints import markets, market_search, users, health

router = APIRouter()

# Include routers
router.include_router(
    users.router,
    prefix="/auth",
    tags=["auth"]
)
router.include_router(
    markets.router,
    prefix="/markets",
    tags=["markets"]
)
router.include_router(
    market_search.router,
    prefix="/market-search",
    tags=["market-search"]
)
router.include_router(
    health.router,
    prefix="/health",
    tags=["health"]
)
