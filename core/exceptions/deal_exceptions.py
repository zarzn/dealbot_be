"""Deal-specific exceptions module."""

from typing import Optional, Dict, Any, List
from .base import BaseError, ValidationError, NotFoundException

__all__ = [
    'DealError',
    'DealNotFoundError',
    'InvalidDealDataError',
    'DealExpirationError',
    'DealPriceError',
    'DealValidationError',
    'DealProcessingError',
    'DealScoreError',
    'DealAnalysisError'
]

class DealError(BaseError):
    """Base class for deal-related errors."""
    
    def __init__(
        self,
        message: str,
        deal_id: Optional[str] = None,
        error_code: str = "deal_error",
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if deal_id:
            error_details["deal_id"] = deal_id
            
        super().__init__(
            message=message,
            error_code=error_code,
            details=error_details
        )

class DealNotFoundError(NotFoundException):
    """Deal not found error."""
    
    def __init__(
        self,
        message: str = "Deal not found",
        deal_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if deal_id:
            error_details["deal_id"] = deal_id
            
        super().__init__(
            message=message,
            resource_type="deal",
            resource_id=deal_id
        )

class InvalidDealDataError(ValidationError):
    """Invalid deal data error."""
    
    def __init__(
        self,
        message: str = "Invalid deal data",
        errors: Optional[List[Dict[str, Any]]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        super().__init__(
            message=message,
            errors=errors,
            field_prefix="deal"
        )

class DealExpirationError(DealError):
    """Error raised when a deal has expired."""
    
    def __init__(
        self,
        deal_id: str,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message or f"Deal {deal_id} has expired",
            deal_id=deal_id,
            error_code="deal_expired",
            details=details
        )

class DealPriceError(DealError):
    """Error raised when there are issues with deal pricing."""
    
    def __init__(
        self,
        deal_id: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            deal_id=deal_id,
            error_code="deal_price_error",
            details=details
        )

class DealValidationError(DealError):
    """Error raised during deal validation."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="deal_validation_error",
            details=details
        )

class DealProcessingError(DealError):
    """Error raised when deal processing fails."""
    
    def __init__(
        self,
        message: str,
        deal_id: Optional[str] = None,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if operation:
            error_details["operation"] = operation
            
        super().__init__(
            message=message,
            deal_id=deal_id,
            error_code="deal_processing_error",
            details=error_details
        )

class DealScoreError(DealError):
    """Error raised when deal scoring fails."""
    
    def __init__(
        self,
        message: str,
        deal_id: Optional[str] = None,
        score_type: Optional[str] = None,
        score_details: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if score_type:
            error_details["score_type"] = score_type
        if score_details:
            error_details["score_details"] = score_details
            
        super().__init__(
            message=message,
            deal_id=deal_id,
            error_code="deal_score_error",
            details=error_details
        )

class DealAnalysisError(DealError):
    """Raised when deal analysis fails."""
    def __init__(
        self,
        message: str = "Deal analysis failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message=message, details=details)
        self.error_code = "deal_analysis_error" 