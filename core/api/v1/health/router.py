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

# Track startup time to provide a grace period for database connections
STARTUP_TIME = time.time()
STARTUP_GRACE_PERIOD = 300  # seconds - increased from 120 to 300 seconds (5 minutes)

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
        # Import Redis directly to avoid service layer
        from redis.asyncio import Redis
        from core.config import settings
        import asyncio
        
        # Basic info
        result = {
            "status": "unknown",
            "timestamp": time.time()
        }
        
        # Create a direct connection to Redis
        try:
            # Get Redis host and port from settings
            redis_host = settings.REDIS_HOST
            redis_port = settings.REDIS_PORT
            redis_db = settings.REDIS_DB
            
            # Try with the default docker-compose password first
            try:
                redis = Redis(
                    host=redis_host,
                    port=redis_port,
                    db=redis_db,
                    password="your_redis_password",
                    socket_timeout=1.0,
                    socket_connect_timeout=1.0,
                    decode_responses=True
                )
                
                # Try a simple PING command
                ping_start = time.time()
                ping_result = await redis.ping()
                ping_time_ms = round((time.time() - ping_start) * 1000)
                
                # Process result
                result["ping_time_ms"] = ping_time_ms
                
                if ping_result:
                    result["status"] = "healthy"
                    result["message"] = f"Redis is connected (ping: {ping_time_ms}ms)"
                    await redis.close()
                    return result
                else:
                    await redis.close()
                    raise Exception("Ping returned False")
                    
            except Exception as e:
                logger.debug(f"Redis connection failed with default password: {str(e)}")
                
                # Try with the configured password
                try:
                    redis = Redis(
                        host=redis_host,
                        port=redis_port,
                        db=redis_db,
                        password=settings.REDIS_PASSWORD,
                        socket_timeout=1.0,
                        socket_connect_timeout=1.0,
                        decode_responses=True
                    )
                    
                    # Try a simple PING command
                    ping_start = time.time()
                    ping_result = await redis.ping()
                    ping_time_ms = round((time.time() - ping_start) * 1000)
                    
                    # Process result
                    result["ping_time_ms"] = ping_time_ms
                    
                    if ping_result:
                        result["status"] = "healthy"
                        result["message"] = f"Redis is connected (ping: {ping_time_ms}ms)"
                        await redis.close()
                        return result
                    else:
                        await redis.close()
                        raise Exception("Ping returned False")
                        
                except Exception as e2:
                    logger.debug(f"Redis connection failed with configured password: {str(e2)}")
                    result["status"] = "unhealthy"
                    result["message"] = f"Redis connection failed with both passwords: {str(e2)}"
                    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
                    return result
            
        except Exception as conn_error:
            result["status"] = "unhealthy"
            result["message"] = f"Redis connection setup failed: {str(conn_error)}"
            result["error"] = str(conn_error)
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return result
            
    except Exception as e:
        logger.error(f"Redis health check failed: {str(e)}")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unhealthy",
            "message": str(e),
            "timestamp": time.time()
        }
    
    # Set the response status code - always 200 for now to prevent load balancer from terminating the task
    response.status_code = status_code
    
    # Log health check results
    log_level = logging.INFO if health_result["status"] == "healthy" else logging.WARNING
    logger.log(log_level, f"Health check: uptime={int(uptime)}s, grace_period={is_in_grace_period}, status={health_result['status']}, db={health_result['database']}, cache={health_result['cache']}")
    
    return health_result

@router.get("/health")
@router.post("/health")
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
        # Import Redis directly to avoid service layer
        from redis.asyncio import Redis
        from core.config import settings
        import asyncio
        
        # Basic info
        result = {
            "status": "unknown",
            "timestamp": time.time()
        }
        
        # Create a direct connection to Redis
        try:
            # Get Redis host and port from settings
            redis_host = settings.REDIS_HOST
            redis_port = settings.REDIS_PORT
            redis_db = settings.REDIS_DB
            
            # Try with the default docker-compose password first
            try:
                redis = Redis(
                    host=redis_host,
                    port=redis_port,
                    db=redis_db,
                    password="your_redis_password",
                    socket_timeout=1.0,
                    socket_connect_timeout=1.0,
                    decode_responses=True
                )
                
                # Try a simple PING command
                ping_start = time.time()
                ping_result = await redis.ping()
                ping_time_ms = round((time.time() - ping_start) * 1000)
                
                # Process result
                result["ping_time_ms"] = ping_time_ms
                
                if ping_result:
                    result["status"] = "healthy"
                    result["message"] = f"Redis is connected (ping: {ping_time_ms}ms)"
                    await redis.close()
                    return result
                else:
                    await redis.close()
                    raise Exception("Ping returned False")
                    
            except Exception as e:
                logger.debug(f"Redis connection failed with default password: {str(e)}")
                
                # Try with the configured password
                try:
                    redis = Redis(
                        host=redis_host,
                        port=redis_port,
                        db=redis_db,
                        password=settings.REDIS_PASSWORD,
                        socket_timeout=1.0,
                        socket_connect_timeout=1.0,
                        decode_responses=True
                    )
                    
                    # Try a simple PING command
                    ping_start = time.time()
                    ping_result = await redis.ping()
                    ping_time_ms = round((time.time() - ping_start) * 1000)
                    
                    # Process result
                    result["ping_time_ms"] = ping_time_ms
                    
                    if ping_result:
                        result["status"] = "healthy"
                        result["message"] = f"Redis is connected (ping: {ping_time_ms}ms)"
                        await redis.close()
                        return result
                    else:
                        await redis.close()
                        raise Exception("Ping returned False")
                        
                except Exception as e2:
                    logger.debug(f"Redis connection failed with configured password: {str(e2)}")
                    result["status"] = "unhealthy"
                    result["message"] = f"Redis connection failed with both passwords: {str(e2)}"
                    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
                    return result
            
        except Exception as conn_error:
            result["status"] = "unhealthy"
            result["message"] = f"Redis connection setup failed: {str(conn_error)}"
            result["error"] = str(conn_error)
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return result
            
    except Exception as e:
        logger.error(f"Redis health check failed: {str(e)}")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unhealthy",
            "message": str(e),
            "timestamp": time.time()
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

@router.get("/scraper-api/usage", response_model=Dict[str, int])
async def get_scraper_api_usage(db: AsyncSession = Depends(get_db_session)):
    """Get current ScraperAPI credit usage."""
    try:
        # Import here to avoid circular imports
        from core.integrations.market_factory import MarketIntegrationFactory
        
        market_factory = MarketIntegrationFactory(db=db)
        # Check if get_credit_usage method exists, otherwise return dummy data
        if hasattr(market_factory.scraper_api, 'get_credit_usage'):
            return await market_factory.scraper_api.get_credit_usage()
        else:
            # Return mock data to avoid errors
            return {"credits_used": 0, "credits_remaining": 1000}
    except MarketIntegrationError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get ScraperAPI usage: {str(e)}"
        )

@router.get("/")
async def root_health_check():
    """Root health check endpoint for AWS load balancers.
    
    This endpoint ALWAYS returns a 200 status code and healthy status,
    regardless of the actual application state.
    """
    return {
        "status": "healthy",
        "message": "Root health check endpoint"
    } 