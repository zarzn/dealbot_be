"""Health check endpoints."""

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from core.database import get_async_db_session as get_db

router = APIRouter()

@router.get("")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check endpoint."""
    try:
        # Check database connection
        await db.execute("SELECT 1")
        return {
            "status": "healthy",
            "database": "connected",
            "message": "System is operational"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "message": str(e)
        } 