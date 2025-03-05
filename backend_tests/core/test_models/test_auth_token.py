"""Tests for the auth token model."""

import pytest
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
import asyncio

from core.models.auth_token import AuthToken, TokenErrorType
from core.models.user import User
from core.models.enums import TokenType, TokenStatus, TokenScope

@pytest.mark.asyncio
@pytest.mark.core
async def test_auth_token_creation(db_session):
    """Test creating an auth token in the database."""
    # Create a user
    user = User(
        email="token_test@example.com",
        name="Token Test User",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create expiration date with timezone info
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    
    # Create an auth token
    token = AuthToken(
        user_id=user.id,
        token="test_token_123456",
        token_type=TokenType.ACCESS.value,
        status=TokenStatus.ACTIVE.value,
        scope=TokenScope.FULL.value,
        expires_at=expires_at,
        meta_data={"device": "test_device"}
    )
    
    # Add to session and commit
    db_session.add(token)
    await db_session.commit()
    await db_session.refresh(token)
    
    # Verify the token was created with an ID
    assert token.id is not None
    assert isinstance(token.id, uuid.UUID)
    assert token.token == "test_token_123456"
    assert token.token_type == TokenType.ACCESS.value
    assert token.status == TokenStatus.ACTIVE.value
    assert token.scope == TokenScope.FULL.value
    assert token.user_id == user.id
    
    # Verify metadata
    assert token.meta_data["device"] == "test_device"
    
    # Verify created_at and updated_at were set
    assert token.created_at is not None
    assert token.updated_at is not None
    assert isinstance(token.created_at, datetime)
    assert isinstance(token.updated_at, datetime)

@pytest.mark.asyncio
@pytest.mark.core
async def test_auth_token_update(db_session):
    """Test updating an auth token."""
    # Create a user
    user = User(
        email="token_update@example.com",
        name="Token Update Test User",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create expiration date with timezone info
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    
    # Create an auth token with initial metadata
    token = AuthToken(
        user_id=user.id,
        token="update_token_123456",
        token_type=TokenType.ACCESS.value,
        status=TokenStatus.ACTIVE.value,
        scope=TokenScope.FULL.value,
        expires_at=expires_at,
        meta_data={"device": "test_device"}
    )
    db_session.add(token)
    await db_session.commit()
    
    # Store the original updated_at timestamp and other values
    original_updated_at = token.updated_at
    original_status = token.status
    
    # Wait a moment to ensure updated_at will be different
    await asyncio.sleep(0.1)
    
    # Update the token
    new_expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    token.status = TokenStatus.REVOKED.value
    token.expires_at = new_expires_at
    
    # Create a new meta_data dictionary instead of modifying the existing one
    token.meta_data = {
        "device": "new_device",
        "reason": "user_logout"
    }
    
    await db_session.commit()
    
    # Fetch the token again to get the updated values
    stmt = select(AuthToken).where(AuthToken.id == token.id)
    result = await db_session.execute(stmt)
    updated_token = result.scalar_one()
    
    # Verify the updates to the fields we explicitly changed
    assert updated_token.status == TokenStatus.REVOKED.value
    assert updated_token.status != original_status
    
    # Verify metadata was updated correctly
    assert updated_token.meta_data["device"] == "new_device"
    assert updated_token.meta_data["reason"] == "user_logout"

@pytest.mark.asyncio
@pytest.mark.core
async def test_auth_token_create_method(db_session):
    """Test the create class method of AuthToken."""
    # Create a user
    user = User(
        email="token_create@example.com",
        name="Token Create Test User",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Use the create method
    token = await AuthToken.create(
        db=db_session,
        user_id=user.id,
        token_type=TokenType.REFRESH,
        token="create_method_token_123456",
        status=TokenStatus.ACTIVE,
        scope=TokenScope.FULL,
        meta_data={"method": "create"}
    )
    
    # Verify the token was created
    assert token.id is not None
    assert token.user_id == user.id
    assert token.token == "create_method_token_123456"
    assert token.token_type == TokenType.REFRESH.value
    assert token.status == TokenStatus.ACTIVE.value
    assert token.scope == TokenScope.FULL.value
    assert token.meta_data["method"] == "create"
    
    # Verify expires_at was set automatically (default is 30 days)
    assert token.expires_at is not None
    # Should be approximately 30 days in the future
    now = datetime.now(timezone.utc)
    future_date = token.expires_at
    if future_date.tzinfo is None:
        future_date = future_date.replace(tzinfo=timezone.utc)
    delta = future_date - now
    assert delta.days >= 29

@pytest.mark.asyncio
@pytest.mark.core
async def test_auth_token_get_by_token(db_session):
    """Test the get_by_token class method of AuthToken."""
    # Create a user
    user = User(
        email="token_get@example.com",
        name="Token Get Test User",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create an auth token
    token_value = "get_by_token_123456"
    token = AuthToken(
        user_id=user.id,
        token=token_value,
        token_type=TokenType.ACCESS.value,
        status=TokenStatus.ACTIVE.value,
        scope=TokenScope.FULL.value,
        expires_at=datetime.utcnow() + timedelta(days=7)
    )
    db_session.add(token)
    await db_session.commit()
    
    # Use the get_by_token method
    retrieved_token = await AuthToken.get_by_token(db_session, token_value)
    
    # Verify the token was retrieved
    assert retrieved_token is not None
    assert retrieved_token.id == token.id
    assert retrieved_token.token == token_value
    
    # Try to get a non-existent token
    non_existent_token = await AuthToken.get_by_token(db_session, "non_existent_token")
    assert non_existent_token is None

@pytest.mark.asyncio
@pytest.mark.core
async def test_auth_token_revoke_all_user_tokens(db_session):
    """Test the revoke_all_user_tokens class method of AuthToken."""
    # Create a user
    user = User(
        email="token_revoke@example.com",
        name="Token Revoke Test User",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create multiple tokens for the user
    tokens = []
    for i in range(3):
        token = AuthToken(
            user_id=user.id,
            token=f"revoke_token_{i}",
            token_type=TokenType.ACCESS.value,
            status=TokenStatus.ACTIVE.value,
            scope=TokenScope.FULL.value,
            expires_at=datetime.utcnow() + timedelta(days=7)
        )
        tokens.append(token)
    
    # Also create an already revoked token
    revoked_token = AuthToken(
        user_id=user.id,
        token="already_revoked",
        token_type=TokenType.ACCESS.value,
        status=TokenStatus.REVOKED.value,
        scope=TokenScope.FULL.value,
        expires_at=datetime.utcnow() + timedelta(days=7)
    )
    tokens.append(revoked_token)
    
    db_session.add_all(tokens)
    await db_session.commit()
    
    # Use the revoke_all_user_tokens method
    await AuthToken.revoke_all_user_tokens(db_session, user.id)
    
    # Verify all tokens are now revoked
    stmt = select(AuthToken).where(AuthToken.user_id == user.id)
    result = await db_session.execute(stmt)
    all_tokens = result.scalars().all()
    
    assert len(all_tokens) == 4
    for token in all_tokens:
        assert token.status == TokenStatus.REVOKED.value

@pytest.mark.asyncio
@pytest.mark.core
async def test_auth_token_is_expired_property(db_session):
    """Test the is_expired property of AuthToken."""
    # Create a user
    user = User(
        email="token_expired@example.com",
        name="Token Expired Test User",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create an expired token
    expired_token = AuthToken(
        user_id=user.id,
        token="expired_token",
        token_type=TokenType.ACCESS.value,
        status=TokenStatus.ACTIVE.value,
        scope=TokenScope.FULL.value,
        expires_at=datetime.utcnow() - timedelta(days=1)  # Expired 1 day ago
    )
    
    # Create a valid token
    valid_token = AuthToken(
        user_id=user.id,
        token="valid_token",
        token_type=TokenType.ACCESS.value,
        status=TokenStatus.ACTIVE.value,
        scope=TokenScope.FULL.value,
        expires_at=datetime.utcnow() + timedelta(days=7)  # Valid for 7 more days
    )
    
    db_session.add_all([expired_token, valid_token])
    await db_session.commit()
    
    # Test the is_expired property
    assert expired_token.is_expired is True
    assert valid_token.is_expired is False

@pytest.mark.asyncio
@pytest.mark.core
async def test_auth_token_is_valid_property(db_session):
    """Test the is_valid property of AuthToken."""
    # Create a user
    user = User(
        email="token_valid@example.com",
        name="Token Valid Test User",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create tokens with different statuses and expiration dates
    valid_token = AuthToken(
        user_id=user.id,
        token="valid_active_token",
        token_type=TokenType.ACCESS.value,
        status=TokenStatus.ACTIVE.value,
        scope=TokenScope.FULL.value,
        expires_at=datetime.utcnow() + timedelta(days=7)  # Valid for 7 more days
    )
    
    expired_token = AuthToken(
        user_id=user.id,
        token="expired_active_token",
        token_type=TokenType.ACCESS.value,
        status=TokenStatus.ACTIVE.value,
        scope=TokenScope.FULL.value,
        expires_at=datetime.utcnow() - timedelta(days=1)  # Expired 1 day ago
    )
    
    revoked_token = AuthToken(
        user_id=user.id,
        token="revoked_token",
        token_type=TokenType.ACCESS.value,
        status=TokenStatus.REVOKED.value,
        scope=TokenScope.FULL.value,
        expires_at=datetime.utcnow() + timedelta(days=7)  # Not expired but revoked
    )
    
    db_session.add_all([valid_token, expired_token, revoked_token])
    await db_session.commit()
    
    # Test the is_valid property
    assert valid_token.is_valid is True
    assert expired_token.is_valid is False  # Not valid because expired
    assert revoked_token.is_valid is False  # Not valid because revoked

@pytest.mark.asyncio
@pytest.mark.core
async def test_auth_token_different_scopes(db_session):
    """Test creating tokens with different scopes."""
    # Create a user
    user = User(
        email="token_scopes@example.com",
        name="Token Scopes Test User",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create tokens with different scopes
    full_scope_token = AuthToken(
        user_id=user.id,
        token="full_scope_token",
        token_type=TokenType.ACCESS.value,
        status=TokenStatus.ACTIVE.value,
        scope=TokenScope.FULL.value,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7)
    )
    
    read_scope_token = AuthToken(
        user_id=user.id,
        token="read_scope_token",
        token_type=TokenType.ACCESS.value,
        status=TokenStatus.ACTIVE.value,
        scope=TokenScope.READ.value,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7)
    )
    
    write_scope_token = AuthToken(
        user_id=user.id,
        token="write_scope_token",
        token_type=TokenType.ACCESS.value,
        status=TokenStatus.ACTIVE.value,
        scope=TokenScope.WRITE.value,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7)
    )
    
    db_session.add_all([full_scope_token, read_scope_token, write_scope_token])
    await db_session.commit()
    
    # Verify the scopes
    assert full_scope_token.scope == TokenScope.FULL.value
    assert read_scope_token.scope == TokenScope.READ.value
    assert write_scope_token.scope == TokenScope.WRITE.value 