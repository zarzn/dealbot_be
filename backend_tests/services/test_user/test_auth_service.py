import pytest
from core.services.auth import AuthService
from core.exceptions import AuthenticationError, InvalidCredentialsError
from factories.user import UserFactory
from utils.markers import service_test, depends_on

pytestmark = pytest.mark.asyncio

@service_test
@depends_on("core.test_models.test_user.test_create_user")
async def test_authenticate_user(db_session):
    """Test user authentication with valid credentials."""
    # Create a test user with known credentials
    user = await UserFactory.create_async(
        db_session=db_session,
        email="test@example.com",
        password="TestPassword123!"
    )
    
    # Test authentication with correct credentials
    authenticated_user = await authenticate_user(
        email="test@example.com",
        password="TestPassword123!",
        db=db_session
    )
    
    assert authenticated_user is not None
    assert authenticated_user.id == user.id
    assert authenticated_user.email == "test@example.com"

@service_test
@depends_on("core.test_models.test_user.test_create_user")
async def test_authentication_failure(db_session):
    """Test authentication failure with invalid credentials."""
    # Create a test user
    await UserFactory.create_async(
        db_session=db_session,
        email="test@example.com",
        password="TestPassword123!"
    )
    
    # Test authentication with incorrect password
    with pytest.raises(InvalidCredentialsError):
        await authenticate_user(
            email="test@example.com",
            password="WrongPassword123!",
            db=db_session
        )
    
    # Test authentication with non-existent user
    with pytest.raises(InvalidCredentialsError):
        await authenticate_user(
            email="nonexistent@example.com",
            password="TestPassword123!",
            db=db_session
        )

@service_test
@depends_on("core.test_models.test_user.test_create_user")
async def test_token_operations(db_session, redis):
    """Test token creation and validation."""
    # Create a test user
    user = await UserFactory.create_async(
        email="test@example.com"
    )
    
    auth_service = AuthService(db_session)
    
    # Create access token
    token = await auth_service.create_access_token(user)
    assert token is not None
    
    # Validate token
    validated_user = await auth_service.validate_token(token)
    assert validated_user.id == user.id
    
    # Test token blacklisting
    await auth_service.blacklist_token(token)
    with pytest.raises(AuthenticationError):
        await auth_service.validate_token(token) 