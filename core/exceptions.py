"""Application exceptions module.

This module defines all custom exceptions for the AI Agentic Deals System,
including authentication, validation, database, and business logic errors.
"""

from typing import List, Dict, Any, Optional, Union
from fastapi import HTTPException
from pydantic import ValidationError as PydanticValidationError
import traceback
import json

class BaseAppException(Exception):
    """Base application exception with enhanced error handling."""
    
    def __init__(
        self,
        message: str,
        status_code: int = 500,
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
        errors: Union[List[Dict[str, Any]], PydanticValidationError],
        message: str = "Validation error",
        field_prefix: str = ""
    ):
        if isinstance(errors, PydanticValidationError):
            formatted_errors = self._format_pydantic_errors(errors, field_prefix)
        else:
            formatted_errors = errors
            
        super().__init__(
            message=message,
            status_code=400,
            error_code="validation_error",
            details={"errors": formatted_errors}
        )

    def _format_pydantic_errors(
        self,
        error: PydanticValidationError,
        field_prefix: str = ""
    ) -> List[Dict[str, Any]]:
        """Format Pydantic validation errors."""
        formatted = []
        for err in error.errors():
            field = ".".join(str(loc) for loc in err["loc"])
            if field_prefix:
                field = f"{field_prefix}.{field}"
            formatted.append({
                "field": field,
                "message": err["msg"],
                "type": err["type"]
            })
        return formatted

class AuthenticationError(BaseAppException):
    """Base authentication error."""
    
    def __init__(
        self,
        message: str = "Authentication failed",
        error_code: str = "authentication_error",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=401,
            error_code=error_code,
            details=details
        )

class TokenExpiredError(AuthenticationError):
    """Token expiration error."""
    
    def __init__(
        self,
        message: str = "Authentication token has expired",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="token_expired",
            details=details
        )

class TokenInvalidError(AuthenticationError):
    """Invalid token error."""
    
    def __init__(
        self,
        message: str = "Invalid authentication token",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="token_invalid",
            details=details
        )

class TokenRevokedError(AuthenticationError):
    """Revoked token error."""
    
    def __init__(
        self,
        message: str = "Authentication token has been revoked",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
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
            status_code=403,
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
            status_code=404,
            error_code="not_found",
            details={
                "resource_type": resource_type,
                "identifier": str(identifier)
            }
        )

class DatabaseError(BaseAppException):
    """Database error with operation details."""
    
    def __init__(
        self,
        operation: str,
        message: str = "Database error occurred",
        original_error: Optional[Exception] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        details["operation"] = operation
        
        super().__init__(
            message=message,
            status_code=500,
            error_code="database_error",
            details=details,
            original_error=original_error
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
            status_code=500,
            error_code="redis_error",
            details=details,
            original_error=original_error
        )

class ExternalServiceError(BaseAppException):
    """External service error with detailed response information."""
    
    def __init__(
        self,
        service: str,
        operation: str,
        message: str = "External service error",
        response: Optional[Any] = None,
        original_error: Optional[Exception] = None
    ):
        details = {
            "service": service,
            "operation": operation
        }
        
        if response:
            try:
                if isinstance(response, (str, bytes)):
                    response_data = json.loads(response)
                else:
                    response_data = response
                details["response"] = response_data
            except Exception:
                details["response"] = str(response)
        
        super().__init__(
            message=message,
            status_code=502,
            error_code="external_service_error",
            details=details,
            original_error=original_error
        )

class RateLimitError(BaseAppException):
    """Rate limit error with limit details."""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=429,
            error_code="rate_limit_error",
            details=details
        )

class TokenError(BaseAppException):
    """Base token-related error."""
    
    def __init__(
        self,
        message: str = "Token error occurred",
        error_code: str = "token_error",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=400,
            error_code=error_code,
            details=details
        )

class InsufficientTokensError(TokenError):
    """Insufficient tokens error with balance details."""
    
    def __init__(
        self,
        required: float,
        available: float,
        message: str = "Insufficient tokens"
    ):
        super().__init__(
            message=message,
            error_code="insufficient_tokens",
            details={
                "required": required,
                "available": available,
                "missing": required - available
            }
        )

class SolanaError(BaseAppException):
    """Solana blockchain error."""
    
    def __init__(
        self,
        operation: str,
        message: str = "Solana operation failed",
        error_code: str = "solana_error",
        details: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None
    ):
        details = details or {}
        details["operation"] = operation
        
        super().__init__(
            message=message,
            status_code=502,
            error_code=error_code,
            details=details,
            original_error=original_error
        )

class SolanaTransactionError(SolanaError):
    """Solana transaction error with signature details."""
    
    def __init__(
        self,
        signature: str,
        message: str = "Transaction failed",
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        details["signature"] = signature
        
        super().__init__(
            operation="transaction",
            message=message,
            error_code="solana_transaction_error",
            details=details
        )

class SolanaConnectionError(SolanaError):
    """Solana connection error."""
    
    def __init__(
        self,
        endpoint: str,
        message: str = "Failed to connect to Solana network",
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        details["endpoint"] = endpoint
        
        super().__init__(
            operation="connection",
            message=message,
            error_code="solana_connection_error",
            details=details
        )

class DealError(BaseAppException):
    """Deal-related error with deal details."""
    
    def __init__(
        self,
        deal_id: Optional[str] = None,
        message: str = "Deal error occurred",
        error_code: str = "deal_error",
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if deal_id:
            details["deal_id"] = deal_id
            
        super().__init__(
            message=message,
            status_code=400,
            error_code=error_code,
            details=details
        )

class GoalError(BaseAppException):
    """Goal-related error with goal details."""
    
    def __init__(
        self,
        goal_id: Optional[str] = None,
        message: str = "Goal error occurred",
        error_code: str = "goal_error",
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        if goal_id:
            details["goal_id"] = goal_id
            
        super().__init__(
            message=message,
            status_code=400,
            error_code=error_code,
            details=details
        )

class NotificationError(BaseAppException):
    """Notification error with delivery details."""
    
    def __init__(
        self,
        notification_type: str,
        recipient: str,
        message: str = "Notification error occurred",
        details: Optional[Dict[str, Any]] = None
    ):
        details = details or {}
        details.update({
            "notification_type": notification_type,
            "recipient": recipient
        })
            
        super().__init__(
            message=message,
            status_code=400,
            error_code="notification_error",
            details=details
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
