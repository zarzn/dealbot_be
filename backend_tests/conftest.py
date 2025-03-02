"""
Test configuration for the AI Agentic Deals System.

This module sets up the test environment, including database connections,
Redis connections, test fixtures, and other test-specific configurations.
"""

import os
import sys
import asyncio
import pytest
import uuid
from pathlib import Path
from typing import AsyncGenerator, Dict, Any, List, Optional, Generator

# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent
sys.path.append(str(backend_dir))

# Set testing flags in environment
os.environ["TESTING"] = "true"
os.environ["SKIP_TOKEN_VERIFICATION"] = "true"

# Set environment variables for Redis
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["REDIS_HOST"] = "localhost"
os.environ["REDIS_PORT"] = "6379"
os.environ["REDIS_DB"] = "0"
os.environ["REDIS_PASSWORD"] = ""
os.environ["host"] = "localhost"
os.environ["hosts"] = "[\"localhost\"]"

# Load environment variables from .env.test file
from dotenv import load_dotenv
env_test_file = backend_dir / '.env.test'
if env_test_file.exists():
    print(f"Loading test environment from: {env_test_file}")
    load_dotenv(env_test_file, override=True)
else:
    print(f"Warning: {env_test_file} not found, using default test configuration")
    # Set default test environment variables if .env.test is not found
    os.environ.setdefault("APP_NAME", "AI Agentic Deals System Test")
    os.environ.setdefault("POSTGRES_USER", "postgres")
    os.environ.setdefault("POSTGRES_PASSWORD", "12345678")
    os.environ.setdefault("POSTGRES_HOST", "localhost")
    os.environ.setdefault("POSTGRES_PORT", "5432")
    os.environ.setdefault("POSTGRES_DB", "deals_test")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
    os.environ.setdefault("REDIS_PASSWORD", "")
    os.environ.setdefault("REDIS_HOST", "localhost")
    os.environ.setdefault("host", "localhost")  # Required by Pydantic
    os.environ.setdefault("hosts", "[\"localhost\"]")  # Required by Pydantic
    os.environ.setdefault("JWT_SECRET", "test_jwt_secret_key_for_testing_only")
    os.environ.setdefault("DEEPSEEK_API_KEY", "test_deepseek_api_key")
    os.environ.setdefault("OPENAI_API_KEY", "test_openai_api_key")

# Force reload of settings module to pick up environment variables
if 'core.config.settings' in sys.modules:
    del sys.modules['core.config.settings']
if 'core.config' in sys.modules:
    del sys.modules['core.config']

# Import the rest of the application after environment is configured
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient

# Create Redis mock module if it doesn't exist
import sys
from unittest.mock import MagicMock

# Create a mock Redis implementation
class RedisMock(MagicMock):
    async def get(self, *args, **kwargs):
        return None
    
    async def set(self, *args, **kwargs):
        return True
    
    async def delete(self, *args, **kwargs):
        return 0
    
    async def exists(self, *args, **kwargs):
        return False
    
    async def flushdb(self, *args, **kwargs):
        return True
    
    async def close(self, *args, **kwargs):
        return None
    
    async def blacklist_token(self, *args, **kwargs):
        return True
    
    async def is_token_blacklisted(self, *args, **kwargs):
        return False

redis_mock = RedisMock()

def patch_redis_service():
    """Patch Redis service for all tests."""
    return MagicMock()

# Import only what we need from core
from core.database import Base, get_session
from core.main import app
from core.services.redis import get_redis_service, RedisService

# Test database URL
TEST_DATABASE_URL = f"postgresql+asyncpg://{os.environ.get('POSTGRES_USER')}:{os.environ.get('POSTGRES_PASSWORD')}@{os.environ.get('POSTGRES_HOST')}:{os.environ.get('POSTGRES_PORT')}/{os.environ.get('POSTGRES_DB')}"

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
    from backend_tests.utils.test_client import APITestClient
    
    # Create a test client with our modified app
    async with AsyncClient(app=app, base_url="http://testserver") as async_client:
        # Wrap with our APITestClient for path handling
        api_client = APITestClient(async_client)
        yield api_client
    
    # Clean up
    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
async def redis_client():
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
    # Import here to avoid circular imports
    try:
        from backend_tests.utils.state import state_manager
        state_manager.reset()
    except ImportError:
        pass
    
    # Reset UserFactory sequence if it exists
    try:
        from backend_tests.factories import UserFactory
        UserFactory._sequence = 1
    except (ImportError, AttributeError):
        pass
        
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

# Test data fixtures
@pytest.fixture
def test_user_data():
    """Return test user data."""
    return {
        "email": f"test-{uuid.uuid4()}@example.com",
        "username": f"testuser-{uuid.uuid4()}",
        "password": "testpassword123",
        "full_name": "Test User",
    }

@pytest.fixture
def test_deal_data():
    """Return test deal data."""
    return {
        "title": f"Test Deal {uuid.uuid4()}",
        "description": "This is a test deal",
        "status": "draft",
        "market_type": "crypto",
        "metadata": {"test": True, "priority": "high"},
    }

@pytest.fixture
def test_market_data():
    """Return test market data."""
    return {
        "name": f"Test Market {uuid.uuid4()}",
        "description": "This is a test market",
        "type": "crypto",
        "metadata": {"test": True, "region": "global"},
    }

@pytest.fixture
def test_token_data():
    """Return test token data."""
    return {
        "name": f"Test Token {uuid.uuid4()}",
        "symbol": f"TT{uuid.uuid4().hex[:4].upper()}",
        "status": "active",
        "metadata": {"decimals": 18, "network": "ethereum"},
    }

@pytest.fixture
def test_goal_data():
    """Return test goal data."""
    return {
        "title": f"Test Goal {uuid.uuid4()}",
        "description": "This is a test goal",
        "status": "pending",
        "priority": 1,
        "metadata": {"category": "financial", "difficulty": "medium"},
    } 