import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from core.models.user import User
from core.models.enums import UserStatus
from backend_tests.factories.user import UserFactory
from backend_tests.utils.markers import core_test

pytestmark = pytest.mark.asyncio

@core_test
async def test_create_user(db_session):
    """Test creating a user."""
    user = await UserFactory.create_async(
        db_session=db_session,
        name='Test User',
        password='TestPassword123!',
        status=UserStatus.ACTIVE.value
    )
    assert user.email.startswith('test')
    assert user.email.endswith('@example.com')
    assert user.name == 'Test User'
    assert user.status == UserStatus.ACTIVE.value

@core_test
async def test_user_password_hashing(db_session):
    """Test that user passwords are hashed."""
    password = 'TestPassword123!'
    user = await UserFactory.create_async(
        db_session=db_session,
        password=password
    )
    assert user.password != password
    assert user.password.startswith('$2b$')

@core_test
async def test_user_status_validation(db_session):
    """Test that invalid user status raises an error."""
    with pytest.raises(DBAPIError) as exc_info:
        await UserFactory.create_async(
            db_session=db_session,
            password='TestPassword123!',
            status='nonexistent_status'
        )
    assert 'неверное значение для перечисления userstatus' in str(exc_info.value) 