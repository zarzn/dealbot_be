"""Configure test environment."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict
import pytest
import asyncio
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from redis.asyncio import Redis
import redis.asyncio as aioredis
from pydantic.json import pydantic_encoder
import json
from datetime import datetime, date, timezone
from decimal import Decimal
from uuid import UUID

# Configure Pydantic to allow arbitrary types globally
BaseModel.model_config = ConfigDict(arbitrary_types_allowed=True)

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Import after Pydantic configuration
from core.database import Base, get_session
from core.config import settings
from core.main import app
from core.services.redis import get_redis_service, RedisService
from core.models.token_models import Token
from backend_tests.utils.state import state_manager
from backend_tests.factories import UserFactory
from backend_tests.mocks.redis_mock import redis_mock, patch_redis_service

# Set testing flag
os.environ["TESTING"] = "true"

# Set Redis configuration
os.environ["REDIS_URL"] = "redis://redis:6379/0"
os.environ["REDIS_HOST"] = "redis"
os.environ["REDIS_PORT"] = "6379"
os.environ["REDIS_DB"] = "0"
os.environ["REDIS_PASSWORD"] = "your_redis_password"

# Load environment variables from .env.development
env_file = backend_dir / '.env.development'
load_dotenv(env_file)

# Test database URL
TEST_DATABASE_URL = "postgresql+asyncpg://postgres:12345678@localhost:5432/deals_test"

# Test Redis URL - use localhost for tests
TEST_REDIS_URL = f"redis://:{os.environ['REDIS_PASSWORD']}@localhost:6379/1"  # Use DB 1 for tests

# Create test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
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

@pytest.fixture(scope="session", autouse=True)
def patch_redis():
    """Patch Redis service for all tests."""
    patch = patch_redis_service()
    yield
    patch.stop()

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def test_db() -> AsyncGenerator:
    """Set up the test database."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    yield test_engine
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope="function")
async def db_session(test_db) -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh database session for a test."""
    connection = await test_db.connect()
    transaction = await connection.begin()
    
    session = TestingSessionLocal(bind=connection)
    
    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()

@pytest.fixture(scope="function")
async def client(db_session) -> AsyncGenerator[TestClient, None]:
    """Create a test client with a fresh database session."""
    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session
    
    app.dependency_overrides[get_session] = override_get_session
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
async def redis_client() -> AsyncGenerator[Redis, None]:
    """Create a test Redis connection using our mock."""
    # Reset the mock Redis state
    await redis_mock.flushdb()
    
    # Override the get_redis_service function
    app.dependency_overrides[get_redis_service] = lambda: redis_mock
    
    yield redis_mock
    
    # Clean up after test
    await redis_mock.flushdb()
    if get_redis_service in app.dependency_overrides:
        del app.dependency_overrides[get_redis_service]

@pytest.fixture(autouse=True)
def reset_test_state():
    """Reset the test state before each test."""
    state_manager.reset()
    UserFactory._sequence = 1  # Reset UserFactory sequence
    yield 