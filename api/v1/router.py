from fastapi import APIRouter
from .endpoints import users, markets, market_search

router = APIRouter()

router.include_router(users.router, prefix="/users", tags=["users"])
router.include_router(markets.router, prefix="/markets", tags=["markets"])
router.include_router(market_search.router, prefix="/market-search", tags=["market-search"])
