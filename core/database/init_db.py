"""Database initialization module.

This module handles the initialization of database tables and initial data setup.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
import logging

# Import all models first to ensure they are registered with the Base metadata
from core.models.base import Base
from core.models.user import User
from core.models.goal import Goal
from core.models.deal import Deal
from core.models.market import Market
from core.models.deal_score import DealScore
from core.models.chat import ChatMessage
from core.models.notification import Notification
from core.models.token_pricing import TokenPricing
from core.models.token import TokenTransaction, TokenBalanceHistory, TokenWallet, TokenBalance, TokenPrice

# Import relationships setup after all models are imported
from core.models.relationships import setup_relationships
from core.database import engine

logger = logging.getLogger(__name__)

async def init_database() -> None:
    """Initialize database tables and verify connection."""
    try:
        # First verify connection
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            logger.info("Database connection verified")
        
        # Set up model relationships after all models are imported
        setup_relationships()
        logger.info("Model relationships configured")
        
        # Create all tables after relationships are set up
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
            
    except SQLAlchemyError as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during database initialization: {str(e)}")
        raise 