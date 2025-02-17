"""Authentication service module.

This module provides authentication and token management functionality.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID
import logging
import json
from decimal import Decimal
from redis.asyncio import Redis

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from core.config import settings
from core.models.user import User
from core.models.auth_token import (
    TokenType,
    TokenStatus,
    TokenScope,
    AuthToken
)
from core.exceptions import (
    AuthenticationError,
    InvalidCredentialsError,
    TokenError,
    SessionExpiredError,
    PermissionDeniedError,
    TwoFactorRequiredError,
    InvalidTwoFactorCodeError,
    UserNotFoundError,
    TokenBalanceError,
    TokenValidationError,
    APIError,
    APIAuthenticationError,
    APIServiceUnavailableError,
    DatabaseError,
    TokenRefreshError
)
from core.database import get_db
from core.utils.redis import get_redis_client

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

logger = logging.getLogger(__name__)

class Token(BaseModel):
    """Token response model."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: Optional[str] = None

    class Config:
        """Pydantic model configuration."""
        from_attributes = True

class TokenData(BaseModel):
    """Token data model for decoded JWT payload."""
    sub: str  # User ID
    exp: Optional[int] = None  # Expiration timestamp
    type: Optional[str] = None  # Token type (access, refresh, etc.)
    scope: Optional[str] = None  # Token scope
    refresh: Optional[bool] = None  # Whether this is a refresh token
    jti: Optional[str] = None  # JWT ID for blacklisting

    class Config:
        """Pydantic model configuration."""
        from_attributes = True

# Token expiration times (in minutes)
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Generate password hash."""
    return pwd_context.hash(password)

async def authenticate_user(
    email: str,
    password: str,
    db: AsyncSession
) -> Optional[User]:
    """Authenticate a user with email and password.
    
    Args:
        email: User's email
        password: User's password
        db: Database session
        
    Returns:
        Optional[User]: Authenticated user or None if authentication fails
        
    Raises:
        InvalidCredentialsError: If credentials are invalid
    """
    try:
        # Get user by email with relationships
        stmt = select(User).where(
            User.email == email,
            User.status == 'active'  # Only allow active users to login
        ).execution_options(populate_existing=True)
        
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            logger.warning(f"User not found or inactive: {email}")
            raise InvalidCredentialsError(
                message="Invalid email or password",
                error_code="user_not_found"
            )
            
        # Verify password using the verify_password function
        if not verify_password(password, user.password):
            logger.warning(f"Invalid password for user: {email}")
            raise InvalidCredentialsError(
                message="Invalid email or password",
                error_code="invalid_password"
            )
            
        # Update last login time
        user.last_login_at = datetime.utcnow()
        await db.commit()
            
        return user
    except InvalidCredentialsError:
        raise
    except Exception as e:
        logger.error(f"Error authenticating user: {e}")
        raise InvalidCredentialsError(
            message="Authentication failed",
            error_code="auth_error",
            details={"error": str(e)}
        )

async def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create a new JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    try:
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY.get_secret_value(),
            algorithm=settings.JWT_ALGORITHM
        )
        return encoded_jwt
    except JWTError as e:
        logger.error(f"Error creating access token: {e}")
        raise TokenRefreshError("Could not create access token")

async def create_refresh_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create a new JWT refresh token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "refresh": True})
    try:
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY.get_secret_value(),
            algorithm=settings.JWT_ALGORITHM
        )
        return encoded_jwt
    except JWTError as e:
        logger.error(f"Error creating refresh token: {e}")
        raise TokenRefreshError("Could not create refresh token")

async def verify_token(token: str, redis: Redis) -> Dict[str, Any]:
    """Verify a JWT token."""
    try:
        # Check if token is blacklisted
        is_blacklisted = await redis.get(f"blacklist:{token}")
        if is_blacklisted:
            raise TokenRefreshError("Token has been revoked")

        payload = jwt.decode(
            token,
            settings.SECRET_KEY.get_secret_value(),
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError as e:
        logger.error(f"Error verifying token: {e}")
        raise TokenRefreshError("Invalid token")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user."""
    try:
        redis_client = await get_redis_client()
        token_data = await verify_token(token, redis_client)
        user = await db.execute(
            select(User).where(User.id == UUID(token_data["sub"]))
        )
        user = user.scalar_one_or_none()
        if user is None:
            raise UserNotFoundError(token_data["sub"])
        return user
    except (JWTError, UserNotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user

async def blacklist_token(token: str, redis: Redis) -> None:
    """Add a token to the blacklist."""
    try:
        # Get token expiration from payload
        payload = jwt.decode(
            token,
            settings.SECRET_KEY.get_secret_value(),
            algorithms=[settings.JWT_ALGORITHM]
        )
        exp = payload.get("exp", 0)
        ttl = max(exp - datetime.utcnow().timestamp(), 0)
        
        # Add to blacklist with TTL
        await redis.setex(
            f"blacklist:{token}",
            int(ttl),
            "1"
        )
    except Exception as e:
        logger.error(f"Error blacklisting token: {e}")
        raise TokenRefreshError("Could not blacklist token")

async def verify_token_balance(
    user: User,
    required_balance: Decimal,
    redis: Redis
) -> bool:
    """Verify if a user has sufficient token balance."""
    try:
        # Get cached balance
        cached_balance = await redis.get(f"balance:{user.id}")
        if cached_balance is not None:
            current_balance = Decimal(cached_balance.decode())
        else:
            current_balance = user.token_balance
            # Cache the balance
            await redis.setex(
                f"balance:{user.id}",
                300,  # 5 minutes TTL
                str(current_balance)
            )

        if current_balance < required_balance:
            raise TokenBalanceError(
                f"Insufficient balance. Required: {required_balance}, Current: {current_balance}"
            )
        return True
    except TokenBalanceError:
        raise
    except Exception as e:
        logger.error(f"Error verifying token balance: {e}")
        raise TokenValidationError("Could not verify token balance")

async def update_token_balance(
    user: User,
    amount: Decimal,
    db: AsyncSession,
    redis: Redis
) -> Decimal:
    """Update a user's token balance."""
    try:
        # Update database
        user.token_balance += amount
        await db.commit()
        
        # Update cache
        await redis.setex(
            f"balance:{user.id}",
            300,  # 5 minutes TTL
            str(user.token_balance)
        )
        
        return user.token_balance
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating token balance: {e}")
        raise TokenValidationError("Could not update token balance")

async def get_token_balance(
    user: User,
    redis: Redis
) -> Decimal:
    """Get a user's current token balance."""
    try:
        # Try to get from cache first
        cached_balance = await redis.get(f"balance:{user.id}")
        if cached_balance is not None:
            return Decimal(cached_balance.decode())
        
        # If not in cache, return from user object and cache it
        await redis.setex(
            f"balance:{user.id}",
            300,  # 5 minutes TTL
            str(user.token_balance)
        )
        return user.token_balance
    except Exception as e:
        logger.error(f"Error getting token balance: {e}")
        raise TokenValidationError("Could not get token balance")

async def create_tokens(data: Dict[str, Any]) -> Tuple[str, str]:
    """Create both access and refresh tokens for a user.
    
    Args:
        data: Dictionary containing token data (must include 'sub' key)
        
    Returns:
        Tuple[str, str]: Access token and refresh token
        
    Raises:
        TokenRefreshError: If token creation fails
    """
    try:
        access_token = await create_access_token(data)
        refresh_token = await create_refresh_token(data)
        return access_token, refresh_token
    except Exception as e:
        logger.error(f"Error creating tokens: {e}")
        raise TokenRefreshError("Could not create tokens")

async def refresh_tokens(
    refresh_token: str,
    db: AsyncSession,
    redis: Redis
) -> Token:
    """Refresh access and refresh tokens.
    
    Args:
        refresh_token: Current refresh token
        db: Database session
        redis: Redis client
        
    Returns:
        Token: New access and refresh tokens
        
    Raises:
        TokenValidationError: If refresh token is invalid
        UserNotFoundError: If user not found
    """
    try:
        # Verify refresh token
        payload = await verify_token(refresh_token, redis)
        if not payload.get("refresh"):
            raise ValueError("Invalid refresh token")
            
        # Get user
        user = await db.execute(
            select(User).where(User.id == UUID(payload["sub"]))
        )
        user = user.scalar_one_or_none()
        if not user:
            raise ValueError("User not found")
            
        # Create new tokens
        access_token = await create_access_token(
            data={"sub": str(user.id)}
        )
        new_refresh_token = await create_refresh_token(
            data={"sub": str(user.id)}
        )
        
        # Blacklist old refresh token
        await blacklist_token(refresh_token, redis)
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            refresh_token=new_refresh_token
        )
    except Exception as e:
        logger.error(f"Error refreshing tokens: {e}")
        raise ValueError("Could not refresh tokens")

async def create_password_reset_token(user_id: UUID) -> str:
    """Create a password reset token."""
    expires = timedelta(hours=settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS)
    return await create_access_token(
        data={"sub": str(user_id), "type": "password_reset"},
        expires_delta=expires
    )

async def verify_password_reset_token(token: str) -> UUID:
    """Verify a password reset token."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        if payload.get("type") != "password_reset":
            raise TokenRefreshError("Invalid token type")
        return UUID(payload["sub"])
    except (JWTError, ValueError) as e:
        logger.error(f"Error verifying password reset token: {e}")
        raise TokenRefreshError("Invalid password reset token")

async def create_email_verification_token(user_id: UUID) -> str:
    """Create an email verification token."""
    expires = timedelta(days=7)  # Email verification tokens last 7 days
    return await create_access_token(
        data={"sub": str(user_id), "type": "email_verification"},
        expires_delta=expires
    )

async def verify_email_token(token: str) -> UUID:
    """Verify an email verification token."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        if payload.get("type") != "email_verification":
            raise TokenRefreshError("Invalid token type")
        return UUID(payload["sub"])
    except (JWTError, ValueError) as e:
        logger.error(f"Error verifying email token: {e}")
        raise TokenRefreshError("Invalid email verification token")

async def create_magic_link_token(data: Dict[str, Any]) -> str:
    """Create a magic link token for passwordless authentication.
    
    Args:
        data: Data to encode in the token
        
    Returns:
        str: Encoded JWT token
    """
    try:
        # Set expiration to 15 minutes for magic links
        expire = datetime.utcnow() + timedelta(minutes=15)
        to_encode = data.copy()
        to_encode.update({
            "exp": expire,
            "type": "magic_link"
        })
        
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY.get_secret_value(),
            algorithm=settings.JWT_ALGORITHM
        )
        return encoded_jwt
    except JWTError as e:
        logger.error(f"Error creating magic link token: {e}")
        raise TokenRefreshError("Could not create magic link token")

async def verify_magic_link_token(token: str) -> Dict[str, Any]:
    """Verify a magic link token.
    
    Args:
        token: JWT token to verify
        
    Returns:
        Dict[str, Any]: Token payload if valid
        
    Raises:
        TokenRefreshError: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        # Verify token type
        if payload.get("type") != "magic_link":
            raise TokenRefreshError("Invalid token type")
            
        return payload
    except JWTError as e:
        logger.error(f"Error verifying magic link token: {e}")
        raise TokenRefreshError("Invalid or expired magic link token")

class AuthService:
    """Authentication service class."""
    
    def __init__(self, db: AsyncSession):
        """Initialize auth service with database session."""
        self.db = db
        
    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        try:
            result = await self.db.execute(
                select(User).where(User.id == UUID(user_id))
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting user by ID: {e}")
            raise UserNotFoundError(f"User not found: {user_id}")

    async def is_token_blacklisted(self, token: str) -> bool:
        """Check if a token is blacklisted.
        
        Args:
            token: JWT token to check
            
        Returns:
            bool: True if token is blacklisted, False otherwise
        """
        try:
            redis_client = await get_redis_client()
            is_blacklisted = await redis_client.get(f"blacklist:{token}")
            return bool(is_blacklisted)
        except Exception as e:
            logger.error(f"Error checking token blacklist: {e}")
            return False  # Default to not blacklisted on error
            
    async def authenticate(self, email: str, password: str) -> Optional[User]:
        """Authenticate a user with email and password."""
        return await authenticate_user(email, password, self.db)
        
    async def create_tokens(self, user: User) -> Token:
        """Create access and refresh tokens for a user."""
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        refresh_token_expires = timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
        
        access_token = await create_access_token(
            data={"sub": str(user.id)},
            expires_delta=access_token_expires
        )
        
        refresh_token = await create_refresh_token(
            data={"sub": str(user.id)},
            expires_delta=refresh_token_expires
        )
        
        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
        
    async def refresh_token(self, refresh_token: str) -> Token:
        """Refresh access token using refresh token."""
        try:
            redis_client = await get_redis_client()
            payload = await verify_token(refresh_token, redis_client)
            
            if not payload.get("refresh"):
                raise TokenRefreshError("Invalid refresh token")
                
            user = await self.get_user_by_id(payload["sub"])
            if not user:
                raise TokenRefreshError("User not found")
                
            return await self.create_tokens(user)
            
        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            raise TokenRefreshError(str(e))
            
    async def logout(self, token: str) -> None:
        """Logout user by blacklisting their token."""
        try:
            redis_client = await get_redis_client()
            await blacklist_token(token, redis_client)
        except Exception as e:
            logger.error(f"Error logging out user: {e}")
            raise ValueError(f"Could not logout user: {e}")

__all__ = [
    'get_current_user',
    'get_current_active_user',
    'create_access_token',
    'create_refresh_token',
    'verify_token',
    'blacklist_token',
    'verify_token_balance',
    'update_token_balance',
    'get_token_balance',
    'create_tokens',
    'refresh_tokens',
    'create_password_reset_token',
    'verify_password_reset_token',
    'create_email_verification_token',
    'verify_email_token',
    'TokenRefreshError',
    'AuthService'
]
