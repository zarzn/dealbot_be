"""Alembic environment configuration.

This module configures the Alembic environment for database migrations.
"""

import asyncio
import os
import sys
import logging
from logging.config import fileConfig
from typing import List

from alembic import context
from sqlalchemy import pool, create_engine
from sqlalchemy.engine import Connection
from sqlalchemy import engine_from_config

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('alembic.env')

# Add parent directory to path for imports
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, parent_dir)

from core.config import settings
from core.models.base import Base

# Import all models to ensure they are registered with SQLAlchemy
from core.models.user import User
from core.models.goal import Goal
from core.models.deal import Deal
from core.models.notification import Notification
from core.models.chat import ChatMessage
from core.models.token import TokenTransaction, TokenBalanceHistory, TokenWallet
from core.models.market import Market
from core.models.auth_token import AuthToken
from core.models.token_balance import TokenBalance
from core.models.token_pricing import TokenPricing
from core.models.price_prediction import PricePrediction
from core.models.price_tracking import PricePoint, PriceTracker
from core.models.deal_score import DealScore
from core.models.user_preferences import UserPreferences

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Get database URL from environment variables
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "12345678")
POSTGRES_DB = os.getenv("POSTGRES_DB", "deals")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")

# Use POSTGRES_HOST environment variable
DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

logger.info(f"Using database URL: {DATABASE_URL}")

# Set database URL in Alembic config
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Add your model's MetaData object here
target_metadata = Base.metadata

def get_revision_dependencies() -> List[str]:
    """Get list of revision dependencies.
    
    Returns:
        List of revision identifiers that this revision depends on
    """
    # Add any revision dependencies here
    return []

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection: Connection) -> None:
    """Run actual migrations.
    
    Args:
        connection: Database connection
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table="alembic_version",
        include_schemas=True,
        include_object=lambda obj, name, type_, reflected, compare_to: True
    )

    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations() -> None:
    """Run migrations in async context."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = DATABASE_URL
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    try:
        # Create the engine with echo=True for SQL logging
        logger.info("Creating database engine...")
        engine = create_engine(DATABASE_URL, echo=True)
        logger.info("Created database engine")
        
        with engine.connect() as connection:
            logger.info("Connected to database")
            logger.info("Configuring alembic context...")
            
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
                compare_server_default=True,
                transaction_per_migration=False,  # Use a single transaction
                render_as_batch=False  # Don't use batch mode
            )
            logger.info("Configured alembic context")

            logger.info("Beginning migrations...")
            with context.begin_transaction():
                context.run_migrations()
                logger.info("Completed migrations successfully")
    except Exception as e:
        logger.error(f"Error during migration: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        raise

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online() 