"""API-related exceptions module."""

from typing import Dict, Any, Optional, List
from .base_exceptions import BaseError, ValidationError

class APIError(BaseError):
    """Base class for API-related errors."""
    
    def __init__(
        self,
        message: str = "API operation failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="api_error",
            details=details
        )

class APIRequestError(APIError):
    """Raised when an API request fails."""
    
    def __init__(
        self,
        endpoint: str,
        method: str,
        status_code: Optional[int] = None,
        error_details: Optional[Dict[str, Any]] = None,
        message: str = "API request failed"
    ):
        super().__init__(
            message=message,
            details={
                "endpoint": endpoint,
                "method": method,
                "status_code": status_code,
                "error_details": error_details or {}
            }
        )

class APIRateLimitError(APIError):
    """Raised when API rate limit is exceeded."""
    
    def __init__(
        self,
        endpoint: str,
        current_rate: float,
        limit: float,
        reset_time: Optional[str] = None,
        message: str = "API rate limit exceeded"
    ):
        super().__init__(
            message=message,
            details={
                "endpoint": endpoint,
                "current_rate": current_rate,
                "limit": limit,
                "reset_time": reset_time
            }
        )

class APIAuthenticationError(APIError):
    """Raised when API authentication fails."""
    
    def __init__(
        self,
        endpoint: str,
        auth_type: str,
        error_details: Optional[Dict[str, Any]] = None,
        message: str = "API authentication failed"
    ):
        super().__init__(
            message=message,
            details={
                "endpoint": endpoint,
                "auth_type": auth_type,
                "error_details": error_details or {}
            }
        )

class APITimeoutError(APIError):
    """Raised when API request times out."""
    
    def __init__(
        self,
        endpoint: str,
        timeout: float,
        message: str = "API request timed out"
    ):
        super().__init__(
            message=message,
            details={
                "endpoint": endpoint,
                "timeout": timeout
            }
        )

class APIResponseValidationError(APIError):
    """Raised when API response validation fails."""
    
    def __init__(
        self,
        endpoint: str,
        validation_errors: List[Dict[str, Any]],
        message: str = "API response validation failed"
    ):
        super().__init__(
            message=message,
            details={
                "endpoint": endpoint,
                "validation_errors": validation_errors
            }
        )

class APIServiceUnavailableError(APIError):
    """Raised when API service is unavailable."""
    
    def __init__(
        self,
        service_name: str,
        retry_after: Optional[int] = None,
        message: str = "API service unavailable"
    ):
        super().__init__(
            message=message,
            details={
                "service_name": service_name,
                "retry_after": retry_after
            }
        )

class AIServiceError(APIError):
    """Raised when AI/LLM service operations fail."""
    
    def __init__(
        self,
        message: str = "AI service operation failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            details=details
        )

class RedisCacheError(APIError):
    """Raised when Redis cache operations fail."""
    
    def __init__(
        self,
        message: str = "Redis cache operation failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            details=details
        )

__all__ = [
    'APIError',
    'APIRequestError',
    'APIRateLimitError',
    'APIAuthenticationError',
    'APITimeoutError',
    'APIResponseValidationError',
    'APIServiceUnavailableError',
    'AIServiceError',
    'RedisCacheError'
]
