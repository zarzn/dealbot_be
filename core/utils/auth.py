"""Authentication utilities."""

from typing import Optional
import jwt
from datetime import datetime, timedelta
import logging
from core.config import settings

logger = logging.getLogger(__name__)

def verify_token(token: str) -> Optional[str]:
    """Verify a JWT token and return the user ID if valid."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            logger.error("Token payload missing user ID")
            return None
        return user_id
    except jwt.ExpiredSignatureError:
        logger.error("Token has expired")
        return None
    except jwt.JWTError as e:
        logger.error(f"Error decoding token: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error verifying token: {str(e)}")
        return None

def create_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create a new JWT token for a user."""
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    expire = datetime.utcnow() + expires_delta
    to_encode = {
        "sub": str(user_id),
        "exp": expire,
        "type": "access"
    }
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt 