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
from httpx import AsyncClient

# Configure Pydantic to allow arbitrary types globally
BaseModel.model_config = ConfigDict(arbitrary_types_allowed=True)

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Set testing flag
os.environ["TESTING"] = "true"
os.environ["SKIP_TOKEN_VERIFICATION"] = "true"

# Set Redis configuration
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["REDIS_HOST"] = "localhost"
os.environ["REDIS_PORT"] = "6379"
os.environ["REDIS_DB"] = "0"
os.environ["REDIS_PASSWORD"] = "your_redis_password"

# Override database URL to use localhost instead of postgres
os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:12345678@localhost:5432/deals_test"
os.environ["POSTGRES_HOST"] = "localhost"

# Load environment variables from .env.development
env_file = backend_dir / '.env.development'
load_dotenv(env_file)

# Test database URL
TEST_DATABASE_URL = "postgresql+asyncpg://postgres:12345678@localhost:5432/deals_test"

# Test Redis URL - use localhost for tests
TEST_REDIS_URL = f"redis://:{os.environ['REDIS_PASSWORD']}@localhost:6379/1"  # Use DB 1 for tests

# Import after environment variables are set
from core.config import settings

# Override settings directly
settings.DATABASE_URL = TEST_DATABASE_URL
settings.REDIS_URL = TEST_REDIS_URL
settings.REDIS_HOST = "localhost"

# Now import the rest of the modules
from core.database import Base, get_session
from core.main import app
from core.services.redis import get_redis_service, RedisService
from core.models.token_models import Token
from backend_tests.utils.state import state_manager
from backend_tests.factories import UserFactory
from backend_tests.mocks.redis_mock import redis_mock, patch_redis_service

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
    # Database settings should already be overridden
    
    async with test_engine.begin() as conn:
        # Create tables
        await conn.run_sync(Base.metadata.create_all)
    
    yield test_engine
    
    # Drop tables after tests
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
async def client(db_session) -> AsyncGenerator:
    """Create a test client with a fresh database session."""
    # Import the app instance from core.main
    from core.main import app
    
    # Define override function that yields the session
    async def override_get_session():
        try:
            yield db_session
        finally:
            pass
            
    # Define override for Redis service
    async def override_redis_service():
        return redis_mock
    
    # Apply all dependency overrides
    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_redis_service] = override_redis_service
    
    # Import the APITestClient wrapper
    from backend_tests.utils.test_client import APITestClient, create_api_test_client
    
    # Create a TestClient with our modified app
    async with AsyncClient(app=app, base_url="http://testserver") as async_client:
        # Wrap with our APITestClient for path handling
        api_client = APITestClient(async_client)
        yield api_client
    
    # Clean up
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

# Add a fixture for test tokens
@pytest.fixture
def test_token() -> str:
    """Generate a test token that will be accepted in the test environment."""
    return "test_token"

# Add a fixture for authenticated client
@pytest.fixture
async def auth_client(client, test_token) -> AsyncGenerator:
    """Create an authenticated test client."""
    # Set the authorization header with the test token
    client.client.headers.update({"Authorization": f"Bearer {test_token}"})
    yield client 