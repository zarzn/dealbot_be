"""Script to add market_search pricing record to the token_pricing table.

This script adds the missing market_search pricing record to the token_pricing table
to fix the issue with the market search workflow.
"""

import asyncio
import logging
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection parameters
DB_USER = "postgres"
DB_PASSWORD = "12345678"
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "deals"

# Async database URL
ASYNC_DB_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

async def add_market_search_pricing():
    """Add market_search pricing record to the token_pricing table."""
    try:
        # Create async engine and session
        engine = create_async_engine(ASYNC_DB_URL)
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        
        async with async_session() as session:
            # Check if market_search pricing already exists
            result = await session.execute(
                text("SELECT * FROM token_pricing WHERE service_type = 'market_search'")
            )
            existing_record = result.fetchone()
            
            if existing_record:
                logger.info("market_search pricing record already exists")
                return
            
            # Add market_search pricing record
            now = datetime.now(timezone.utc)
            await session.execute(
                text("""
                    INSERT INTO token_pricing 
                    (id, service_type, token_cost, valid_from, is_active, created_at, updated_at)
                    VALUES 
                    (:id, :service_type, :token_cost, :valid_from, :is_active, :created_at, :updated_at)
                """),
                {
                    "id": str(uuid4()),
                    "service_type": "market_search",
                    "token_cost": 2.0,  # Set appropriate token cost
                    "valid_from": now,
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now
                }
            )
            
            await session.commit()
            logger.info("Successfully added market_search pricing record")
            
    except Exception as e:
        logger.error(f"Failed to add market_search pricing record: {str(e)}")
        raise

async def main():
    """Main function to run the script."""
    logger.info("Starting to add market_search pricing record...")
    await add_market_search_pricing()
    logger.info("Completed adding market_search pricing record")

if __name__ == "__main__":
    asyncio.run(main()) 