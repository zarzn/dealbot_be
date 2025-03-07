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
from sqlalchemy import pool, create_engine, text
from sqlalchemy.engine import Connection
from sqlalchemy import engine_from_config

# Configure logging with more detail
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('alembic.env')

# Add parent directory to path for imports
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, parent_dir)
logger.info(f"Added parent directory to path: {parent_dir}")

from core.config import settings
from core.models.base import Base

# Import all models to ensure they are registered with SQLAlchemy
logger.info("Importing models...")
from core.models import *  # This imports all models
logger.info("Models imported successfully")

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Get database URL from settings - prioritize AWS RDS endpoint if in environment variables
postgres_host = os.getenv("POSTGRES_HOST")
postgres_port = os.getenv("POSTGRES_PORT", "5432")
postgres_user = os.getenv("POSTGRES_USER", "postgres")
postgres_password = os.getenv("POSTGRES_PASSWORD", "12345678")
postgres_db = os.getenv("POSTGRES_DB", "agentic_deals")

if postgres_host:
    DATABASE_URL = f"postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{postgres_db}"
    logger.info(f"Using environment database host: {postgres_host}")
else:
    DATABASE_URL = os.getenv("DATABASE_URL", f"postgresql://postgres:12345678@deals_postgres:5432/{postgres_db}")
    logger.info("Using default DATABASE_URL (development)")

logger.info(f"Using database URL: {DATABASE_URL}")

# Set database URL in Alembic config
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Add your model's MetaData object here
target_metadata = Base.metadata
logger.info(f"Loaded metadata with {len(target_metadata.tables)} tables")
for table in target_metadata.tables:
    logger.info(f"Found table in metadata: {table}")

def get_revision_dependencies() -> List[str]:
    """Get list of revision dependencies."""
    return []

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    logger.info("Running migrations in offline mode")
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()
    logger.info("Offline migrations completed")

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    logger.info(f"Using database URL: {DATABASE_URL}")
    
    # Override the sqlalchemy.url in the alembic config
    config.set_main_option("sqlalchemy.url", DATABASE_URL)
    
    # Log tables in metadata
    logger.info(f"Loaded metadata with {len(target_metadata.tables)} tables")
    for table_name in target_metadata.tables:
        logger.info(f"Found table in metadata: {table_name}")

    # Create engine with explicit transaction handling
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.isolation_level"] = "REPEATABLE READ"
    
    logger.info("Creating database engine...")
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    # Test connection and verify current state
    try:
        with connectable.connect() as connection:
            logger.info("Connected to database")
            logger.info("Configuring alembic context...")
            
            # Test query
            result = connection.execute(text("SELECT 1"))
            logger.info("Database connection test successful")
            
            # Log current tables
            logger.info("Current tables in database:")
            result = connection.execute(text(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
            ))
            for row in result:
                logger.info(f"Table before migration: {row[0]}")
            
            connection.commit()
            
            # Configure context with explicit transaction handling
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                transaction_per_migration=True,
                compare_type=True,
                compare_server_default=True,
                include_schemas=True
            )

            logger.info("Configured alembic context")
            logger.info("Beginning migrations...")
            
            try:
                with context.begin_transaction():
                    context.run_migrations()
                    logger.info("Committing transaction...")
                    connection.commit()
                    logger.info("Transaction committed")
                
                # Log tables after migration
                logger.info("Tables after migration:")
                result = connection.execute(text(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
                ))
                for row in result:
                    logger.info(f"Table after migration: {row[0]}")
                
                logger.info("Completed migrations successfully")
                
            except Exception as e:
                logger.error(f"Error during migration: {str(e)}")
                logger.info("Rolling back transaction...")
                connection.rollback()
                logger.info("Transaction rolled back")
                raise
                
    except Exception as e:
        logger.error(f"Error connecting to database: {str(e)}")
        raise

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online() 