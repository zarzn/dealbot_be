"""Test fixtures."""

import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from core.config.test import settings
from core.database import Base
from core.models import User
from core.security import get_password_hash
from main import app

# Create test engine
test_engine = create_async_engine(str(settings.SQLALCHEMY_DATABASE_URI))
TestingSessionLocal = sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="function")
async def db():
    """Create database tables."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture(scope="function")
async def client():
    """Create test client."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest_asyncio.fixture(scope="function")
async def test_user(db: AsyncSession):
    """Create test user."""
    user = User(
        email=settings.TEST_USER_EMAIL,
        hashed_password=get_password_hash(settings.TEST_USER_PASSWORD),
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

@pytest_asyncio.fixture(scope="function")
async def test_user_token(client: AsyncClient):
    """Get test user token."""
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": settings.TEST_USER_EMAIL,
            "password": settings.TEST_USER_PASSWORD,
        },
    )
    return response.json()["access_token"]

@pytest_asyncio.fixture(scope="function")
async def authorized_client(client: AsyncClient, test_user_token: str):
    """Create authorized test client."""
    client.headers["Authorization"] = f"Bearer {test_user_token}"
    return client 