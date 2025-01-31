from datetime import datetime, timedelta
from typing import Optional, Any, Tuple
import logging
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import status, HTTPException
from redis.asyncio import Redis
from pydantic import BaseModel

from backend.core.models.user import UserInDB
from backend.core.exceptions import AuthenticationError, TokenError
from backend.core.config import settings

__all__ = [
    'Token',
    'TokenData',
    'verify_password',
    'get_password_hash', 
    'create_tokens',
    'refresh_tokens',
    'authenticate_user',
    'get_current_user'
]

from backend.core.config import settings
from backend.core.models.user import UserInDB
from backend.core.services.user import get_user_by_email
from backend.core.exceptions import (
    InvalidCredentialsError,
    TokenValidationError,
    RateLimitExceededError,
    AccountLockedError,
    TokenRefreshError
)

# Initialize Redis connection
redis: Redis = Redis.from_url(
    settings.REDIS_URL,
    decode_responses=True
)

logger = logging.getLogger(__name__)

# Security configurations
RATE_LIMIT = 5  # Max attempts
RATE_LIMIT_WINDOW = 60  # Seconds
LOCKOUT_DURATION = 300  # Seconds
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7
ALGORITHM = "HS256"
TOKEN_TYPE = "Bearer"

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hashed version"""
    return pwd_context.verify(plain_password, hashed_password)

async def get_password_hash(password: str) -> str:
    """Generate password hash"""
    return pwd_context.hash(password)

async def create_tokens(data: dict) -> Tuple[str, str]:
    """Create access and refresh tokens"""
    access_expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    access_data = data.copy()
    access_data.update({"exp": access_expire, "type": "access"})
    
    refresh_data = data.copy()
    refresh_data.update({"exp": refresh_expire, "type": "refresh"})
    
    access_token = jwt.encode(access_data, settings.SECRET_KEY, algorithm=ALGORITHM)
    refresh_token = jwt.encode(refresh_data, settings.SECRET_KEY, algorithm=ALGORITHM)
    
    return access_token, refresh_token

async def refresh_tokens(refresh_token: str) -> Tuple[str, str]:
    """Refresh access and refresh tokens"""
    try:
        payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise TokenRefreshError("Invalid token type")
            
        email = payload.get("sub")
        if email is None:
            raise TokenRefreshError("Invalid token payload")
            
        return create_tokens({"sub": email})
    except JWTError as e:
        raise TokenRefreshError(f"Token validation failed: {str(e)}")

async def authenticate_user(
    email: str, 
    password: str, 
    redis: Redis
) -> Optional[UserInDB]:
    """Authenticate user with rate limiting and account lockout"""
    lock_key = f"lock:{email}"
    attempt_key = f"attempts:{email}"
    
    # Check if account is locked
    if await redis.get(lock_key):
        raise AccountLockedError("Account temporarily locked")
        
    user = get_user_by_email(email)
    if not user:
        return None
        
    if not verify_password(password, user.password):
        # Increment failed attempts
        attempts = await redis.incr(attempt_key)
        if attempts == 1:
            await redis.expire(attempt_key, RATE_LIMIT_WINDOW)
            
        # Lock account if rate limit exceeded
        if attempts >= RATE_LIMIT:
            await redis.set(lock_key, "locked", ex=LOCKOUT_DURATION)
            raise RateLimitExceededError("Too many failed attempts")
            
        return None
        
    # Reset attempts on successful login
    await redis.delete(attempt_key)
    return user

async def get_current_user(token: str) -> UserInDB:
    """Get current user from access token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise TokenValidationError("Invalid token type")
            
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
            
        # Check if token is revoked
        is_revoked = await redis.get(f"revoked:{token}")
        if is_revoked:
            raise TokenValidationError("Token has been revoked")
            
        user = await get_user_by_email(email)
        if user is None:
            raise credentials_exception
            
        # Log token usage
        await redis.incr(f"token_usage:{email}")
        await redis.expire(f"token_usage:{email}", 3600)  # Track hourly usage
            
        return user
    except JWTError as e:
        logger.error(f"Token validation failed: {str(e)}", extra={
            "email": email,
            "token": token[:10] + "..."  # Log partial token for security
        })
        raise credentials_exception
