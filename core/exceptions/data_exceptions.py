"""Data processing related exceptions module."""

from typing import Dict, Any, Optional, List
from .base import BaseError, ValidationError

class DataError(BaseError):
    """Base class for data-related errors."""
    
    def __init__(
        self,
        message: str = "Data operation failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="data_error",
            details=details
        )

class DataProcessingError(DataError):
    """Raised when data processing fails."""
    
    def __init__(
        self,
        operation: str,
        reason: str,
        data_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        error_details.update({
            "operation": operation,
            "reason": reason
        })
        if data_type:
            error_details["data_type"] = data_type
        super().__init__(
            message=f"Data processing failed during {operation}: {reason}",
            details=error_details
        )

class DataValidationError(DataError):
    """Raised when data validation fails."""
    
    def __init__(
        self,
        errors: List[Dict[str, Any]],
        data_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        error_details.update({
            "validation_errors": errors
        })
        if data_type:
            error_details["data_type"] = data_type
        super().__init__(
            message=f"Data validation failed: {len(errors)} error(s) found",
            details=error_details
        )

class DataTransformationError(DataError):
    """Raised when data transformation fails."""
    
    def __init__(
        self,
        source_type: str,
        target_type: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        error_details.update({
            "source_type": source_type,
            "target_type": target_type,
            "reason": reason
        })
        super().__init__(
            message=f"Failed to transform data from {source_type} to {target_type}: {reason}",
            details=error_details
        )

class DataIntegrityError(DataError):
    """Raised when data integrity is compromised."""
    
    def __init__(
        self,
        issue: str,
        affected_data: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        error_details.update({
            "issue": issue
        })
        if affected_data:
            error_details["affected_data"] = affected_data
        super().__init__(
            message=f"Data integrity issue: {issue}",
            details=error_details
        )

class DataSyncError(DataError):
    """Raised when data synchronization fails."""
    
    def __init__(
        self,
        source: str,
        target: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        error_details.update({
            "source": source,
            "target": target,
            "reason": reason
        })
        super().__init__(
            message=f"Data sync failed between {source} and {target}: {reason}",
            details=error_details
        )

class DataQualityError(DataError):
    """Raised when data quality checks fail."""
    def __init__(
        self,
        message: str = "Data quality check failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message=message, details=details)
        self.error_code = "data_quality_error"

__all__ = [
    'DataError',
    'DataProcessingError',
    'DataValidationError',
    'DataTransformationError',
    'DataIntegrityError',
    'DataSyncError',
    'DataQualityError'
] 