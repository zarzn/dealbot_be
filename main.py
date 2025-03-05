"""Main application module."""

import logging
import logging.handlers
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import configure_mappers
from sqlalchemy import event
from sqlalchemy.engine import Engine
from fastapi.responses import JSONResponse
from sqlalchemy.sql import text

from core.config import settings

# Configure environment-specific logging
def setup_logging():
    """Set up logging configuration based on environment."""
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    # Determine log level based on environment
    if str(settings.APP_ENVIRONMENT).lower() == "production":
        root_level = logging.WARNING
        log_format = '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
        # In production, use rotating file handler to manage log size
        handlers = [
            logging.handlers.RotatingFileHandler(
                "logs/app.log",
                maxBytes=10485760,  # 10 MB
                backupCount=5,
                encoding="utf-8"
            )
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
        'fastapi': logging.WARNING if str(settings.APP_ENVIRONMENT).lower() == "production" else logging.INFO,
        'uvicorn': logging.WARNING if str(settings.APP_ENVIRONMENT).lower() == "production" else logging.INFO,
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

# Import relationships module
from core.models.relationships import setup_relationships

# Import middleware setup
from core.middleware import setup_middleware

# Import routers
from core.api.v1.auth.router import router as auth_router
from core.api.v1.users.router import router as users_router
from core.api.v1.goals.router import router as goals_router
from core.api.v1.deals.router import router as deals_router
from core.api.v1.markets.router import router as markets_router
from core.api.v1.chat.router import router as chat_router
from core.api.v1.token.router import router as token_router
from core.api.v1.notifications.router import router as notifications_router
from core.api.v1.health.router import router as health_router
from core.api.v1.price_tracking.router import router as price_tracking_router
from core.api.v1.price_prediction.router import router as price_prediction_router

# Import websocket handlers
from core.api.v1.notifications.websocket import handle_websocket
from core.api.websocket import router as websocket_router

from core.utils.redis import get_redis_client, close_redis_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    try:
        # Set up model relationships
        logger.info("Setting up model relationships...")
        setup_relationships()
        logger.info("Model relationships set up")

        # Configure SQLAlchemy mappers
        logger.info("Configuring SQLAlchemy mappers...")
        configure_mappers()
        logger.info("SQLAlchemy mappers configured")
        
        # Initialize Redis client
        logger.info("Initializing Redis client...")
        await get_redis_client()  # Use await for async function
        logger.info("Redis client initialized")
        
        yield
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        raise
    finally:
        # Cleanup
        logger.info("Shutting down application...")
        await close_redis_client()  # Use await for async function
        logger.info("Redis client closed")

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="AI-powered deal monitoring system",
        lifespan=lifespan
    )

    # Add CORS middleware first
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
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
        return JSONResponse(
            content={},
            headers={
                "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
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
        from core.database import get_async_db_session as get_db
        from core.services.redis import get_redis_service
        import asyncio
        
        health_status = {
            "status": "healthy",
            "checks": {
                "database": {"status": "unknown", "message": "Not checked"},
                "redis": {"status": "unknown", "message": "Not checked"},
            },
            "version": settings.APP_VERSION,
            "environment": str(settings.APP_ENVIRONMENT)
        }
        
        # Check database connection
        try:
            db_session = next(get_db())
            with db_session.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                if result.scalar() == 1:
                    health_status["checks"]["database"] = {
                        "status": "healthy",
                        "message": "Connected successfully"
                    }
                else:
                    health_status["checks"]["database"] = {
                        "status": "unhealthy",
                        "message": "Database query failed"
                    }
        except Exception as e:
            health_status["checks"]["database"] = {
                "status": "unhealthy",
                "message": f"Database connection error: {str(e)}"
            }
            health_status["status"] = "unhealthy"
        
        # Check Redis connection
        try:
            redis = await get_redis_service()
            if await redis.ping():
                health_status["checks"]["redis"] = {
                    "status": "healthy",
                    "message": "Connected successfully"
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
