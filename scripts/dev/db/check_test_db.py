"""
Script to check if the test database is set up correctly with all tables.
This script will try to create tables in the test database and verify 
that they exist.
"""

import os
import sys
import asyncio
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

# Import required models
from core.models.base import Base
from core.models.user import User
from core.models.deal import Deal
from core.models.market import Market
from core.models.goal import Goal
from core.models.auth_token import AuthToken
from core.models.token import Token
from core.models.token_transaction import TokenTransaction
from core.models.token_balance import TokenBalance
from core.models.token_balance_history import TokenBalanceHistory
from core.models.token_pricing import TokenPricing
from core.models.token_wallet import TokenWallet, WalletTransaction
from core.models.notification import Notification
from core.models.chat import Chat, ChatMessage
from core.models.chat_context import ChatContext
from core.models.agent import Agent
from core.models.user_preferences import UserPreferences
from core.models.deal_token import DealToken

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Force the root logger to use our configuration
logging.getLogger().setLevel(logging.INFO)
print("Script starting...")

# Default database credentials for Docker
POSTGRES_USER = os.environ.get('POSTGRES_USER', 'postgres')
POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD', '12345678')
POSTGRES_HOST = os.environ.get('POSTGRES_HOST', 'localhost')
POSTGRES_PORT = os.environ.get('POSTGRES_PORT', '5432')

# Test database URL
TEST_DATABASE_URL = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/agentic_deals_test"

# Create test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=True,
    future=True
)

# Test session factory
TestingSessionLocal = sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

async def check_test_db():
    """Check if the test database is set up correctly."""
    logger.info(f"Connecting to database using URL: {TEST_DATABASE_URL}")
    
    try:
        # Drop and recreate all tables
        logger.info("Dropping all tables if they exist...")
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        
        logger.info("Creating all tables...")
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # List all tables
        logger.info("Checking if tables were created...")
        async with TestingSessionLocal() as session:
            result = await session.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
            tables = result.scalars().all()
            
            if not tables:
                logger.error("No tables were created!")
            else:
                logger.info(f"Found {len(tables)} tables in the database:")
                for table in tables:
                    logger.info(f"- {table}")

            # Check for specific tables we need
            required_tables = [
                'users', 'deals', 'markets', 'goals', 'auth_tokens',
                'tokens', 'token_transactions', 'token_balances',
                'token_balance_history', 'token_pricing', 'token_wallets',
                'wallet_transactions', 'notifications', 'chats',
                'chat_messages', 'chat_contexts', 'agents', 'user_preferences',
                'deal_tokens'
            ]
            
            missing_tables = [table for table in required_tables if table not in tables]
            
            if missing_tables:
                logger.error(f"Missing required tables: {', '.join(missing_tables)}")
            else:
                logger.info("All required tables exist!")
                
            # Try to insert a test user
            try:
                logger.info("Attempting to insert a test user...")
                password = "$2b$12$GAbGmit6J08AMdY64FBTiuBCF7sBqLO5/FuXaf4spGrfiTvNn0UbS"  # Hashed "TestPassword123!"
                test_user = User(
                    email="test@example.com",
                    name="Test User",
                    password=password,
                    status="active",
                    email_verified=True
                )
                session.add(test_user)
                await session.commit()
                
                # Check if user was inserted
                result = await session.execute(text("SELECT COUNT(*) FROM users"))
                count = result.scalar()
                
                if count > 0:
                    logger.info(f"Successfully inserted test user! Count: {count}")
                else:
                    logger.error("Failed to insert test user!")
                    
            except Exception as e:
                logger.error(f"Error inserting test user: {str(e)}")
                
    except Exception as e:
        logger.error(f"Error checking test database: {str(e)}")
        raise
    finally:
        await test_engine.dispose()

if __name__ == "__main__":
    print("Starting database check...")
    asyncio.run(check_test_db())
    print("Database check finished.") 