"""Test configuration and fixtures."""

import os
import pytest
import logging
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from fastapi import FastAPI
from httpx import AsyncClient

from core.database import Base
from core.config import get_settings, Settings
from core.services.redis import get_redis_service
from utils.state import state_manager
from utils.markers import register_markers
from tests.mocks.redis_mock import get_redis_mock

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Register markers
def pytest_configure(config):
    """Configure pytest with custom markers."""
    register_markers(config)

# Test settings
@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Create test settings."""
    settings = get_settings()
    settings.TESTING = True
    settings.DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/deals_test"
    settings.REDIS_URL = "redis://localhost:6379/1"
    settings.JWT_SECRET_KEY = "test-secret-key"
    return settings

# Database fixtures
@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop."""
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def test_engine(test_settings):
    """Create test database engine."""
    engine = create_async_engine(
        test_settings.DATABASE_URL,
        echo=True,
        future=True,
        poolclass=NullPool
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()

@pytest.fixture
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    TestingSessionLocal = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )
    
    async with TestingSessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()

# Redis fixtures
@pytest.fixture
async def redis_mock():
    """Create Redis mock."""
    mock = get_redis_mock()
    await mock.init()
    mock.data.clear()
    mock._blacklist.clear()
    yield mock
    await mock.close()

# Application fixtures
@pytest.fixture
async def app(test_settings, test_session, redis_mock) -> FastAPI:
    """Create test application."""
    from core.main import app
    
    # Override settings
    app.state.settings = test_settings
    
    # Override dependencies
    async def override_get_db():
        yield test_session
    
    async def override_get_redis():
        return redis_mock
    
    app.dependency_overrides[get_redis_service] = override_get_redis
    
    return app

@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Create test client."""
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        yield client

# State management fixtures
@pytest.fixture(autouse=True)
def manage_test_state(request):
    """Manage test state for each test."""
    marker_names = [marker.name for marker in request.node.iter_markers()]
    
    # Reset state for relevant features
    for marker in marker_names:
        if marker in state_manager._dependencies:
            state_manager.reset_state(marker)
    
    yield
    
    # Update state based on test result
    for marker in marker_names:
        if marker in state_manager._dependencies:
            if request.node.rep_call.passed:
                state_manager.mark_test_passed(marker)
            else:
                state_manager.mark_test_failed(marker)

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Store test results for state management."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)

# Cleanup
@pytest.fixture(scope="function", autouse=True)
async def cleanup_after_test(test_session):
    """Clean up after each test."""
    yield
    await test_session.rollback() 