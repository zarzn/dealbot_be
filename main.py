"""Main application module."""

import logging
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
sqlalchemy_logger = logging.getLogger('sqlalchemy')
sqlalchemy_logger.setLevel(logging.ERROR)
sqlalchemy_logger.propagate = False  # Prevent propagation to root logger

sqlalchemy_engine_logger = logging.getLogger('sqlalchemy.engine')
sqlalchemy_engine_logger.setLevel(logging.ERROR)
sqlalchemy_engine_logger.propagate = False

sqlalchemy_pool_logger = logging.getLogger('sqlalchemy.pool')
sqlalchemy_pool_logger.setLevel(logging.ERROR)
sqlalchemy_pool_logger.propagate = False

sqlalchemy_dialects_logger = logging.getLogger('sqlalchemy.dialects')
sqlalchemy_dialects_logger.setLevel(logging.ERROR)
sqlalchemy_dialects_logger.propagate = False

sqlalchemy_orm_logger = logging.getLogger('sqlalchemy.orm')
sqlalchemy_orm_logger.setLevel(logging.ERROR)
sqlalchemy_orm_logger.propagate = False

logger = logging.getLogger(__name__)

# Import all models to ensure they are registered with SQLAlchemy
from core.models.base import Base
from core.models.user import User
from core.models.goal import Goal
from core.models.deal import Deal
from core.models.notification import Notification
from core.models.chat import ChatMessage
from core.models.token import TokenTransaction, TokenBalanceHistory, TokenWallet
from core.models.market import Market

# Import relationships module
from core.models.relationships import setup_relationships

# Set up relationships before any database operations
logger.info("Setting up model relationships...")
setup_relationships()

# Configure mappers after relationships are set
logger.info("Configuring SQLAlchemy mappers...")
configure_mappers()

# Import router after all models and mappers are configured
from core.api.v1 import api_router

# Create FastAPI application
app = FastAPI(
    title="AI Agentic Deals API",
    description="API for AI-driven deal monitoring and analysis",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_websockets=True,  # Explicitly allow WebSocket connections
)

# Include API routes
app.include_router(api_router, prefix="/api/v1")

@app.on_event("startup")
async def startup_event():
    """Run startup tasks."""
    logger.info("Starting up AI Agentic Deals API...")
    # Verify mapper configuration
    logger.info("Verifying SQLAlchemy configuration...")
    try:
        configure_mappers()  # Re-run to verify configuration
        logger.info("SQLAlchemy configuration verified successfully")
    except Exception as e:
        logger.error(f"Error in SQLAlchemy configuration: {str(e)}")
        raise

# For SQLite (if used in development)
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Set SQLite pragmas on connection."""
    if hasattr(dbapi_connection, "execute"):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")
