"""Test configuration and fixtures."""

import pytest
import asyncio
from typing import AsyncGenerator, Generator
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from fastapi import FastAPI
from sqlalchemy.sql import text
from tests.mocks.redis_mock import AsyncRedisMock

from core.database import Base
from core.config import get_settings, Settings
from app import create_app

settings = get_settings()

# Create test database engine
test_engine = create_async_engine(
    settings.TEST_DATABASE_URL,
    echo=True,
    future=True
)

# Create test session factory
test_async_session = sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def app() -> FastAPI:
    """Create a fresh database on each test case."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    app = create_app()
    return app

@pytest.fixture
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a test session for database operations."""
    async with test_async_session() as session:
        yield session
        await session.rollback()
        await session.close()

@pytest.fixture
async def test_client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Get a test client for making HTTP requests."""
    async with AsyncClient(
        app=app,
        base_url="http://test",
        follow_redirects=True
    ) as client:
        yield client

@pytest.fixture(autouse=True)
async def setup_and_teardown():
    """Setup before each test and cleanup after."""
    # Setup - can add any initialization code here
    yield
    # Teardown - cleanup after each test
    async with test_engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE notifications CASCADE"))
        await conn.execute(text("TRUNCATE TABLE price_points CASCADE"))
        await conn.execute(text("TRUNCATE TABLE price_trackers CASCADE"))
        await conn.execute(text("TRUNCATE TABLE price_predictions CASCADE"))
        await conn.execute(text("TRUNCATE TABLE deals CASCADE"))

@pytest.fixture
def redis_mock() -> Generator[AsyncRedisMock, None, None]:
    """Provide Redis mock for testing."""
    yield AsyncRedisMock()

@pytest.fixture
def mock_settings(monkeypatch):
    """Mock settings for testing."""
    test_settings = Settings()
    test_settings.SCRAPER_API_KEY = "34b092724b61ff18f116305a51ee77e7"
    test_settings.SCRAPER_API_CONCURRENT_LIMIT = 25
    test_settings.SCRAPER_API_REQUESTS_PER_SECOND = 3
    test_settings.SCRAPER_API_MONTHLY_LIMIT = 200_000
    
    monkeypatch.setattr("core.config.settings", test_settings)
    return test_settings 