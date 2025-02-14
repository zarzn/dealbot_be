"""Main application module."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import configure_mappers
from sqlalchemy import event
from sqlalchemy.engine import Engine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True  # Force reconfiguration of the root logger
)

# Configure SQLAlchemy logging
loggers = {
    'sqlalchemy': logging.ERROR,
    'sqlalchemy.engine': logging.ERROR,
    'sqlalchemy.pool': logging.ERROR,
    'sqlalchemy.dialects': logging.ERROR,
    'sqlalchemy.orm': logging.ERROR
}

for logger_name, level in loggers.items():
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    logger.propagate = False

logger = logging.getLogger(__name__)

# Import all models to ensure they are registered with SQLAlchemy
from core.models import (
    Base, User, Goal, Deal, Notification, ChatMessage,
    TokenTransaction, TokenBalanceHistory, TokenWallet,
    Market, PricePoint, PriceTracker, PricePrediction,
    MessageRole, MessageStatus
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

from core.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    try:
        # Configure SQLAlchemy mappers
        logger.info("Configuring SQLAlchemy mappers...")
        configure_mappers()
        logger.info("SQLAlchemy mappers configured")
        
        yield
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        raise
    finally:
        # Cleanup
        logger.info("Shutting down application...")

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="AI-powered deal monitoring system",
        lifespan=lifespan
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"]
    )

    # Setup middleware
    setup_middleware(app)

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

    # WebSocket endpoint
    app.websocket("/notifications/ws")(handle_websocket)

    @app.get("/")
    async def root():
        """Root endpoint for health check"""
        return {
            "status": "ok",
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT
        }

    return app

app = create_app()

# For SQLite (if used in development)
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Set SQLite pragmas on connection."""
    if hasattr(dbapi_connection, "execute"):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")
