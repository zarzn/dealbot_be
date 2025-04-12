"""Payment exceptions."""

from typing import Optional, Dict, Any, List
from fastapi import status

from .base_exceptions import BaseError

class PaymentError(BaseError):
    """Exception raised when payment processing fails."""
    
    def __init__(
        self,
        message: str = "Payment processing error",
        payment_id: Optional[str] = None,
        payment_method: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize PaymentError.
        
        Args:
            message: Error message
            payment_id: ID of the payment that failed
            payment_method: Payment method that was used
            details: Additional error details
        """
        error_details = details or {}
        
        if payment_id:
            error_details["payment_id"] = payment_id
            
        if payment_method:
            error_details["payment_method"] = payment_method
            
        super().__init__(
            message=message,
            error_code="payment_error",
            details=error_details
        )

class PaymentValidationError(PaymentError):
    """Exception raised when payment validation fails."""
    
    def __init__(
        self,
        message: str = "Payment validation error",
        field: Optional[str] = None,
        reason: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize PaymentValidationError.
        
        Args:
            message: Error message
            field: Field that failed validation
            reason: Reason for validation failure
            details: Additional error details
        """
        error_details = details or {}
        
        if field:
            error_details["field"] = field
            
        if reason:
            error_details["reason"] = reason
            
        super().__init__(
            message=message,
            details=error_details
        )

class PaymentMethodNotSupportedError(PaymentError):
    """Exception raised when payment method is not supported."""
    
    def __init__(
        self,
        message: str = "Payment method not supported",
        payment_method: Optional[str] = None,
        supported_methods: Optional[List[str]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize PaymentMethodNotSupportedError.
        
        Args:
            message: Error message
            payment_method: Payment method that is not supported
            supported_methods: List of supported payment methods
            details: Additional error details
        """
        error_details = details or {}
        
        if payment_method:
            error_details["payment_method"] = payment_method
            
        if supported_methods:
            error_details["supported_methods"] = supported_methods
            
        super().__init__(
            message=message,
            payment_method=payment_method,
            details=error_details
        )

class PaymentRequiredError(PaymentError):
    """Exception raised when payment is required to proceed."""
    
    def __init__(
        self,
        message: str = "Payment required",
        amount: Optional[float] = None,
        currency: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize PaymentRequiredError.
        
        Args:
            message: Error message
            amount: Amount required for payment
            currency: Currency for payment
            details: Additional error details
        """
        error_details = details or {}
        
        if amount:
            error_details["amount"] = amount
            
        if currency:
            error_details["currency"] = currency
            
        super().__init__(
            message=message,
            details=error_details
        )

class PaymentDeclinedError(PaymentError):
    """Exception raised when payment is declined by payment processor."""
    
    def __init__(
        self,
        message: str = "Payment declined",
        reason: Optional[str] = None,
        payment_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize PaymentDeclinedError.
        
        Args:
            message: Error message
            reason: Reason for decline
            payment_id: ID of the declined payment
            details: Additional error details
        """
        error_details = details or {}
        
        if reason:
            error_details["reason"] = reason
            
        super().__init__(
            message=message,
            payment_id=payment_id,
            details=error_details
        ) 