"""Cache-related exceptions module."""

from typing import Dict, Any, Optional
from .base import BaseError

class CacheError(BaseError):
    """Base class for cache-related errors."""
    
    def __init__(
        self,
        message: str = "Cache operation failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="cache_error",
            details=details
        )

class CacheOperationError(CacheError):
    """Raised when a cache operation fails."""
    
    def __init__(
        self,
        operation: str,
        reason: str,
        key: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        error_details.update({
            "operation": operation,
            "reason": reason
        })
        if key:
            error_details["key"] = key
        super().__init__(
            message=f"Cache {operation} failed: {reason}",
            details=error_details
        )

class CacheConnectionError(CacheError):
    """Raised when connection to cache fails."""
    
    def __init__(
        self,
        host: str,
        port: int,
        reason: str,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        error_details.update({
            "host": host,
            "port": port,
            "reason": reason
        })
        super().__init__(
            message=f"Cache connection failed: {reason}",
            details=error_details
        )

class CacheKeyError(CacheError):
    """Raised when there's an issue with cache keys."""
    
    def __init__(
        self,
        key: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        error_details.update({
            "key": key,
            "reason": reason
        })
        super().__init__(
            message=f"Cache key error: {reason}",
            details=error_details
        )

class CacheTimeoutError(CacheError):
    """Raised when a cache operation times out."""
    
    def __init__(
        self,
        operation: str,
        timeout: float,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        error_details.update({
            "operation": operation,
            "timeout": timeout
        })
        super().__init__(
            message=f"Cache operation timed out after {timeout}s",
            details=error_details
        )

class CacheCapacityError(CacheError):
    """Raised when cache capacity is exceeded."""
    
    def __init__(
        self,
        current_size: int,
        max_size: int,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        error_details.update({
            "current_size": current_size,
            "max_size": max_size
        })
        super().__init__(
            message=f"Cache capacity exceeded: {current_size}/{max_size}",
            details=error_details
        )

__all__ = [
    'CacheError',
    'CacheOperationError',
    'CacheConnectionError',
    'CacheKeyError',
    'CacheTimeoutError',
    'CacheCapacityError'
] 