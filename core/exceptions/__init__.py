"""Core exceptions initialization."""

class BaseError(Exception):
    """Base error class for all custom exceptions."""
    pass

class ValidationError(BaseError):
    """Raised when validation fails."""
    pass

class NotFoundException(BaseError):
    """Raised when a resource is not found."""
    pass

class UserNotFoundError(NotFoundException):
    """Raised when a user is not found."""
    pass

class TokenError(BaseError):
    """Base class for token-related errors."""
    pass

class TokenValidationError(TokenError):
    """Raised when token validation fails."""
    pass

class TokenExpiredError(TokenError):
    """Raised when a token has expired."""
    pass

class TokenInvalidError(TokenError):
    """Raised when a token is invalid."""
    pass

class TokenRefreshError(TokenError):
    """Raised when token refresh fails."""
    pass

class RateLimitError(BaseError):
    """Raised when rate limit is exceeded."""
    pass

class AuthenticationError(BaseError):
    """Raised when authentication fails."""
    pass

class PermissionError(BaseError):
    """Raised when user lacks required permissions."""
    pass

class DatabaseError(BaseError):
    """Raised when database operations fail."""
    pass

class CacheOperationError(BaseError):
    """Raised when cache operations fail."""
    pass

class ExternalServiceError(BaseError):
    """Raised when external service calls fail."""
    pass

class ConfigurationError(BaseError):
    """Raised when configuration is invalid."""
    pass

__all__ = [
    'BaseError',
    'ValidationError',
    'NotFoundException',
    'UserNotFoundError',
    'TokenError',
    'TokenValidationError',
    'TokenExpiredError',
    'TokenInvalidError',
    'TokenRefreshError',
    'RateLimitError',
    'AuthenticationError',
    'PermissionError',
    'DatabaseError',
    'CacheOperationError',
    'ExternalServiceError',
    'ConfigurationError'
] 