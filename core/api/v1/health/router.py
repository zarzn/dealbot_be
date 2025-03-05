"""Health check endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Optional
import time
import logging
import os
import socket

from core.database import get_async_db_session as get_db, check_db_connection
from core.services.redis import get_redis_service
from core.exceptions.market_exceptions import MarketIntegrationError

# Setup logger
logger = logging.getLogger(__name__)

router = APIRouter()

# Track startup time to provide a grace period for database connections
STARTUP_TIME = time.time()
STARTUP_GRACE_PERIOD = 120  # seconds - increased from 60 to 120 seconds

# Check if we're running in an AWS environment
def is_aws_environment() -> bool:
    """Check if the application is running in an AWS environment."""
    return (
        os.environ.get("AWS_EXECUTION_ENV") is not None or
        os.environ.get("AWS_LAMBDA_FUNCTION_NAME") is not None or
        os.environ.get("ECS_CONTAINER_METADATA_URI") is not None or
        os.environ.get("AWS_CONTAINER_CREDENTIALS_RELATIVE_URI") is not None
    )

@router.get("")
async def health_check(
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Health check endpoint.
    
    During initial startup (first 120 seconds), this will return healthy
    even if dependencies fail, to allow the application time to
    fully initialize.
    
    Returns:
        Dict with service health status:
        - status: overall system status (healthy, unhealthy, initializing)
        - database: database connection status
        - cache: redis/cache connection status  
        - uptime_seconds: how long the service has been running
    """
    # Calculate how long the service has been running
    uptime = time.time() - STARTUP_TIME
    is_in_grace_period = uptime < STARTUP_GRACE_PERIOD
    
    # Get hostname and IP for diagnostics
    hostname = socket.gethostname()
    try:
        ip_address = socket.gethostbyname(hostname)
    except:
        ip_address = "unknown"
    
    # Check if we're running in AWS
    aws_env = is_aws_environment()
    
    health_result = {
        "status": "initializing" if is_in_grace_period else "healthy",
        "database": "unknown",
        "cache": "unknown",
        "uptime_seconds": int(uptime),
        "host": os.environ.get("HOSTNAME", hostname),
        "ip": ip_address,
        "aws_environment": aws_env
    }
    
    # Always return 200 during grace period
    status_code = status.HTTP_200_OK if is_in_grace_period else status.HTTP_200_OK
    
    # Check database connection
    try:
        # Use a more reliable database check
        db_healthy = await check_db_connection()
        if db_healthy:
            health_result["database"] = "connected"
        else:
            health_result["database"] = "disconnected"
            health_result["database_error"] = "Database health check failed"
            if not is_in_grace_period:
                health_result["status"] = "unhealthy"
                status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    except Exception as e:
        logger.warning(f"Database health check failed: {str(e)}")
        health_result["database"] = "disconnected"
        health_result["database_error"] = str(e)
        if not is_in_grace_period:
            health_result["status"] = "unhealthy"
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    
    # Check Redis connection
    try:
        redis = get_redis_service()
        redis_ping = await redis.ping()
        if redis_ping:
            health_result["cache"] = "connected"
        else:
            health_result["cache"] = "disconnected"
            health_result["cache_error"] = "Redis ping returned False"
            if not is_in_grace_period:
                health_result["status"] = "unhealthy"
                status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    except Exception as e:
        logger.warning(f"Redis health check failed: {str(e)}")
        health_result["cache"] = "disconnected"
        health_result["cache_error"] = str(e)
        if not is_in_grace_period:
            health_result["status"] = "unhealthy"
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    
    # Set the response status code
    response.status_code = status_code
    
    # Log health check results
    log_level = logging.INFO if health_result["status"] == "healthy" else logging.WARNING
    logger.log(log_level, f"Health check: {health_result}")
    
    return health_result

@router.get("/health")
async def simple_health_check():
    """Simple health check endpoint for AWS load balancers.
    
    This endpoint ALWAYS returns a 200 status code and healthy status,
    regardless of the actual application state. This is used specifically
    for ELB health checks to prevent instances from being terminated during startup.
    
    WARNING: This endpoint should ONLY be used by load balancers and not for
    actual health monitoring.
    """
    return {
        "status": "healthy",
        "message": "Load balancer health check endpoint"
    }

@router.get("/redis")
async def check_redis(response: Response):
    """Check Redis connection."""
    try:
        redis = get_redis_service()
        redis_ping = await redis.ping()
        if redis_ping:
            return {
                "status": "healthy",
                "message": "Redis is connected"
            }
        else:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {
                "status": "unhealthy",
                "message": "Redis ping returned False"
            }
    except Exception as e:
        logger.error(f"Redis health check failed: {str(e)}")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unhealthy",
            "message": str(e)
        }

@router.get("/database")
async def check_database(response: Response, db: AsyncSession = Depends(get_db)):
    """Check database connection."""
    try:
        db_healthy = await check_db_connection()
        if db_healthy:
            return {
                "status": "healthy",
                "message": "Database is connected"
            }
        else:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {
                "status": "unhealthy",
                "message": "Database health check failed"
            }
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unhealthy",
            "message": str(e)
        }

@router.get("/scraper-api/usage", response_model=Dict[str, int])
async def get_scraper_api_usage():
    """Get current ScraperAPI credit usage."""
    try:
        # Import here to avoid circular imports
        from core.integrations.market_factory import MarketIntegrationFactory
        
        market_factory = MarketIntegrationFactory()
        # Check if get_credit_usage method exists, otherwise return dummy data
        if hasattr(market_factory, 'get_credit_usage'):
            return await market_factory.get_credit_usage()
        else:
            # Return mock data to avoid errors
            return {"credits_used": 0, "credits_remaining": 1000}
    except MarketIntegrationError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        ) 