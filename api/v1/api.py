"""Main API router."""

from fastapi import APIRouter
from api.v1.endpoints import (
    users,
    auth,
    deals,
    goals,
    monitoring
)

api_router = APIRouter()

api_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["auth"]
)

api_router.include_router(
    users.router,
    prefix="/users",
    tags=["users"]
)

api_router.include_router(
    deals.router,
    prefix="/deals",
    tags=["deals"]
)

api_router.include_router(
    goals.router,
    prefix="/goals",
    tags=["goals"]
)

api_router.include_router(
    monitoring.router,
    prefix="/monitoring",
    tags=["monitoring"]
) 