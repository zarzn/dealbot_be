"""Application exceptions module.

This module defines all custom exceptions for the AI Agentic Deals System,
including authentication, validation, database, and business logic errors.
"""

from typing import List, Dict, Any, Optional, Union
from fastapi import HTTPException, status
from pydantic import ValidationError as PydanticValidationError
import traceback
import json

class BaseAppException(Exception):
    """Base application exception with enhanced error handling."""
    
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code: str = "internal_error",
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}
        self.original_error = original_error
        
        if original_error:
            self.details["original_error"] = {
                "type": type(original_error).__name__,
                "message": str(original_error)
            }
            
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary with enhanced details."""
        error_dict = {
            "status": "error",
            "error": {
                "code": self.error_code,
                "message": self.message,
                "details": self.details
            },
            "status_code": self.status_code
        }
        
        # Add stack trace in debug mode
        if self.details.get("debug", False):
            error_dict["error"]["stack_trace"] = traceback.format_exc()
            
        return error_dict

    def __str__(self) -> str:
        """String representation of the error."""
        return f"{self.error_code}: {self.message}"

class ValidationError(BaseAppException):
    """Validation error with detailed field errors."""
    
    def __init__(
        self,
        message: str = "Validation error",
        errors: Optional[List[Dict[str, Any]]] = None,
        field_prefix: str = ""
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="validation_error",
            details={"errors": errors or []}
        )

class AuthenticationError(BaseAppException):
    """Authentication error."""
    
    def __init__(
        self,
        message: str = "Authentication failed",
        details: Optional[Dict[str, Any]] = None,
        error_code: str = "authentication_error"
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code=error_code,
            details=details
        )

class NotFoundException(BaseAppException):
    """Resource not found error."""
    
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
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="not_found",
            details=details
        )

class DatabaseError(BaseAppException):
    """Database operation error."""
    
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
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="database_error",
            details=error_details
        )

class MarketError(BaseAppException):
    """Market operation error."""
    
    def __init__(
        self,
        message: str = "Market operation failed",
        market_id: Optional[str] = None,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if market_id:
            error_details["market_id"] = market_id
        if operation:
            error_details["operation"] = operation
            
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="market_error",
            details=error_details
        )

class RateLimitError(BaseAppException):
    """Rate limit exceeded error."""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        limit: Optional[int] = None,
        reset_after: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if limit:
            error_details["limit"] = limit
        if reset_after:
            error_details["reset_after"] = reset_after
            
        super().__init__(
            message=message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error_code="rate_limit_exceeded",
            details=error_details
        )

class InsufficientTokensError(BaseAppException):
    """Insufficient tokens error."""
    
    def __init__(
        self,
        message: str = "Insufficient tokens",
        required: Optional[int] = None,
        available: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if required is not None:
            error_details["required"] = required
        if available is not None:
            error_details["available"] = available
            
        super().__init__(
            message=message,
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            error_code="insufficient_tokens",
            details=error_details
        )

class MarketConnectionError(MarketError):
    """Market connection error."""
    
    def __init__(
        self,
        message: str = "Failed to connect to market",
        market_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            market_id=market_id,
            operation="connect",
            details=details
        )

class MarketAuthenticationError(MarketError):
    """Market authentication error."""
    
    def __init__(
        self,
        message: str = "Market authentication failed",
        market_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            market_id=market_id,
            operation="authenticate",
            details=details
        )

class MarketRateLimitError(MarketError):
    """Market rate limit error."""
    
    def __init__(
        self,
        message: str = "Market rate limit exceeded",
        market_id: Optional[str] = None,
        reset_after: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if reset_after:
            error_details["reset_after"] = reset_after
            
        super().__init__(
            message=message,
            market_id=market_id,
            operation="rate_limit",
            details=error_details
        )

class MarketMaintenanceError(MarketError):
    """Market maintenance error."""
    
    def __init__(
        self,
        message: str = "Market is under maintenance",
        market_id: Optional[str] = None,
        maintenance_window: Optional[Dict[str, str]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if maintenance_window:
            error_details["maintenance_window"] = maintenance_window
            
        super().__init__(
            message=message,
            market_id=market_id,
            operation="maintenance",
            details=error_details
        )

class TokenTransactionError(BaseAppException):
    """Token transaction error."""
    
    def __init__(
        self,
        message: str = "Token transaction failed",
        transaction_id: Optional[str] = None,
        transaction_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if transaction_id:
            error_details["transaction_id"] = transaction_id
        if transaction_type:
            error_details["transaction_type"] = transaction_type
            
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="token_transaction_error",
            details=error_details
        )

class DealError(BaseAppException):
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
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code=error_code,
            details=error_details
        )

class TokenExpiredError(BaseAppException):
    """Token expiration error."""
    
    def __init__(
        self,
        message: str = "Authentication token has expired",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="token_expired",
            details=details
        )

class InvalidTokenError(BaseAppException):
    """Invalid token error."""
    
    def __init__(
        self,
        message: str = "Invalid authentication token",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="token_invalid",
            details=details
        )

class TokenRevokedError(BaseAppException):
    """Revoked token error."""
    
    def __init__(
        self,
        message: str = "Authentication token has been revoked",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="token_revoked",
            details=details
        )

class AuthorizationError(BaseAppException):
    """Authorization error with resource information."""
    
    def __init__(
        self,
        message: str = "Not authorized",
        resource_type: Optional[str] = None,
        required_permissions: Optional[List[str]] = None,
        user_permissions: Optional[List[str]] = None
    ):
        details = {
            "resource_type": resource_type
        }
        if required_permissions:
            details["required_permissions"] = required_permissions
        if user_permissions:
            details["user_permissions"] = user_permissions
            
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="authorization_error",
            details=details
        )

class NotFoundError(BaseAppException):
    """Resource not found error with identifier information."""
    
    def __init__(
        self,
        resource_type: str,
        identifier: Any,
        message: Optional[str] = None
    ):
        message = message or f"{resource_type} not found"
        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="not_found",
            details={
                "resource_type": resource_type,
                "identifier": str(identifier)
            }
        )

class RedisError(BaseAppException):
    """Redis error with operation details."""
    
    def __init__(
        self,
        operation: str,
        message: str = "Redis error occurred",
        original_error: Optional[Exception] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        details["operation"] = operation
        
        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="redis_error",
            details=details,
            original_error=original_error
        )

class RedisConnectionError(RedisError):
    """Redis connection error."""
    
    def __init__(
        self,
        message: str = "Failed to connect to Redis",
        original_error: Optional[Exception] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            operation="connect",
            message=message,
            original_error=original_error,
            details=details
        )

class ExternalServiceError(BaseAppException):
    """External service error with detailed response information."""
    
    def __init__(
        self,
        service: str,
        message: str = "External service error",
        status_code: Optional[int] = None,
        response_data: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        details = {
            "service": service
        }
        if status_code:
            details["status_code"] = status_code
        if response_data:
            details["response_data"] = response_data
            
        super().__init__(
            message=message,
            status_code=status.HTTP_502_BAD_GATEWAY,
            error_code="external_service_error",
            details=details,
            original_error=original_error
        )

class TokenError(BaseAppException):
    """Token-related error."""
    
    def __init__(
        self,
        message: str = "Token error occurred",
        details: Optional[Dict[str, Any]] = None,
        error_code: str = "token_error"
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code=error_code,
            details=details
        )

class InvalidCredentialsError(AuthenticationError):
    """Invalid credentials error."""
    
    def __init__(
        self,
        message: str = "Invalid credentials",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            details=details
        )

class TokenValidationError(BaseAppException):
    """Token validation error."""
    
    def __init__(
        self,
        message: str = "Token validation failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="token_validation_error",
            details=details
        )

class RateLimitExceededError(RateLimitError):
    """Rate limit exceeded error."""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        limit: Optional[int] = None,
        reset_after: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if limit:
            error_details["limit"] = limit
        if reset_after:
            error_details["reset_after"] = reset_after
            
        super().__init__(
            message=message,
            limit=limit,
            reset_after=reset_after,
            details=error_details
        )

class AccountLockedError(AuthenticationError):
    """Account locked error."""
    
    def __init__(
        self,
        message: str = "Account is locked",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            details=details
        )

class TokenRefreshError(BaseAppException):
    """Token refresh error."""
    
    def __init__(
        self,
        message: str = "Token refresh failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="token_refresh_error",
            details=details
        )

class UserError(BaseAppException):
    """User-related error."""
    
    def __init__(
        self,
        message: str = "User error occurred",
        error_code: str = "user_error",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code=error_code,
            details=details
        )

class WalletError(BaseAppException):
    """Wallet-related error."""
    
    def __init__(
        self,
        message: str = "Wallet error occurred",
        error_code: str = "wallet_error",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code=error_code,
            details=details
        )

class ServiceError(BaseAppException):
    """Service-related error."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="service_error",
            details=details
        )

class InsufficientBalanceError(BaseAppException):
    """Insufficient balance error."""
    
    def __init__(
        self,
        message: str = "Insufficient balance",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="insufficient_balance",
            details=details
        )

# Goal-related exceptions
class GoalConstraintError(BaseAppException):
    """Goal constraint validation error."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="goal_constraint_error",
            details=details
        )

class GoalValidationError(BaseAppException):
    """Goal validation error."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="goal_validation_error",
            details=details
        )

class GoalNotFoundError(NotFoundError):
    """Goal not found error."""
    
    def __init__(
        self,
        goal_id: Any,
        message: Optional[str] = None
    ):
        super().__init__(
            resource_type="Goal",
            identifier=goal_id,
            message=message
        )

class GoalStatusError(BaseAppException):
    """Goal status transition error."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="goal_status_error",
            details=details
        )

class InvalidGoalConstraintsError(BaseAppException):
    """Invalid goal constraints error."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="invalid_goal_constraints",
            details=details
        )

class GoalCreationError(BaseAppException):
    """Goal creation error."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="goal_creation_error",
            details=details
        )

class GoalUpdateError(BaseAppException):
    """Goal update error."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="goal_update_error",
            details=details
        )

class DealMatchError(BaseAppException):
    """Deal matching error."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="deal_match_error",
            details=details
        )

class UserNotFoundError(NotFoundError):
    """Error raised when a user is not found."""
    
    def __init__(
        self,
        user_id: Any,
        message: Optional[str] = None
    ):
        super().__init__(
            resource_type="user",
            identifier=user_id,
            message=message or f"User with ID {user_id} not found"
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
            deal_id=deal_id,
            message=message or f"Deal {deal_id} has expired",
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
            deal_id=deal_id,
            message=message,
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

class AIServiceError(ExternalServiceError):
    """Error raised when AI service operations fail."""
    
    def __init__(
        self,
        operation: str,
        message: str = "AI service error occurred",
        response: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(
            service="ai",
            operation=operation,
            message=message,
            response=response,
            original_error=original_error
        )

class MarketNotFoundError(NotFoundError):
    """Error raised when a market is not found."""
    
    def __init__(
        self,
        market_id: Any,
        message: Optional[str] = None
    ):
        super().__init__(
            resource_type="market",
            identifier=market_id,
            message=message or f"Market with ID {market_id} not found"
        )

class DealAnalysisError(BaseAppException):
    """Raised when deal analysis fails."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="deal_analysis_error",
            details=details
        )

class DataQualityError(BaseAppException):
    """Raised when data quality is insufficient."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="data_quality_error",
            details=details
        )

class ModelError(BaseAppException):
    """Raised when ML model operations fail."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="model_error",
            details=details
        )

class ConfigurationError(BaseAppException):
    """Configuration error."""
    
    def __init__(
        self,
        message: str = "Configuration error",
        config_key: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if config_key:
            error_details["config_key"] = config_key
            
        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="configuration_error",
            details=error_details
        )

class CacheError(BaseAppException):
    """Cache operation error."""
    
    def __init__(
        self,
        message: str = "Cache operation failed",
        operation: Optional[str] = None,
        key: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if operation:
            error_details["operation"] = operation
        if key:
            error_details["key"] = key
            
        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="cache_error",
            details=error_details
        )

def http_exception_handler(exc: HTTPException) -> Dict[str, Any]:
    """Convert FastAPI HTTP exception to standard format."""
    return {
        "status": "error",
        "error": {
            "code": f"http_{exc.status_code}",
            "message": exc.detail,
            "details": getattr(exc, "details", {})
        },
        "status_code": exc.status_code
    }

def validation_exception_handler(exc: PydanticValidationError) -> Dict[str, Any]:
    """Handle Pydantic validation exceptions."""
    return ValidationError(exc).to_dict()

def app_exception_handler(exc: BaseAppException) -> Dict[str, Any]:
    """Handle application exceptions."""
    return exc.to_dict()

def generic_exception_handler(exc: Exception) -> Dict[str, Any]:
    """Handle unhandled exceptions."""
    return BaseAppException(
        message="An unexpected error occurred",
        error_code="internal_error",
        original_error=exc
    ).to_dict()
