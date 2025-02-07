from typing import Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import psutil
import os
from datetime import datetime

from core.database import get_db
from core.utils.redis import get_redis_client
from core.utils.logger import get_logger

router = APIRouter(prefix="/health", tags=["health"])
logger = get_logger(__name__)

@router.get("")
async def health_check() -> Dict[str, Any]:
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": os.getenv("APP_VERSION", "1.0.0")
    }

@router.get("/detailed")
async def detailed_health_check(
    session: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Detailed health check with component status"""
    status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": os.getenv("APP_VERSION", "1.0.0"),
        "components": {}
    }

    # Check database
    try:
        await session.execute("SELECT 1")
        status["components"]["database"] = {
            "status": "healthy",
            "message": "Connected successfully"
        }
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        status["components"]["database"] = {
            "status": "unhealthy",
            "message": str(e)
        }
        status["status"] = "degraded"

    # Check Redis
    try:
        redis = await get_redis_client()
        await redis.ping()
        status["components"]["redis"] = {
            "status": "healthy",
            "message": "Connected successfully"
        }
    except Exception as e:
        logger.error(f"Redis health check failed: {str(e)}")
        status["components"]["redis"] = {
            "status": "unhealthy",
            "message": str(e)
        }
        status["status"] = "degraded"

    # Check system resources
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        status["components"]["system"] = {
            "status": "healthy",
            "cpu": {
                "percent": cpu_percent,
                "status": "healthy" if cpu_percent < 80 else "warning"
            },
            "memory": {
                "total": memory.total,
                "available": memory.available,
                "percent": memory.percent,
                "status": "healthy" if memory.percent < 80 else "warning"
            },
            "disk": {
                "total": disk.total,
                "free": disk.free,
                "percent": disk.percent,
                "status": "healthy" if disk.percent < 80 else "warning"
            }
        }

        # Update overall status if resources are critical
        if cpu_percent > 90 or memory.percent > 90 or disk.percent > 90:
            status["status"] = "degraded"

    except Exception as e:
        logger.error(f"System health check failed: {str(e)}")
        status["components"]["system"] = {
            "status": "unknown",
            "message": str(e)
        }

    return status

@router.get("/readiness")
async def readiness_check(
    session: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Readiness check for kubernetes/container orchestration"""
    try:
        # Check database
        await session.execute("SELECT 1")
        
        # Check Redis
        redis = await get_redis_client()
        await redis.ping()
        
        return {
            "status": "ready",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Readiness check failed: {str(e)}")
        return {
            "status": "not_ready",
            "timestamp": datetime.utcnow().isoformat(),
            "message": str(e)
        }

@router.get("/liveness")
async def liveness_check() -> Dict[str, Any]:
    """Liveness check for kubernetes/container orchestration"""
    try:
        # Check system resources
        memory = psutil.virtual_memory()
        if memory.percent > 95:  # Critical memory usage
            raise Exception("Critical memory usage")

        cpu_percent = psutil.cpu_percent(interval=1)
        if cpu_percent > 95:  # Critical CPU usage
            raise Exception("Critical CPU usage")

        return {
            "status": "alive",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Liveness check failed: {str(e)}")
        return {
            "status": "critical",
            "timestamp": datetime.utcnow().isoformat(),
            "message": str(e)
        } 