"""Analytics-related exceptions."""

from typing import Dict, Any, Optional
from .base_exceptions import BaseError

class AnalyticsError(BaseError):
    """Base class for analytics-related errors."""
    
    def __init__(
        self,
        message: str = "Analytics operation failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.details = details or {}
        
    def _get_details(self) -> Dict[str, Any]:
        return self.details

class AnalyticsProcessingError(AnalyticsError):
    """Raised when analytics processing fails."""
    
    def __init__(
        self,
        message: str = "Analytics processing failed",
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if operation:
            error_details["operation"] = operation
            
        super().__init__(
            message=message,
            details=error_details
        )

class AnalyticsDataError(AnalyticsError):
    """Raised when there are issues with analytics data."""
    
    def __init__(
        self,
        message: str = "Invalid or missing analytics data",
        data_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if data_type:
            error_details["data_type"] = data_type
            
        super().__init__(
            message=message,
            details=error_details
        )

class AnalyticsValidationError(AnalyticsError):
    """Raised when analytics validation fails."""
    
    def __init__(
        self,
        message: str = "Analytics validation failed",
        validation_errors: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if validation_errors:
            error_details["validation_errors"] = validation_errors
            
        super().__init__(
            message=message,
            details=error_details
        ) 