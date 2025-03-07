"""Script to check alembic version in databases.

This script connects to both agentic_deals and agentic_deals_test databases and checks
the current alembic version to verify if migrations have been applied.
"""

import asyncio
import asyncpg
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_alembic_version():
    """Check alembic version in databases."""
    try:
        # Check both main and test databases
        for db_name in ['agentic_deals', 'agentic_deals_test']:
            # Connect to the database
            print(f"\nConnecting to the {db_name} database...")
            conn = await asyncpg.connect(
                user='postgres',
                password='12345678',
                database=db_name,
                host='localhost'
            )
            
            # Get alembic version
            try:
                version = await conn.fetchval('SELECT version_num FROM alembic_version;')
                print(f"Current alembic version in {db_name}: {version}")
            except Exception as e:
                print(f"Error getting alembic version in {db_name}: {str(e)}")
            
            # Close the connection
            await conn.close()
            print(f"Connection to {db_name} closed.")
        
    except Exception as e:
        logger.error(f"Error checking database: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(check_alembic_version()) 