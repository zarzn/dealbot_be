"""Health check endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Optional
import time
import logging
import os
import socket
from urllib.parse import urlparse, urlunparse

from core.database import get_async_db_session as get_db, check_db_connection, get_async_db_context
from core.services.redis import get_redis_service
from core.exceptions.market_exceptions import MarketIntegrationError

# Setup logger
logger = logging.getLogger(__name__)

router = APIRouter()

# Add the get_db_session dependency function
async def get_db_session() -> AsyncSession:
    """Get a database session using the improved context manager.
    
    This dependency provides better connection management and prevents connection leaks.
    """
    async with get_async_db_context() as session:
        yield session

# Constants for health check
STARTUP_TIME = time.time()
STARTUP_GRACE_PERIOD = 300  # 5 minutes

def is_aws_environment() -> bool:
    """Check if we're running in an AWS environment."""
    host = os.environ.get("HOSTNAME", socket.gethostname())
    # Check common AWS environment flags
    return (
        os.environ.get("AWS_EXECUTION_ENV") is not None
        or "ECS" in host
        or "EC2" in host
        or os.environ.get("AWS_CONTAINER_CREDENTIALS_RELATIVE_URI") is not None
    )

@router.get("")
async def health_check(
    response: Response,
    db: AsyncSession = Depends(get_db_session)
):
    """Health check endpoint.
    
    During initial startup (first 300 seconds), this will return healthy
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
        "aws_environment": aws_env,
        "grace_period": is_in_grace_period,
        "grace_period_seconds": STARTUP_GRACE_PERIOD
    }
    
    # Always return 200 during grace period
    status_code = status.HTTP_200_OK
    
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
            # Only set non-200 status code if outside grace period AND we want to fail health checks
            # status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    except Exception as e:
        logger.warning(f"Database health check failed: {str(e)}")
        health_result["database"] = "disconnected"
        health_result["database_error"] = str(e)
        if not is_in_grace_period:
            health_result["status"] = "unhealthy"
            # Only set non-200 status code if outside grace period AND we want to fail health checks
            # status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    
    # Check Redis connection
    try:
        redis = await get_redis_service()
        if redis:
            ping_result = await redis.ping()
            if ping_result:
                health_result["cache"] = "connected"
            else:
                health_result["cache"] = "disconnected"
                health_result["cache_error"] = "Redis ping failed"
                # Only make service unhealthy if outside grace period
                if not is_in_grace_period:
                    health_result["status"] = "unhealthy"
                    # Only set non-200 status code if outside grace period
                    # status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        else:
            health_result["cache"] = "not_configured"
    except Exception as e:
        logger.warning(f"Redis health check failed: {str(e)}")
        health_result["cache"] = "disconnected"
        health_result["cache_error"] = str(e)
        if not is_in_grace_period:
            health_result["status"] = "unhealthy"
            # Only set non-200 status code if outside grace period
            # status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    
    response.status_code = status_code
    return health_result

@router.get("/health")
async def simple_health_check():
    """Simple health check endpoint for AWS load balancers.
    
    This endpoint ALWAYS returns a 200 status code and healthy status,
    regardless of the actual application state. This is used specifically
    for ELB health checks to prevent instances from being terminated during startup.
    """
    return {
        "status": "healthy",
        "message": "Load balancer health check endpoint"
    }

@router.get("/database")
async def check_database(response: Response):
    """Check database connection.
    
    Performs a minimal check of the database connection by running a simple query.
    """
    # Basic information
    result = {
        "status": "unknown",
        "timestamp": time.time()
    }
    
    # Use a very simple try/except block
    try:
        # We directly use execute_query from the dependency
        from sqlalchemy import text
        from core.database import AsyncDatabaseSession
        
        # Use the database session context manager for proper cleanup
        async with AsyncDatabaseSession() as session:
            # Try a simple query
            res = await session.execute(text("SELECT 1 AS test"))
            value = res.scalar_one()
            
            if value == 1:
                result["status"] = "healthy"
                result["message"] = "Database connection successful"
                return result
            
            # If we got here, something unexpected happened
            result["status"] = "unhealthy"
            result["message"] = f"Unexpected database response: {value}"
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return result
    
    except Exception as e:
        # Log the exception
        logger.error(f"Database health check failed: {str(e)}")
        
        # Return an error response
        result["status"] = "unhealthy"
        result["message"] = f"Database error: {str(e)}"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return result 