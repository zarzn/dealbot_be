"""Authentication utility functions.

This module provides utility functions for authentication-related tasks.
"""

import logging
import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from fastapi import Request

from core.models.user import User

logger = logging.getLogger(__name__)

def create_test_user() -> User:
    """Create a test user for development and testing.
    
    Returns:
        User: A test user with predefined ID and attributes
    """
    # Use a consistent UUID for test user to ensure it's always the same
    user_id = uuid.UUID('00000000-0000-4000-a000-000000000000')
    
    return User(
        id=user_id,
        email='test@example.com',
        username='testuser',
        full_name='Test User',
        status='active',
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        roles=['user']
    )

def is_test_token(token: Optional[str]) -> bool:
    """Check if the provided token is a test token.
    
    Args:
        token: The token to check
        
    Returns:
        bool: True if the token is a test token
    """
    if not token:
        return False
    
    return token.startswith('test_')

def get_authorization_token(request: Request) -> Optional[str]:
    """Extract the authorization token from the request headers.
    
    Args:
        request: The FastAPI request object
        
    Returns:
        Optional[str]: The token if present, None otherwise
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None
    
    # Handle standard Bearer token format
    parts = auth_header.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    
    return None

def log_auth_info(request: Request, logger: logging.Logger) -> None:
    """Log authentication information from the request.
    
    Args:
        request: The FastAPI request object
        logger: The logger to use
    """
    # Log request info
    logger.info(f"Request: {request.method} {request.url}")
    auth_header = request.headers.get("Authorization")
    logger.info(f"Auth header present: {'Yes' if auth_header else 'No'}")
    
    # If there's an auth header, check if it's a test token
    if auth_header:
        token = get_authorization_token(request)
        if token and is_test_token(token):
            logger.info(f"Using test token for authentication") 