"""Market-related exceptions."""

from typing import Dict, Any, Optional
from .base_exceptions import BaseError, ValidationError

class MarketError(BaseError):
    """Base class for market-related errors."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.details = details or {}
        
    def _get_details(self) -> Dict[str, Any]:
        return self.details

class MarketValidationError(ValidationError):
    """Raised when market validation fails."""
    
    def __init__(
        self,
        message: str = "Market validation failed",
        errors: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message=message, errors=errors)

class MarketNotFoundError(MarketError):
    """Raised when a market is not found."""
    
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
    """Raised when connection to a market fails."""
    
    def __init__(
        self,
        market: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        error_details.update({
            "market": market,
            "reason": reason
        })
        super().__init__(
            message=f"Failed to connect to market {market}: {reason}",
            details=error_details
        )

class MarketRateLimitError(MarketError):
    """Raised when market rate limit is exceeded."""
    
    def __init__(
        self,
        market: str,
        limit: int,
        reset_time: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        error_details.update({
            "market": market,
            "limit": limit,
            "reset_time": reset_time
        })
        super().__init__(
            message=f"Rate limit exceeded for market {market}",
            details=error_details
        )

class MarketConfigurationError(MarketError):
    """Raised when market configuration is invalid."""
    
    def __init__(
        self,
        market: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        error_details.update({
            "market": market,
            "reason": reason
        })
        super().__init__(
            message=f"Invalid configuration for market {market}: {reason}",
            details=error_details
        )

class MarketOperationError(MarketError):
    """Raised when a market operation fails."""
    
    def __init__(
        self,
        market: str,
        operation: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        error_details.update({
            "market": market,
            "operation": operation,
            "reason": reason
        })
        super().__init__(
            message=f"Operation {operation} failed for market {market}: {reason}",
            details=error_details
        )

class MarketAuthenticationError(MarketError):
    """Raised when market authentication fails."""
    
    def __init__(
        self,
        market: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        error_details.update({
            "market": market,
            "reason": reason
        })
        super().__init__(
            message=f"Authentication failed for market {market}: {reason}",
            details=error_details
        )

class MarketProductError(MarketError):
    """Raised when there's an error with market products."""
    
    def __init__(
        self,
        market: str,
        product_id: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        error_details.update({
            "market": market,
            "product_id": product_id,
            "reason": reason
        })
        super().__init__(
            message=f"Product error in market {market} for {product_id}: {reason}",
            details=error_details
        )

class ProductNotFoundError(MarketProductError):
    """Raised when a product is not found in the market."""
    
    def __init__(
        self,
        market: str,
        product_id: str,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        error_details.update({
            "market": market,
            "product_id": product_id,
            "reason": "Product not found"
        })
        super().__init__(
            market=market,
            product_id=product_id,
            reason=f"Product {product_id} not found",
            details=error_details
        )

class PricePredictionError(MarketError):
    """Raised when price prediction fails."""
    
    def __init__(
        self,
        market: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        error_details.update({
            "market": market,
            "reason": reason
        })
        super().__init__(
            message=f"Price prediction failed for market {market}: {reason}",
            details=error_details
        )

class InvalidMarketDataError(MarketError):
    """Raised when market data is invalid."""
    
    def __init__(
        self,
        market: str,
        reason: str,
        data: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=f"Invalid market data from {market}: {reason}",
            details={
                "market": market,
                "reason": reason,
                "data": data,
                **(details or {})
            }
        )

class MarketIntegrationError(MarketError):
    """Raised when there's an error with market integration."""
    
    def __init__(
        self,
        market: str,
        operation: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        error_details.update({
            "market": market,
            "operation": operation,
            "reason": reason
        })
        super().__init__(
            message=f"Market integration error for {market} during {operation}: {reason}",
            details=error_details
        )

class RateLimitError(MarketError):
    """Raised when rate limit is exceeded."""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message=message, details=details)

__all__ = [
    'MarketError',
    'MarketValidationError',
    'MarketNotFoundError',
    'MarketConnectionError',
    'MarketRateLimitError',
    'MarketConfigurationError',
    'MarketOperationError',
    'MarketAuthenticationError',
    'MarketProductError',
    'ProductNotFoundError',
    'PricePredictionError',
    'InvalidMarketDataError',
    'MarketIntegrationError',
    'RateLimitError',
] 