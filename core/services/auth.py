"""Authentication service module.

This module provides authentication and token management functionality.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID
import logging
import json
from decimal import Decimal

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis
from redis.asyncio import Redis
from pydantic import BaseModel

from core.config import settings
from core.models.user import User
from core.exceptions import (
    AuthenticationError,
    InvalidTokenError,
    UserNotFoundError,
    InsufficientBalanceError,
    TokenValidationError
)
from core.utils.redis import get_redis_pool

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

logger = logging.getLogger(__name__)

# Token expiration times (in minutes)
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

class TokenData(BaseModel):
    """Token data model."""
    sub: str
    exp: Optional[datetime] = None
    refresh: bool = False

class Token(BaseModel):
    """Token response model."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = ACCESS_TOKEN_EXPIRE_MINUTES * 60
    refresh_token: Optional[str] = None

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Generate password hash."""
    return pwd_context.hash(password)

async def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create a new JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    try:
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        return encoded_jwt
    except JWTError as e:
        logger.error(f"Error creating access token: {e}")
        raise TokenValidationError("Could not create access token")

async def create_refresh_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create a new JWT refresh token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "refresh": True})
    try:
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        return encoded_jwt
    except JWTError as e:
        logger.error(f"Error creating refresh token: {e}")
        raise TokenValidationError("Could not create refresh token")

async def verify_token(token: str, redis: Redis) -> Dict[str, Any]:
    """Verify a JWT token and check if it's blacklisted."""
    try:
        # Check if token is blacklisted
        is_blacklisted = await redis.get(f"blacklist:{token}")
        if is_blacklisted:
            raise InvalidTokenError("Token has been revoked")

        # Verify token
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError as e:
        logger.error(f"Error verifying token: {e}")
        raise InvalidTokenError("Invalid token")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(lambda: next(get_db())),
    redis: Redis = Depends(get_redis_pool)
) -> User:
    """Get current authenticated user."""
    try:
        token_data = await verify_token(token, redis)
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
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        exp = payload.get("exp")
        if exp:
            # Calculate TTL
            exp_datetime = datetime.fromtimestamp(exp)
            ttl = (exp_datetime - datetime.utcnow()).total_seconds()
            if ttl > 0:
                await redis.setex(
                    f"blacklist:{token}",
                    int(ttl),
                    "true"
                )
    except Exception as e:
        logger.error(f"Error blacklisting token: {e}")
        raise TokenValidationError("Could not blacklist token")

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
            raise InsufficientBalanceError(
                f"Insufficient balance. Required: {required_balance}, Current: {current_balance}"
            )
        return True
    except InsufficientBalanceError:
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
    """Create both access and refresh tokens."""
    access_token = await create_access_token(data)
    refresh_token = await create_refresh_token(data)
    return access_token, refresh_token

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
    'create_tokens'
]
