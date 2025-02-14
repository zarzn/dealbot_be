"""Base exceptions for the application."""

from typing import Dict, Any, Optional, List
from datetime import datetime

class BaseError(Exception):
    """Base exception class for all application exceptions."""
    
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
        self.timestamp = datetime.utcnow()
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary format."""
        return {
            'error': self.__class__.__name__,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'details': self._get_details()
        }
        
    def _get_details(self) -> Dict[str, Any]:
        """Get additional error details. Override in subclasses."""
        return {}

class ValidationError(BaseError):
    """Raised when data validation fails."""
    
    def __init__(
        self,
        message: str,
        errors: Optional[Dict[str, Any]] = None,
        field_prefix: Optional[str] = None
    ):
        super().__init__(message)
        self.errors = errors or {}
        self.field_prefix = field_prefix
        
    def _get_details(self) -> Dict[str, Any]:
        details = {'validation_errors': self.errors}
        if self.field_prefix:
            details['field_prefix'] = self.field_prefix
        return details

class NotFoundError(BaseError):
    """Raised when a requested resource is not found."""
    
    def __init__(self, message: str, resource_type: str, resource_id: Any):
        super().__init__(message)
        self.resource_type = resource_type
        self.resource_id = resource_id
        
    def _get_details(self) -> Dict[str, Any]:
        return {
            'resource_type': self.resource_type,
            'resource_id': self.resource_id
        }

# Alias for backward compatibility
NotFoundException = NotFoundError

class AuthenticationError(BaseError):
    """Raised when authentication fails."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.details = details or {}
        
    def _get_details(self) -> Dict[str, Any]:
        return self.details

class AuthorizationError(BaseError):
    """Raised when authorization fails."""
    
    def __init__(self, message: str, required_permissions: Optional[List[str]] = None):
        super().__init__(message)
        self.required_permissions = required_permissions or []
        
    def _get_details(self) -> Dict[str, Any]:
        return {'required_permissions': self.required_permissions}

class DatabaseError(BaseError):
    """Raised when database operations fail."""
    
    def __init__(self, message: str, operation: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.operation = operation
        self.details = details or {}
        
    def _get_details(self) -> Dict[str, Any]:
        return {
            'operation': self.operation,
            **self.details
        }

class ServiceError(BaseError):
    """Raised when a service operation fails."""
    
    def __init__(
        self,
        message: str,
        service: str,
        operation: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.service = service
        self.operation = operation
        self.details = details or {}
        
    def _get_details(self) -> Dict[str, Any]:
        return {
            'service': self.service,
            'operation': self.operation,
            **self.details
        }

class ExternalServiceError(ServiceError):
    """Raised when an external service operation fails."""
    
    def __init__(
        self,
        service: str,
        operation: str,
        status_code: Optional[int] = None,
        response: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if status_code:
            error_details['status_code'] = status_code
        if response:
            error_details['response'] = response
            
        super().__init__(
            message=f"External service {service} failed during {operation}",
            service=service,
            operation=operation,
            details=error_details
        )

class ConfigurationError(BaseError):
    """Raised when there is a configuration error."""
    
    def __init__(self, message: str, config_key: str, expected_type: Optional[str] = None):
        super().__init__(message)
        self.config_key = config_key
        self.expected_type = expected_type
        
    def _get_details(self) -> Dict[str, Any]:
        return {
            'config_key': self.config_key,
            'expected_type': self.expected_type
        }

class CacheError(BaseError):
    """Raised when a cache operation fails."""
    
    def __init__(self, message: str, cache_key: str, operation: str):
        super().__init__(message)
        self.cache_key = cache_key
        self.operation = operation
        
    def _get_details(self) -> Dict[str, Any]:
        return {
            'cache_key': self.cache_key,
            'operation': self.operation
        }

class IntegrationError(BaseError):
    """Raised when an integration operation fails."""
    
    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.operation = operation
        self.details = details or {}
        
    def _get_details(self) -> Dict[str, Any]:
        return {
            'operation': self.operation,
            **self.details
        }

class NetworkError(BaseError):
    """Raised when a network operation fails."""
    
    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.operation = operation
        self.details = details or {}
        
    def _get_details(self) -> Dict[str, Any]:
        return {
            'operation': self.operation,
            **self.details
        }

class RateLimitError(BaseError):
    """Raised when rate limit is exceeded."""
    
    def __init__(self, message: str, limit: int, reset_at: datetime):
        super().__init__(message)
        self.limit = limit
        self.reset_at = reset_at
        
    def _get_details(self) -> Dict[str, Any]:
        return {
            'limit': self.limit,
            'reset_at': self.reset_at.isoformat()
        }

class RateLimitExceededError(RateLimitError):
    """Alias for RateLimitError for backward compatibility."""
    pass

class RepositoryError(BaseError):
    """Raised when a repository operation fails."""
    
    def __init__(
        self,
        message: str,
        operation: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.operation = operation
        self.details = details or {}
        
    def _get_details(self) -> Dict[str, Any]:
        return {
            'operation': self.operation,
            **self.details
        } 