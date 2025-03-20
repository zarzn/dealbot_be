"""Main application module.

This module sets up the FastAPI application and its dependencies.
"""

import logging
import logging.handlers
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, status, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import configure_mappers
from sqlalchemy import event
from sqlalchemy.engine import Engine
from fastapi.responses import JSONResponse
from sqlalchemy.sql import text, select
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.utils import get_openapi
import time
import sys
import asyncio
from typing import Dict, Any, List, Optional, Union, Callable

from core.config import settings
from core.models.relationships import setup_relationships
from core.database import async_engine, sync_engine
from core.services.redis import get_redis_service

# Configure environment-specific logging
def setup_logging():
    """Set up logging configuration based on environment."""
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    # Determine log level based on environment
    if str(settings.APP_ENVIRONMENT).lower() == "production":
        root_level = logging.INFO  # Changed from WARNING to INFO to capture more logs
        log_format = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
        # In production, use both rotating file handler AND stdout handler for Docker/CloudWatch
        handlers = [
            logging.handlers.RotatingFileHandler(
                "logs/app.log",
                maxBytes=10485760,  # 10 MB
                backupCount=5,
                encoding="utf-8"
            ),
            logging.StreamHandler(sys.stdout)  # Added StreamHandler for Docker logs
        ]
    else:
        # More verbose logging for development/test
        root_level = logging.INFO
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        handlers = [logging.StreamHandler()]

    # Configure root logger
    logging.basicConfig(
        level=root_level,
        format=log_format,
        handlers=handlers,
        force=True  # Force reconfiguration
    )

    # Configure module-specific log levels
    loggers = {
        'sqlalchemy': logging.ERROR,
        'sqlalchemy.engine': logging.ERROR,
        'sqlalchemy.pool': logging.ERROR,
        'sqlalchemy.dialects': logging.ERROR,
        'sqlalchemy.orm': logging.ERROR,
        'urllib3': logging.WARNING,
        'asyncio': logging.WARNING,
        'fastapi': logging.INFO,  # Changed to INFO in production to see API requests
        'uvicorn': logging.INFO,  # Changed to INFO in production to see startup/requests
        'aiohttp': logging.WARNING,
    }

    for logger_name, level in loggers.items():
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
        logger.propagate = False

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)
logger.info(f"Application starting in {settings.APP_ENVIRONMENT} environment")

# Import all models to ensure they are registered with SQLAlchemy
from core.models import (
    Base, User, Goal, Deal, Notification, ChatMessage,
    TokenTransaction, TokenBalanceHistory, TokenWallet,
    Market, PricePoint, PriceTracker, PricePrediction,
    MessageRole, MessageStatus, AuthToken
)

# Import middleware setup
from core.middleware import setup_middleware

# Import routers
from core.api.v1.auth import router as auth_router
from core.api.v1.users import router as users_router
from core.api.v1.goals import router as goals_router
from core.api.v1.deals import router as deals_router
from core.api.v1.markets import router as markets_router
from core.api.v1.chat import router as chat_router
from core.api.v1.token import router as token_router
from core.api.v1.notifications import router as notifications_router
from core.api.v1.health import router as health_router
from core.api.v1.price_tracking import router as price_tracking_router
from core.api.v1.price_prediction import router as price_prediction_router
from core.api.v1.ai import router as ai_router
from core.api.v1.analytics import router as analytics_router

# Import websocket handlers
from core.api.v1.notifications.websocket import handle_websocket
from core.api.websocket import router as websocket_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan setup and cleanup.
    
    This function handles setup before the application starts
    and cleanup after it stops.
    """
    # Background tasks for monitoring
    connection_monitor_task = None
    connection_leak_detector_task = None
    
    # Setup
    try:
        # Setup model relationships
        logger.info("Setting up model relationships...")
        setup_relationships()
        logger.info("Model relationships set up")
        
        # Configure SQLAlchemy mappers
        logger.info("Configuring SQLAlchemy mappers...")
        configure_mappers()
        logger.info("SQLAlchemy mappers configured")
        
        # Initialize Redis client
        logger.info("Initializing Redis client...")
        try:
            # Use a timeout to prevent hanging if Redis is unresponsive
            redis_init_task = asyncio.create_task(get_redis_service())
            redis_service = await asyncio.wait_for(redis_init_task, timeout=5.0)
            logger.info("Redis client initialized")
        except asyncio.TimeoutError:
            logger.error("Redis initialization timed out - continuing without Redis")
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {str(e)} - continuing without Redis")
        
        # Start database connection monitoring
        try:
            logger.info("Starting database connection monitoring...")
            from core.utils.connection_monitor import monitor_connections, detect_connection_leaks, cleanup_connections
            
            # Clean up any existing connections
            await cleanup_connections()
            
            # Start connection monitoring background task
            connection_monitor_task = asyncio.create_task(monitor_connections(interval=30))
            
            # Start connection leak detection background task
            connection_leak_detector_task = asyncio.create_task(
                detect_connection_leaks(timeout=180, threshold=5, interval=60)
            )
            
            logger.info("Database connection monitoring started")
        except Exception as e:
            logger.error(f"Failed to start database connection monitoring: {str(e)}")
        
        yield
    
    except Exception as e:
        logger.error(f"Error during application startup: {str(e)}")
        # Yield even if setup fails to prevent application crash
        yield
    
    finally:
        # Shutdown
        logger.info("Shutting down application...")
        
        # Cancel background tasks
        if connection_monitor_task:
            logger.info("Stopping connection monitoring...")
            connection_monitor_task.cancel()
            try:
                await connection_monitor_task
            except asyncio.CancelledError:
                pass
            
        if connection_leak_detector_task:
            logger.info("Stopping connection leak detection...")
            connection_leak_detector_task.cancel()
            try:
                await connection_leak_detector_task
            except asyncio.CancelledError:
                pass
        
        # Clean up database connections
        try:
            logger.info("Cleaning up database connections...")
            from core.utils.connection_monitor import cleanup_connections
            await cleanup_connections()
            logger.info("Database connections cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up database connections: {str(e)}")
        
        # Close Redis connections
        try:
            logger.info("Closing Redis connections...")
            try:
                redis_service = await get_redis_service()
                if redis_service is not None:
                    await redis_service.close()
                    logger.info("Redis client closed")
                else:
                    logger.info("No Redis client to close")
            except Exception as e:
                logger.error(f"Error closing Redis connections: {str(e)}")
        except Exception as e:
            logger.error(f"Exception accessing Redis service during shutdown: {str(e)}")
        
        # Close database connections
        try:
            logger.info("Closing database connections...")
            
            # Close async engine
            if async_engine is not None and hasattr(async_engine, 'dispose'):
                try:
                    await async_engine.dispose()
                    logger.info("Async engine disposed")
                except Exception as e:
                    logger.error(f"Error disposing async engine: {str(e)}")
            
            # Close sync engine
            if sync_engine is not None and hasattr(sync_engine, 'dispose'):
                try:
                    sync_engine.dispose()
                    logger.info("Sync engine disposed")
                except Exception as e:
                    logger.error(f"Error disposing sync engine: {str(e)}")
                    
            logger.info("Database connections closed")
        except Exception as e:
            logger.error(f"Exception closing database connections: {str(e)}")
        
        logger.info("Application shutdown completed")

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="AI-powered deal monitoring system",
        lifespan=lifespan
    )

    # Add a public deals endpoint that doesn't go through authentication middleware
    # This must be defined BEFORE any middleware is applied
    @app.get("/api/v1/public-deals", tags=["Public Deals"])
    async def get_public_deals(
        page: int = Query(1, ge=1, description="Page number"),
        page_size: int = Query(6, ge=1, le=20, description="Items per page"),
        category: Optional[str] = None,
        price_min: Optional[float] = None,
        price_max: Optional[float] = None,
        sort_by: Optional[str] = "relevance"
    ):
        """
        Get public deals without requiring authentication.
        This endpoint is publicly accessible.
        """
        logger = logging.getLogger(__name__)
        try:
            # Debug log all request parameters
            logger.warning(f"PUBLIC DEALS ENDPOINT ACCESSED: page={page}, page_size={page_size}, category={category}, price_min={price_min}, price_max={price_max}, sort_by={sort_by}")
            
            # Create direct database session without dependencies
            from sqlalchemy.ext.asyncio import AsyncSession
            from core.models.deal import Deal, DealResponse
            from core.models.enums import DealStatus
            
            async with AsyncSession(async_engine) as db:
                try:
                    # Build query
                    offset = (page - 1) * page_size
                    
                    # Build the SQL query explicitly
                    stmt = select(Deal).where(
                        Deal.is_active == True,
                        Deal.status == DealStatus.ACTIVE.value.lower()
                    )
                    
                    # Apply filters if provided
                    if category:
                        stmt = stmt.where(Deal.category == category)
                    if price_min is not None:
                        stmt = stmt.where(Deal.price >= price_min)
                    if price_max is not None:
                        stmt = stmt.where(Deal.price <= price_max)
                        
                    # Apply sorting
                    if sort_by == "price_asc":
                        stmt = stmt.order_by(Deal.price.asc())
                    elif sort_by == "price_desc":
                        stmt = stmt.order_by(Deal.price.desc())
                    else:
                        stmt = stmt.order_by(Deal.created_at.desc())
                        
                    # Apply pagination
                    stmt = stmt.offset(offset).limit(page_size)
                    
                    # Log the SQL being executed
                    logger.warning(f"PUBLIC DEALS SQL: {str(stmt)}")
                    
                    # Execute query
                    result = await db.execute(stmt)
                    deals = result.scalars().all()
                    
                    logger.warning(f"Found {len(deals)} public deals")
                    
                    # Convert to response model and return
                    response_deals = []
                    for deal in deals:
                        try:
                            deal_dict = {
                                "id": str(deal.id),
                                "title": deal.title,
                                "description": deal.description,
                                "url": deal.url,
                                "image_url": deal.image_url,
                                "price": deal.price,
                                "original_price": deal.original_price,
                                "category": deal.category,
                                "source": deal.source,
                                "is_active": deal.is_active,
                                "status": deal.status,
                                "market_id": str(deal.market_id),
                                "currency": deal.currency,
                                "seller_info": deal.seller_info,
                                "availability": deal.availability,
                                "deal_metadata": deal.deal_metadata,
                                "price_metadata": deal.price_metadata,
                                "found_at": deal.found_at,
                                "created_at": deal.created_at,
                                "updated_at": deal.updated_at,
                                "latest_score": deal.score,
                                "price_history": []
                            }
                            response_deals.append(DealResponse(**deal_dict))
                        except Exception as conversion_error:
                            logger.warning(f"Error converting deal to response model: {str(conversion_error)}")
                            # Skip this deal and continue with others
                            continue
                    
                    # If we have no real deals and are in development mode, generate mock deals
                    if len(response_deals) == 0 and os.environ.get("ENVIRONMENT", "development") == "development":
                        logger.warning("No deals found, generating mock deals for development")
                        from decimal import Decimal
                        from uuid import uuid4
                        from datetime import datetime, timedelta
                        import random
                        
                        # Generate 10 mock deals
                        for i in range(10):
                            created_time = datetime.now() - timedelta(days=random.randint(1, 30))
                            # Choose from valid market categories
                            categories = ["electronics", "home", "fashion", "books", "sports"]
                            # Choose from valid source types
                            sources = ["amazon", "walmart", "ebay", "manual", "api"]
                            
                            # Create price history for the mock deal
                            historical_price = Decimal(random.uniform(600, 1000)).quantize(Decimal('0.01'))
                            current_price = Decimal(random.uniform(50, 500)).quantize(Decimal('0.01'))
                            
                            price_history = [
                                {
                                    "price": float(historical_price),
                                    "currency": "USD",
                                    "timestamp": (created_time - timedelta(days=7)).isoformat(),
                                    "source": "historical"
                                },
                                {
                                    "price": float(current_price),
                                    "currency": "USD",
                                    "timestamp": created_time.isoformat(),
                                    "source": "current"
                                }
                            ]
                            
                            mock_deal = DealResponse(
                                id=str(uuid4()),
                                title=f"Mock Deal {i+1}",
                                description="This is a mock deal for development purposes",
                                url="https://example.com/mock-deal",
                                image_url="https://via.placeholder.com/350x150",
                                price=current_price,
                                original_price=historical_price,
                                currency="USD",
                                source=random.choice(sources),
                                category=random.choice(categories),
                                is_active=True,
                                status="active",
                                market_id=str(uuid4()),
                                found_at=created_time,
                                created_at=created_time,
                                updated_at=created_time,
                                seller_info={"name": "Mock Seller", "rating": 4.5},
                                availability={"in_stock": True, "quantity": 10},
                                score=Decimal(random.uniform(80, 95)).quantize(Decimal('0.1')),
                                latest_score=Decimal(random.uniform(80, 95)).quantize(Decimal('0.1')),
                                price_history=price_history,
                                deal_metadata={"vendor": random.choice(["Amazon", "Walmart", "Target", "Best Buy"]), "is_verified": True},
                                price_metadata={
                                    "price_history": [
                                        {
                                            "price": str(historical_price),
                                            "timestamp": (created_time - timedelta(days=7)).isoformat(),
                                            "source": "historical"
                                        },
                                        {
                                            "price": str(current_price),
                                            "timestamp": created_time.isoformat(),
                                            "source": "current"
                                        }
                                    ]
                                }
                            )
                            response_deals.append(mock_deal)
                        
                    logger.warning(f"Returning {len(response_deals)} public deals")
                    
                    # Explicitly commit the transaction (although it's a read-only operation)
                    await db.commit()
                    return response_deals
                except Exception as db_error:
                    # Make sure to roll back the transaction on error
                    await db.rollback()
                    logger.error(f"Database error in public deals endpoint: {str(db_error)}", exc_info=True)
                    raise
                
        except Exception as e:
            logger.error(f"Error in get_public_deals: {str(e)}", exc_info=True)
            # Return empty list instead of an error to avoid breaking the UI
            return []

    # Add CORS middleware first
    cors_origins = settings.CORS_ORIGINS
    # Convert to a proper list if it's a Pydantic FieldInfo
    if not isinstance(cors_origins, list):
        try:
            # Try to convert to list if possible
            cors_origins = list(cors_origins)
        except (TypeError, ValueError):
            # Fallback to safe default
            cors_origins = ["*"]
    
    # Ensure CloudFront domain is in the list
    cloudfront_domain = "https://d3irpl0o2ddv9y.cloudfront.net"
    if cloudfront_domain not in cors_origins:
        cors_origins.append(cloudfront_domain)
            
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=["*"],
        expose_headers=["*"],
        max_age=600,  # 10 minutes
    )

    # Setup other middleware
    @app.on_event("startup")
    async def startup_event():
        await setup_middleware(app)

    # Add OPTIONS handler for all routes
    @app.options("/{full_path:path}")
    async def options_handler(request: Request):
        origin = request.headers.get("origin", "*")
        # Ensure CloudFront domain is allowed
        cloudfront_domain = "https://d3irpl0o2ddv9y.cloudfront.net"
        
        # If origin is our CloudFront domain, use it specifically, otherwise use the settings
        allowed_origin = origin if origin == cloudfront_domain or origin in settings.CORS_ORIGINS else "*"
        
        return JSONResponse(
            content={},
            headers={
                "Access-Control-Allow-Origin": allowed_origin,
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Allow-Credentials": "true",
            },
        )

    # Include routers
    app.include_router(auth_router, prefix=f"{settings.API_V1_PREFIX}/auth", tags=["Authentication"])
    app.include_router(users_router, prefix=f"{settings.API_V1_PREFIX}/users", tags=["Users"])
    app.include_router(goals_router, prefix=f"{settings.API_V1_PREFIX}/goals", tags=["Goals"])
    app.include_router(deals_router, prefix=f"{settings.API_V1_PREFIX}/deals", tags=["Deals"])
    app.include_router(markets_router, prefix=f"{settings.API_V1_PREFIX}/markets", tags=["Markets"])
    app.include_router(chat_router, prefix=f"{settings.API_V1_PREFIX}/chat", tags=["Chat"])
    app.include_router(token_router, prefix=f"{settings.API_V1_PREFIX}/token", tags=["Token"])
    app.include_router(notifications_router, prefix=f"{settings.API_V1_PREFIX}/notifications", tags=["Notifications"])
    app.include_router(price_tracking_router, prefix=f"{settings.API_V1_PREFIX}/price-tracking", tags=["Price Tracking"])
    app.include_router(price_prediction_router, prefix=f"{settings.API_V1_PREFIX}/price-prediction", tags=["Price Prediction"])
    app.include_router(health_router, prefix=f"{settings.API_V1_PREFIX}/health", tags=["System"])
    app.include_router(ai_router, prefix=f"{settings.API_V1_PREFIX}/ai", tags=["AI"])
    app.include_router(analytics_router, prefix=f"{settings.API_V1_PREFIX}/analytics", tags=["Analytics"])
    
    # Include WebSocket router
    app.include_router(websocket_router, tags=["WebSocket"])

    # Legacy WebSocket endpoint
    app.websocket("/notifications/ws")(handle_websocket)

    @app.get("/")
    async def root():
        """Root endpoint for health check"""
        return {
            "status": "ok",
            "version": settings.APP_VERSION,
            "environment": str(settings.APP_ENVIRONMENT)
        }

    # Health endpoint moved to app.py which redirects to /api/v1/health/health

    # Add a more comprehensive health check endpoint
    @app.get("/api/v1/health")
    async def api_health():
        """API health check that verifies connectivity to dependencies.
        
        This endpoint checks database and Redis connectivity.
        """
        from core.database import AsyncDatabaseSession
        from core.services.redis import get_redis_service
        import time
        
        start_time = time.time()
        health_status = {
            "status": "healthy",
            "checks": {
                "database": {"status": "unknown", "message": "Not checked"},
                "redis": {"status": "unknown", "message": "Not checked"},
            },
            "version": settings.APP_VERSION,
            "environment": str(settings.APP_ENVIRONMENT),
            "timestamp": start_time
        }
        
        # Check database connection
        try:
            async with AsyncDatabaseSession() as db_session:
                # Simple query to check database connectivity
                result = await db_session.execute(text("SELECT 1"))
                value = result.scalar()
                
                if value == 1:
                    db_response_time = time.time() - start_time
                    health_status["checks"]["database"] = {
                        "status": "healthy",
                        "message": "Connected successfully",
                        "response_time_ms": round(db_response_time * 1000, 2)
                    }
                else:
                    health_status["checks"]["database"] = {
                        "status": "unhealthy",
                        "message": "Database query failed"
                    }
                    health_status["status"] = "unhealthy"
        except Exception as e:
            health_status["checks"]["database"] = {
                "status": "unhealthy",
                "message": f"Database connection error: {str(e)}"
            }
            health_status["status"] = "unhealthy"
        
        # Check Redis connection
        redis_start_time = time.time()
        try:
            redis = await get_redis_service()
            ping_result = await redis.ping()
            
            redis_response_time = time.time() - redis_start_time
            if ping_result:
                health_status["checks"]["redis"] = {
                    "status": "healthy",
                    "message": "Connected successfully",
                    "ping_time_ms": round(redis_response_time * 1000, 2)
                }
            else:
                health_status["checks"]["redis"] = {
                    "status": "unhealthy",
                    "message": "Redis ping failed"
                }
                health_status["status"] = "unhealthy"
        except Exception as e:
            health_status["checks"]["redis"] = {
                "status": "unhealthy",
                "message": f"Redis connection error: {str(e)}"
            }
            health_status["status"] = "unhealthy"
        
        # Update total response time
        health_status["response_time_ms"] = round((time.time() - start_time) * 1000, 2)
        
        return health_status

    @app.get("/api/v1/health/health")
    async def simple_api_health():
        """Simple API health check that always returns healthy.
        
        This is an alternative to the more comprehensive health check
        and is useful for basic health monitoring.
        """
        return {"status": "healthy"}

    return app

app = create_app()

# For SQLite (if used in development)
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Set SQLite pragmas on connection."""
    # Only run for SQLite connections, not PostgreSQL
    if hasattr(dbapi_connection, "execute") and settings.DATABASE_URL and 'sqlite' in str(settings.DATABASE_URL).lower():
        dbapi_connection.execute("PRAGMA foreign_keys=ON")
        dbapi_connection.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging for better concurrency
        dbapi_connection.execute("PRAGMA synchronous=NORMAL")  # Balance between durability and speed
        dbapi_connection.execute("PRAGMA cache_size=-64000")  # Use up to 64MB memory for caching (negative value is in KB)
        dbapi_connection.execute("PRAGMA temp_store=MEMORY")  # Store temporary tables and indices in memory
