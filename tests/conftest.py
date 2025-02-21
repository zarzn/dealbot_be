"""Test configuration module."""

import os

# Set test environment variables before any imports
os.environ["ENVIRONMENT"] = "development"  # Use development environment for main database
os.environ["DEEPSEEK_API_KEY"] = "test-key"
os.environ["OPENAI_API_KEY"] = "test-key"
os.environ["POSTGRES_HOST"] = "localhost"  # Use localhost for testing
os.environ["POSTGRES_PORT"] = "5432"
os.environ["POSTGRES_USER"] = "postgres"
os.environ["POSTGRES_PASSWORD"] = "12345678"
os.environ["POSTGRES_DB"] = "deals"

import asyncio
from typing import AsyncGenerator, Generator, Dict
import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from uuid import uuid4
import jwt
from datetime import datetime, timedelta
from decimal import Decimal
import logging
from sqlalchemy import text

from core.config import get_settings
from core.database import Base, get_db
from core.models.user import User, UserCreate, UserInDB
from core.models.market import Market, MarketType, MarketStatus
from core.models.goal import Goal, GoalCreate, GoalResponse
from core.models.deal import Deal, DealCreate, DealResponse
from main import create_app
from .mocks.redis_mock import AsyncRedisMock

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

settings = get_settings()

# Log the database URL
logger.info(f"Database URL: {settings.SQLALCHEMY_DATABASE_URI}")

# Create async engine for main database
engine = create_async_engine(
    str(settings.SQLALCHEMY_DATABASE_URI),  # Convert PostgresDsn to string
    poolclass=NullPool,
    echo=False,
    pool_pre_ping=True
)

# Create session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def app() -> FastAPI:
    """Create a FastAPI test application."""
    # Create the app
    print("Creating test application...")
    app = create_app()
    app.dependency_overrides[get_db] = get_test_session
    yield app

@pytest.fixture
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a test session for database operations."""
    async with async_session_maker() as session:
        try:
            yield session
            # Rollback any changes made during the test
            await session.rollback()
        except Exception as e:
            await session.rollback()
            raise e
        finally:
            await session.close()

@pytest.fixture
async def async_client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Get a test client for making HTTP requests."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture
async def test_user(async_session: AsyncSession) -> User:
    """Create a test user."""
    user = await User.create(
        async_session,
        email="test@example.com",
        name="Test User",
        password="hashed_password",  # In real app, this would be hashed
        status="active",
        token_balance=Decimal("100.0")
    )
    return user

@pytest.fixture
async def auth_headers(test_user: User) -> Dict[str, str]:
    """Get authentication headers."""
    access_token = jwt.encode(
        {
            "sub": str(test_user.id),
            "exp": datetime.utcnow() + timedelta(days=1),
            "type": "access"
        },
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    
    return {
        "Authorization": f"Bearer {access_token}",
        "user_id": str(test_user.id)
    }

@pytest.fixture
async def test_market(async_session: AsyncSession) -> Market:
    """Create a test market."""
    market = Market(
        name="Test Market",
        type=MarketType.AMAZON.value,  # Use .value to get the lowercase string
        status=MarketStatus.ACTIVE.value,  # Use .value to get the lowercase string
        rate_limit=100,
        is_active=True,
        error_count=0,
        requests_today=0,
        total_requests=0,
        success_rate=1.0,
        avg_response_time=0.0
    )
    async_session.add(market)
    await async_session.flush()
    return market

@pytest.fixture
async def test_goal(async_session: AsyncSession, test_user: User) -> Goal:
    """Create a test goal."""
    goal = Goal(
        user_id=test_user.id,
        title="Test Goal",
        item_category="electronics",
        constraints={
            "max_price": 1000,
            "min_price": 500,
            "brands": ["Test"],
            "conditions": ["new"]
        }
    )
    async_session.add(goal)
    await async_session.flush()  # Use flush instead of commit
    return goal

@pytest.fixture
async def test_deal(async_session: AsyncSession, test_user: User, test_market: Market, test_goal: Goal) -> Deal:
    """Create a test deal."""
    deal = Deal(
        user_id=test_user.id,
        goal_id=test_goal.id,
        market_id=test_market.id,
        title="Test Deal",
        description="Test deal description",
        url="https://example.com/test-deal",
        price=Decimal("99.99"),
        original_price=Decimal("149.99"),
        currency="USD",
        source="amazon",
        category="electronics",
        status="active"
    )
    async_session.add(deal)
    await async_session.flush()  # Use flush instead of commit
    return deal

async def get_test_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a test database session."""
    async with async_session_maker() as session:
        yield session

@pytest.fixture(autouse=True)
async def setup_and_teardown(async_session: AsyncSession):
    """Setup before each test and cleanup after."""
    # Setup - create necessary database objects
    try:
        # Create enum types if they don't exist
        await async_session.execute(text("""
            DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'userstatus') THEN
                    CREATE TYPE userstatus AS ENUM ('active', 'inactive', 'suspended', 'deleted');
                END IF;
                
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'markettype') THEN
                    CREATE TYPE markettype AS ENUM ('amazon', 'walmart', 'ebay', 'target', 'bestbuy');
                END IF;
                
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'market_status') THEN
                    CREATE TYPE market_status AS ENUM ('active', 'inactive', 'maintenance', 'rate_limited', 'error');
                END IF;

                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'currency') THEN
                    CREATE TYPE currency AS ENUM ('USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY');
                END IF;

                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'token_operation') THEN
                    CREATE TYPE token_operation AS ENUM ('deduction', 'reward', 'refund', 'transfer', 'purchase');
                END IF;
            END $$;
        """))
        await async_session.commit()
    except Exception as e:
        logger.warning(f"Enum type creation skipped (might already exist): {e}")
        await async_session.rollback()
    
    yield
    
    # Cleanup - clear all tables
    try:
        await async_session.execute(text("""
            TRUNCATE users, goals, deals, notifications, auth_tokens, markets,
                    token_transactions, token_balance_history 
            CASCADE;
        """))
        await async_session.commit()
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        await async_session.rollback()

@pytest.fixture
async def redis_mock():
    """Create Redis mock instance for testing."""
    redis = AsyncRedisMock()
    await redis.auth("test_password")
    yield redis
    await redis.close()  # This will clear all data

@pytest.fixture(autouse=True)
def mock_redis_dependency(app: FastAPI, redis_mock):
    """Override Redis dependency in FastAPI app."""
    async def get_test_redis():
        return redis_mock
    
    # Store original dependency
    original = app.dependency_overrides.get("get_redis")
    
    # Override with test dependency
    app.dependency_overrides["get_redis"] = get_test_redis
    
    yield
    
    # Restore original dependency if it existed
    if original:
        app.dependency_overrides["get_redis"] = original
    else:
        app.dependency_overrides.pop("get_redis", None)

@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    from pydantic import SecretStr
    
    class MockSettings:
        """Mock settings for testing."""
        
        def __init__(self):
            self.SCRAPER_API_KEY = SecretStr("34b092724b61ff18f116305a51ee77e7")
            self.SCRAPER_API_BASE_URL = "http://api.scraperapi.com"
            self.SCRAPER_API_CONCURRENT_LIMIT = 25
            self.SCRAPER_API_REQUESTS_PER_SECOND = 3
            self.SCRAPER_API_MONTHLY_LIMIT = 200_000
            self.SCRAPER_API_TIMEOUT = 70
            self.SCRAPER_API_CACHE_TTL = 1800
            self.SCRAPER_API_BACKGROUND_CACHE_TTL = 7200
            self.JWT_SECRET_KEY = "test_secret_key"
            self.JWT_ALGORITHM = "HS256"
    
    return MockSettings() 