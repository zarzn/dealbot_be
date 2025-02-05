"""Base exceptions module."""

from typing import Dict, Any, Optional, List

class BaseError(Exception):
    """Base error class for all custom exceptions."""
    
    def __init__(
        self,
        message: str,
        error_code: str = "error",
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

class ValidationError(BaseError):
    """Raised when validation fails."""
    
    def __init__(
        self,
        message: str = "Validation error",
        errors: Optional[List[Dict[str, Any]]] = None,
        field_prefix: str = ""
    ):
        details = {"errors": errors or [], "field_prefix": field_prefix}
        super().__init__(message=message, error_code="validation_error", details=details)

class IntegrationError(BaseError):
    """Base exception for integration errors."""
    def __init__(
        self,
        message: str = "Integration operation failed",
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if operation:
            error_details["operation"] = operation
        super().__init__(
            message=message,
            error_code="integration_error",
            details=error_details
        )

class SmartContractError(BaseError):
    """Raised when a smart contract operation fails."""
    
    def __init__(
        self,
        operation: str,
        message: str = "Smart contract operation failed",
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        error_details["operation"] = operation
        super().__init__(
            message=message,
            error_code="smart_contract_error",
            details=error_details
        )

class NotFoundException(BaseError):
    """Raised when a resource is not found."""
    
    def __init__(
        self,
        message: str = "Resource not found",
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None
    ):
        details = {}
        if resource_type:
            details["resource_type"] = resource_type
        if resource_id:
            details["resource_id"] = resource_id
            
        super().__init__(
            message=message,
            error_code="not_found",
            details=details
        )

# Alias for NotFoundException to maintain backward compatibility
NotFoundError = NotFoundException

class DatabaseError(BaseError):
    """Raised when database operations fail."""
    
    def __init__(
        self,
        message: str = "Database operation failed",
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if operation:
            error_details["operation"] = operation
            
        super().__init__(
            message=message,
            error_code="database_error",
            details=error_details
        )

class RepositoryError(BaseError):
    """Raised when repository operations fail."""
    
    def __init__(
        self,
        message: str = "Repository operation failed",
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if operation:
            error_details["operation"] = operation
            
        super().__init__(
            message=message,
            error_code="repository_error",
            details=error_details
        )

class NetworkError(BaseError):
    """Raised when network operations fail."""
    
    def __init__(
        self,
        message: str = "Network operation failed",
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if operation:
            error_details["operation"] = operation
            
        super().__init__(
            message=message,
            error_code="network_error",
            details=error_details
        )

class ServiceError(BaseError):
    """Raised when a service operation fails."""
    
    def __init__(
        self,
        message: str = "Service operation failed",
        service: Optional[str] = None,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if service:
            error_details["service"] = service
        if operation:
            error_details["operation"] = operation
            
        super().__init__(
            message=message,
            error_code="service_error",
            details=error_details
        )

class ExternalServiceError(BaseError):
    """Base class for external service-related errors."""
    
    def __init__(
        self,
        message: str = "External service operation failed",
        service_name: Optional[str] = None,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if service_name:
            error_details["service_name"] = service_name
        if operation:
            error_details["operation"] = operation
            
        super().__init__(
            message=message,
            error_code="external_service_error",
            details=error_details
        )

class RateLimitError(BaseError):
    """Base class for rate limit related errors."""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        operation: Optional[str] = None,
        limit: Optional[int] = None,
        reset_after: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if operation:
            error_details["operation"] = operation
        if limit:
            error_details["limit"] = limit
        if reset_after:
            error_details["reset_after"] = reset_after
            
        super().__init__(
            message=message,
            error_code="rate_limit_exceeded",
            details=error_details
        )

# Alias for backward compatibility
RateLimitExceededError = RateLimitError

__all__ = [
    'BaseError',
    'ValidationError',
    'NotFoundException',
    'NotFoundError',
    'DatabaseError',
    'RepositoryError',
    'NetworkError',
    'ServiceError',
    'ExternalServiceError',
    'RateLimitError',
    'RateLimitExceededError',
    'SmartContractError',
    'IntegrationError'
]
