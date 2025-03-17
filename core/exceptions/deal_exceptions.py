"""Deal-related exceptions."""

from typing import Optional, Dict, Any
from .base_exceptions import BaseError, ValidationError, NotFoundException

__all__ = [
    'DealError',
    'DealNotFoundError',
    'InvalidDealDataError',
    'DealExpirationError',
    'DealPriceError',
    'DealValidationError',
    'DealProcessingError',
    'DealScoreError',
    'DealAnalysisError',
    'DealMatchError',
    'DealDuplicateError'
]

class DealError(BaseError):
    """Base exception for deal-related errors."""
    
    def __init__(
        self,
        message: str,
        deal_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.deal_id = deal_id
        self.details = details or {}
        
    def _get_details(self) -> Dict[str, Any]:
        return {
            'deal_id': self.deal_id,
            **self.details
        }

class DealNotFoundError(DealError):
    """Raised when a deal is not found."""
    pass

class InvalidDealDataError(DealError):
    """Raised when deal data is invalid."""
    
    def __init__(
        self,
        message: str,
        deal_id: Optional[str] = None,
        validation_errors: Optional[Dict[str, str]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, deal_id, details)
        self.validation_errors = validation_errors or {}
        
    def _get_details(self) -> Dict[str, Any]:
        details = super()._get_details()
        details['validation_errors'] = self.validation_errors
        return details

class DealExpirationError(DealError):
    """Raised when a deal has expired."""
    pass

class DealPriceError(DealError):
    """Raised when there's an error with deal pricing."""
    
    def __init__(
        self,
        message: str,
        deal_id: Optional[str] = None,
        price: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, deal_id, details)
        self.price = price
        
    def _get_details(self) -> Dict[str, Any]:
        details = super()._get_details()
        details['price'] = self.price
        return details

class DealValidationError(DealError):
    """Raised when deal validation fails."""
    
    def __init__(
        self,
        message: str,
        deal_id: Optional[str] = None,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, deal_id, details)
        self.field = field
        
    def _get_details(self) -> Dict[str, Any]:
        details = super()._get_details()
        details['field'] = self.field
        return details

class DealProcessingError(DealError):
    """Raised when deal processing fails."""
    
    def __init__(
        self,
        message: str,
        deal_id: Optional[str] = None,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, deal_id, details)
        self.operation = operation
        
    def _get_details(self) -> Dict[str, Any]:
        details = super()._get_details()
        details['operation'] = self.operation
        return details

class DealScoreError(DealError):
    """Raised when deal scoring fails."""
    
    def __init__(
        self,
        message: str,
        deal_id: Optional[str] = None,
        score: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, deal_id, details)
        self.score = score
        
    def _get_details(self) -> Dict[str, Any]:
        details = super()._get_details()
        details['score'] = self.score
        return details

class DealAnalysisError(DealError):
    """Raised when deal analysis fails."""
    
    def __init__(
        self,
        message: str,
        deal_id: Optional[str] = None,
        analysis_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, deal_id, details)
        self.analysis_type = analysis_type
        
    def _get_details(self) -> Dict[str, Any]:
        details = super()._get_details()
        details['analysis_type'] = self.analysis_type
        return details

class DealMatchError(DealError):
    """Raised when deal matching fails."""
    
    def __init__(
        self,
        message: str,
        deal_id: Optional[str] = None,
        goal_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, deal_id, details)
        self.goal_id = goal_id
        
    def _get_details(self) -> Dict[str, Any]:
        details = super()._get_details()
        details['goal_id'] = self.goal_id
        return details

class DealDuplicateError(DealError):
    """Raised when attempting to create a duplicate deal."""
    
    def __init__(
        self,
        message: str,
        deal_id: Optional[str] = None,
        duplicate_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, deal_id, details)
        self.duplicate_id = duplicate_id
        
    def _get_details(self) -> Dict[str, Any]:
        details = super()._get_details()
        details['duplicate_id'] = self.duplicate_id
        return details 