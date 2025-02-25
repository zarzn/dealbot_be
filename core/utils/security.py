"""Security utilities module.

This module provides core security functions for password hashing and verification.
"""

import bcrypt
from typing import Optional
import secrets
import string
import hashlib
import base64

def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt.
    
    Args:
        password: Plain text password
        
    Returns:
        str: Hashed password
    """
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash.
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to verify against
        
    Returns:
        bool: True if password matches hash
    """
    return bcrypt.checkpw(
        plain_password.encode(),
        hashed_password.encode()
    )

def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token.
    
    Args:
        length: Length of token to generate
        
    Returns:
        str: Secure random token
    """
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def hash_string(value: str) -> str:
    """Create a SHA-256 hash of a string.
    
    Args:
        value: String to hash
        
    Returns:
        str: Base64 encoded hash
    """
    hasher = hashlib.sha256()
    hasher.update(value.encode())
    return base64.b64encode(hasher.digest()).decode()

__all__ = [
    'get_password_hash',
    'verify_password',
    'generate_secure_token',
    'hash_string'
] 