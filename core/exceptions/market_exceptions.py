"""Market-related exceptions module."""

from typing import Dict, Any, Optional, List
from .base import BaseError, ValidationError

class MarketError(BaseError):
    """Base class for market-related errors."""
    
    def __init__(
        self,
        message: str = "Market operation failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="market_error",
            details=details
        )

class MarketValidationError(ValidationError):
    """Raised when market validation fails."""
    
    def __init__(
        self,
        message: str = "Market validation error",
        errors: Optional[List[Dict[str, Any]]] = None,
        field_prefix: str = "market"
    ):
        super().__init__(
            message=message,
            errors=errors,
            field_prefix=field_prefix
        )

class InvalidMarketDataError(MarketError):
    """Raised when market data is invalid."""
    
    def __init__(
        self,
        message: str = "Invalid market data",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="invalid_market_data",
            details=details
        )

class MarketNotFoundError(MarketError):
    """Raised when a market cannot be found."""
    
    def __init__(
        self,
        market_id: str,
        message: str = "Market not found"
    ):
        super().__init__(
            message=message,
            details={"market_id": market_id}
        )

class MarketConnectionError(MarketError):
    """Raised when there's an error connecting to a market API."""
    
    def __init__(
        self,
        market_type: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = {
            "market_type": market_type,
            "reason": reason
        }
        if details:
            error_details.update(details)
        super().__init__(
            message=f"Error connecting to {market_type} market: {reason}",
            details=error_details
        )

class MarketRateLimitError(MarketError):
    """Raised when market rate limit is exceeded."""
    
    def __init__(
        self,
        market_type: str,
        limit: int,
        window: str
    ):
        super().__init__(
            message=f"Rate limit exceeded for {market_type}: {limit} requests per {window}",
            details={
                "market_type": market_type,
                "limit": limit,
                "window": window
            }
        )

class MarketConfigurationError(MarketError):
    """Raised when market configuration is invalid."""
    
    def __init__(
        self,
        market_type: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = {
            "market_type": market_type,
            "reason": reason
        }
        if details:
            error_details.update(details)
        super().__init__(
            message=f"Invalid configuration for {market_type} market: {reason}",
            details=error_details
        )

class MarketOperationError(MarketError):
    """Raised when a market operation fails."""
    
    def __init__(
        self,
        operation: str,
        reason: str,
        market_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = {
            "operation": operation,
            "reason": reason
        }
        if market_type:
            error_details["market_type"] = market_type
        if details:
            error_details.update(details)
        super().__init__(
            message=f"Market operation error during {operation}: {reason}",
            details=error_details
        )

class MarketAuthenticationError(MarketError):
    """Raised when market authentication fails."""
    
    def __init__(
        self,
        market: str,
        message: str = "Market authentication failed",
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = {"market": market}
        if details:
            error_details.update(details)
        super().__init__(
            message=message,
            error_code="market_authentication_error",
            details=error_details
        )

class InvalidDealDataError(MarketError):
    """Raised when deal data is invalid."""
    
    def __init__(
        self,
        message: str = "Invalid deal data",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="invalid_deal_data",
            details=details
        )

__all__ = [
    'MarketError',
    'MarketValidationError',
    'InvalidMarketDataError',
    'MarketNotFoundError',
    'MarketConnectionError',
    'MarketRateLimitError',
    'MarketConfigurationError',
    'MarketOperationError',
    'MarketAuthenticationError',
    'InvalidDealDataError'
] 