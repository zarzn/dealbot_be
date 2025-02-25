"""Test configuration module."""

import os
import logging
import asyncio
from typing import Generator, Dict, AsyncGenerator
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text, delete
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
import jwt
import httpx
import pytest_asyncio
from pydantic import SecretStr
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.orm import DeclarativeBase
from core.services.redis import get_redis_service
from core.config import get_settings, Settings
from core.database import get_db, Base, async_engine as app_async_engine, AsyncSessionLocal as AppAsyncSessionLocal
from core.services.email.backends.console import ConsoleEmailBackend
from core.models.user import User
from core.models.deal import Deal
from core.models.market import Market
from core.models.enums import UserStatus, MarketType, MarketStatus
from core.utils.redis import get_redis_client, close_redis_client
from main import create_app
from core.config import settings
from core.models.goal import Goal
from core.models.price_tracking import PricePoint, PriceTracker
from core.models.notification import Notification
from core.models.token import TokenTransaction, TokenBalanceHistory
from core.schemas.auth import AuthResponse, RegisterRequest, LoginRequest
from core.api.v1.router import router as api_router
from httpx import AsyncClient
from sqlalchemy import select
from core.utils.security import get_password_hash
from tests.mocks.redis_mock import get_redis_mock

# Configure logger
logger = logging.getLogger(__name__)

# Test settings
settings = get_settings()

# Set test environment variables
os.environ["TESTING"] = "1"
os.environ["DATABASE_URL"] = "postgresql://postgres:12345678@localhost:5432/deals"
os.environ["REDIS_URL"] = "redis://localhost:6379/1"
os.environ["REDIS_HOST"] = "localhost"
os.environ["REDIS_PORT"] = "6379"
os.environ["REDIS_DB"] = "1"
os.environ["JWT_SECRET_KEY"] = "test-secret-key"
os.environ["API_URL"] = "http://localhost:8000"
os.environ["FRONTEND_URL"] = "http://localhost:3000"
os.environ["SCRAPER_API_KEY"] = "test-scraper-api-key"

@pytest.fixture
def mock_settings() -> Settings:
    """Create mock settings for testing."""
    settings = Settings(
        DATABASE_URL="postgresql://postgres:12345678@localhost:5432/deals",
        REDIS_URL="redis://localhost:6379/1",
        REDIS_HOST="localhost",
        REDIS_PORT=6379,
        REDIS_DB=1,
        JWT_SECRET_KEY="test-secret-key",
        API_URL="http://localhost:8000",
        FRONTEND_URL="http://localhost:3000",
        SECRET_KEY=SecretStr("test-secret-key"),
        JWT_SECRET=SecretStr("test-secret-key"),
        SCRAPER_API_KEY=SecretStr("test-scraper-api-key"),
        SCRAPER_API_BASE_URL="https://api.scraperapi.com",
        SCRAPER_API_CONCURRENT_LIMIT=10,
        SCRAPER_API_REQUESTS_PER_SECOND=5,
        SCRAPER_API_MONTHLY_LIMIT=10000,
        SCRAPER_API_TIMEOUT=30,
        SCRAPER_API_CACHE_TTL=3600,
        SCRAPER_API_BACKGROUND_CACHE_TTL=7200,
        DEEPSEEK_API_KEY=SecretStr("test-deepseek-key"),
        OPENAI_API_KEY=SecretStr("test-openai-key"),
        FCM_PROJECT_ID="test-fcm-project",
        FCM_PRIVATE_KEY="test-fcm-key",
        FCM_CLIENT_EMAIL="test@fcm.com",
        DEBUG=True
    )
    return settings

# Create test engine
test_engine = create_async_engine(
    os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+asyncpg://"),
    echo=True,
    future=True,
    poolclass=NullPool
)

# Create test session factory
TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Initialize email backend for testing
email_backend = ConsoleEmailBackend()

@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_test_database():
    """Create test database tables."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture(scope="function")
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    """Create async session for testing."""
    async with TestingSessionLocal() as session:
        # Start a nested transaction
        async with session.begin():
            try:
                # Clear all tables before each test
                for table in reversed(Base.metadata.sorted_tables):
                    await session.execute(delete(table))
                await session.flush()
                
                yield session
            finally:
                # Rollback the nested transaction
                await session.rollback()
                await session.close()

@pytest.fixture
async def redis_mock():
    """Redis mock fixture for testing."""
    mock = get_redis_mock()
    await mock.init()
    # Clear any existing data
    mock.data.clear()
    mock._blacklist.clear()
    yield mock
    await mock.close()

@pytest.fixture
def test_settings():
    """Create test settings."""
    settings.TESTING = True
    settings.DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/deals_test"
    settings.REDIS_URL = "redis://localhost:6379/1"
    settings.JWT_SECRET_KEY = "test-secret-key"  # Use plain string for testing
    settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 30
    settings.JWT_REFRESH_TOKEN_EXPIRE_MINUTES = 10080  # 7 days in minutes
    settings.JWT_ALGORITHM = "HS256"
    return settings

@pytest.fixture
async def app(test_settings):
    """Create test application."""
    from core.main import app
    from core.api.v1.dependencies import get_db, get_redis_client
    
    # Override settings
    app.state.settings = test_settings
    
    # Override dependencies
    async def override_get_db():
        async with TestingSessionLocal() as session:
            yield session
    
    async def override_get_redis():
        redis_mock = get_redis_mock()
        await redis_mock.init()
        return redis_mock
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis_client] = override_get_redis
    
    return app

@pytest.fixture
async def test_client(app: FastAPI) -> AsyncClient:
    """Create test client."""
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        yield client

@pytest.fixture
async def async_client(app: FastAPI) -> AsyncClient:
    """Create async test client."""
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        yield client

@pytest_asyncio.fixture
async def existing_user(async_session: AsyncSession) -> AsyncGenerator[User, None]:
    """Create test user for login tests."""
    # First try to find existing user
    stmt = select(User).where(User.email == "test@example.com")
    result = await async_session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        # Create new user if not exists
        user_data = {
            "email": "test@example.com",
            "name": "Test User",
            "password": "testpassword123"
        }
        hashed_password = get_password_hash(user_data["password"])
        user = User(
            email=user_data["email"],
            password=hashed_password,
            name=user_data["name"],
            status=UserStatus.ACTIVE
        )
        async_session.add(user)
        await async_session.flush()
        await async_session.refresh(user)
    
    yield user
    
    # Clean up after test
    await async_session.execute(
        delete(User).where(User.email == "test@example.com")
    )
    await async_session.flush()

@pytest_asyncio.fixture
async def test_market(async_session):
    """Create test market."""
    market = Market(
        name="Test Market",
        type="test",
        api_endpoint="http://test.com",
        api_key="test_key",
        status="active"
    )
    async_session.add(market)
    await async_session.commit()
    await async_session.refresh(market)
    return market

@pytest.fixture
def auth_headers(test_user):
    """Create auth headers for testing."""
    return {
        "Authorization": f"Bearer test_token",
        "user-id": str(test_user.id)  # Add user ID to headers for tests
    }

@pytest.fixture
def test_token(existing_user) -> str:
    """Create a test JWT token."""
    payload = {
        "sub": str(existing_user.id),
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )

@pytest.fixture
async def redis_sorted_set(redis_test_client):
    """Create a test sorted set in Redis."""
    key = "test:sorted_set"
    test_data = {
        "member1": 1.0,
        "member2": 2.0,
        "member3": 3.0
    }
    for member, score in test_data.items():
        await redis_test_client.zadd(key, score, member)
    yield key, test_data
    await redis_test_client.delete(key)

@pytest.fixture
async def redis_set(redis_test_client):
    """Create a test set in Redis."""
    key = "test:set"
    test_data = {"member1", "member2", "member3"}
    await redis_test_client.sadd(key, *test_data)
    yield key, test_data
    await redis_test_client.delete(key)

@pytest.fixture
async def redis_pubsub(redis_test_client):
    """Create a test pub/sub connection in Redis."""
    channel = "test:channel"
    pubsub = await redis_test_client.subscribe(channel)
    yield channel, pubsub
    await redis_test_client.unsubscribe(channel)

@pytest.fixture
async def redis_stream(redis_test_client):
    """Create a test stream in Redis."""
    stream = "test:stream"
    test_data = [
        {"field1": "value1", "field2": "value2"},
        {"field1": "value3", "field2": "value4"},
        {"field1": "value5", "field2": "value6"}
    ]
    message_ids = []
    for data in test_data:
        message_id = await redis_test_client.xadd(stream, data)
        message_ids.append(message_id)
    yield stream, test_data, message_ids
    await redis_test_client.delete(stream)

@pytest.fixture
async def redis_consumer_group(redis_test_client, redis_stream):
    """Create a test consumer group in Redis."""
    stream, _, _ = redis_stream
    group = "test:group"
    consumer = "test:consumer"
    await redis_test_client.xgroup_create(stream, group, mkstream=True)
    yield stream, group, consumer
    await redis_test_client.xgroup_destroy(stream, group)

@pytest.fixture
async def redis_pending_messages(redis_test_client, redis_consumer_group):
    """Create test pending messages in Redis."""
    stream, group, consumer = redis_consumer_group
    # Add test messages and read them without acknowledging
    message_ids = []
    test_data = [
        {"field1": "pending1", "field2": "value1"},
        {"field1": "pending2", "field2": "value2"}
    ]
    for data in test_data:
        message_id = await redis_test_client.xadd(stream, data)
        message_ids.append(message_id)
    
    # Read messages without acknowledging to create pending entries
    await redis_test_client.xreadgroup(group, consumer, {stream: ">"})
    yield stream, group, consumer, message_ids, test_data

@pytest.fixture
async def redis_transaction(redis_test_client):
    """Create a test transaction in Redis."""
    key1, key2 = "test:trans1", "test:trans2"
    
    # Set initial values
    await redis_test_client.set(key1, "value1")
    await redis_test_client.set(key2, "value2")
    
    async def transaction_func(tr, **kwargs):
        tr.set(key1, "new_value1")
        tr.set(key2, "new_value2")
        return tr
    
    yield key1, key2, transaction_func
    
    # Cleanup
    await redis_test_client.delete(key1)
    await redis_test_client.delete(key2)

@pytest.fixture
async def redis_script(redis_test_client):
    """Create a test Lua script in Redis."""
    # Simple increment script
    script = """
    local key = KEYS[1]
    local increment = ARGV[1]
    local value = redis.call('GET', key)
    if not value then
        value = 0
    end
    value = value + increment
    redis.call('SET', key, value)
    return value
    """
    
    key = "test:script:counter"
    await redis_test_client.set(key, "0")
    sha = await redis_test_client.script_load(script)
    
    yield key, script, sha
    
    # Cleanup
    await redis_test_client.delete(key)
    await redis_test_client.script_flush()

@pytest.fixture
async def redis_hyperloglog(redis_test_client):
    """Create test HyperLogLog structures in Redis."""
    key1, key2 = "test:hll1", "test:hll2"
    elements1 = ["a", "b", "c", "d"]
    elements2 = ["c", "d", "e", "f"]
    
    # Add elements to HyperLogLogs
    await redis_test_client.pfadd(key1, *elements1)
    await redis_test_client.pfadd(key2, *elements2)
    
    yield key1, key2, elements1, elements2
    
    # Cleanup
    await redis_test_client.delete(key1)
    await redis_test_client.delete(key2)

@pytest.fixture
async def redis_geo(redis_test_client):
    """Create test geospatial data in Redis."""
    key = "test:geo"
    locations = {
        "New York": (-74.006015, 40.712784),
        "London": (-0.127758, 51.507351),
        "Tokyo": (139.691706, 35.689487),
        "Sydney": (151.209296, -33.868820)
    }
    
    # Add locations to geo index
    for name, (longitude, latitude) in locations.items():
        await redis_test_client.geoadd(key, longitude, latitude, name)
    
    yield key, locations
    
    # Cleanup
    await redis_test_client.delete(key)

@pytest.fixture
async def redis_bitmap(redis_test_client):
    """Create test bitmap data in Redis."""
    key1, key2 = "test:bitmap1", "test:bitmap2"
    
    # Set some bits in the bitmaps
    for i in range(0, 8):
        await redis_test_client.setbit(key1, i, i % 2 == 0)
        await redis_test_client.setbit(key2, i, i % 2 == 1)
    
    yield key1, key2
    
    # Cleanup
    await redis_test_client.delete(key1)
    await redis_test_client.delete(key2)

@pytest.fixture
async def redis_cluster(redis_test_client):
    """Create test cluster data in Redis."""
    # Note: This is a mock cluster setup since we're using a standalone Redis
    # Real cluster operations should be tested with an actual Redis Cluster
    keys = [
        "test:cluster:key1",
        "test:cluster:key2",
        "test:cluster:key3"
    ]
    
    # Set some test data
    for i, key in enumerate(keys):
        await redis_test_client.set(key, f"value{i}")
    
    yield keys
    
    # Cleanup
    for key in keys:
        await redis_test_client.delete(key)

@pytest.fixture
async def redis_scan(redis_test_client):
    """Create test data for scanning in Redis."""
    # Create test data for different data structures
    key_prefix = "test:scan:"
    
    # Regular keys
    keys = [f"{key_prefix}key{i}" for i in range(5)]
    for i, key in enumerate(keys):
        await redis_test_client.set(key, f"value{i}")
    
    # Set
    set_key = f"{key_prefix}set"
    set_members = [f"member{i}" for i in range(5)]
    await redis_test_client.sadd(set_key, *set_members)
    
    # Hash
    hash_key = f"{key_prefix}hash"
    hash_fields = {f"field{i}": f"value{i}" for i in range(5)}
    await redis_test_client.set_hash(hash_key, hash_fields)
    
    # Sorted set
    zset_key = f"{key_prefix}zset"
    zset_members = {f"member{i}": float(i) for i in range(5)}
    for member, score in zset_members.items():
        await redis_test_client.zadd(zset_key, score, member)
    
    yield {
        "keys": keys,
        "set": (set_key, set_members),
        "hash": (hash_key, hash_fields),
        "zset": (zset_key, zset_members)
    }
    
    # Cleanup
    for key in keys:
        await redis_test_client.delete(key)
    await redis_test_client.delete(set_key)
    await redis_test_client.delete(hash_key)
    await redis_test_client.delete(zset_key)

@pytest.fixture
async def redis_pipeline(redis_test_client):
    """Create a test pipeline in Redis."""
    key1, key2 = "test:pipeline1", "test:pipeline2"
    
    # Create a pipeline
    pipeline = await redis_test_client.pipeline()
    
    # Add some commands to the pipeline
    pipeline.set(key1, "value1")
    pipeline.set(key2, "value2")
    pipeline.get(key1)
    pipeline.get(key2)
    
    yield pipeline, key1, key2
    
    # Cleanup
    await redis_test_client.delete(key1)
    await redis_test_client.delete(key2)

@pytest.fixture
async def redis_monitor(redis_test_client):
    """Create a test monitoring setup in Redis."""
    # Get initial server info
    info = await redis_test_client.info()
    
    # Get initial client list
    clients = await redis_test_client.client_list()
    
    # Get current client ID
    client_id = await redis_test_client.client_id()
    
    yield info, clients, client_id

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def test_app() -> FastAPI:
    """Create test FastAPI app."""
    app = FastAPI()
    app.include_router(api_router, prefix=settings.API_V1_STR)
    return app

async def close_redis_pool():
    """Close Redis connection pool."""
    if hasattr(close_redis_pool, "pool"):
        await close_redis_pool.pool.close()

@pytest.fixture(scope="session", autouse=True)
async def cleanup_redis():
    """Cleanup Redis after tests."""
    yield
    await close_redis_pool()