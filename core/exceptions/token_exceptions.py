"""Token-related exceptions module."""

from typing import Optional, Dict, Any
from .base import BaseError

class TokenError(BaseError):
    """Base class for token-related exceptions"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="token_error",
            details=details or {}
        )

class TokenNotFoundError(TokenError):
    """Raised when a token transaction or record is not found"""
    def __init__(
        self,
        token_id: str,
        message: str = "Token not found",
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        error_details["token_id"] = token_id
        super().__init__(
            message=message,
            details=error_details
        )

class TokenServiceError(TokenError):
    """Raised when a token service operation fails"""
    def __init__(
        self,
        service: str,
        operation: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None
    ):
        self.service = service
        self.operation = operation
        self.reason = reason
        message = f"Token service error in {service} during {operation}: {reason}"
        service_details = {
            "service": service,
            "operation": operation,
            "reason": reason
        }
        if details:
            service_details.update(details)
        super().__init__(message, service_details)

class TokenBalanceError(TokenError):
    """Raised when there's an error with token balance operations"""
    def __init__(self, operation: str, reason: str, balance: Optional[float] = None):
        self.operation = operation
        self.reason = reason
        self.balance = balance
        message = f"Token balance error during {operation}: {reason}"
        details = {"operation": operation, "reason": reason}
        if balance is not None:
            details["balance"] = balance
        super().__init__(message, details)

class InvalidBalanceChangeError(TokenError):
    """Raised when a balance change operation is invalid"""
    def __init__(
        self,
        message: str,
        balance_before: Optional[float] = None,
        balance_after: Optional[float] = None,
        change_amount: Optional[float] = None
    ):
        details = {}
        if balance_before is not None:
            details["balance_before"] = balance_before
        if balance_after is not None:
            details["balance_after"] = balance_after
        if change_amount is not None:
            details["change_amount"] = change_amount
        super().__init__(message, details)

class InsufficientBalanceError(TokenError):
    """Raised when user has insufficient token balance"""
    def __init__(self, required: float, available: float):
        self.required = required
        self.available = available
        message = f"Insufficient balance: required {required}, available {available}"
        details = {"required": required, "available": available}
        super().__init__(message, details)

class InvalidTransactionError(TokenError):
    """Raised when transaction is invalid"""
    def __init__(self, transaction_id: str, reason: str):
        self.transaction_id = transaction_id
        self.reason = reason
        message = f"Invalid transaction {transaction_id}: {reason}"
        details = {"transaction_id": transaction_id, "reason": reason}
        super().__init__(message, details)

class WalletConnectionError(TokenError):
    """Raised when there's an error connecting to a wallet"""
    def __init__(self, address: str, reason: str):
        self.address = address
        self.reason = reason
        message = f"Error connecting wallet {address}: {reason}"
        details = {"address": address, "reason": reason}
        super().__init__(message, details)

class WalletNotFoundError(TokenError):
    """Raised when wallet is not found"""
    def __init__(self, wallet_id: str):
        self.wallet_id = wallet_id
        message = f"Wallet not found: {wallet_id}"
        details = {"wallet_id": wallet_id}
        super().__init__(message, details)

class TransactionNotFoundError(TokenError):
    """Raised when transaction is not found"""
    def __init__(self, transaction_id: str):
        self.transaction_id = transaction_id
        message = f"Transaction not found: {transaction_id}"
        details = {"transaction_id": transaction_id}
        super().__init__(message, details)

class TokenPriceError(TokenError):
    """Raised when there's an error with token price"""
    def __init__(self, reason: str, source: Optional[str] = None):
        self.reason = reason
        self.source = source
        message = f"Token price error: {reason}"
        details = {"reason": reason}
        if source:
            details["source"] = source
        super().__init__(message, details)

class SmartContractError(TokenError):
    """Raised when there's an error interacting with the smart contract"""
    def __init__(self, operation: str, reason: str, tx_hash: Optional[str] = None):
        self.operation = operation
        self.reason = reason
        self.tx_hash = tx_hash
        message = f"Smart contract error during {operation}: {reason}"
        details = {"operation": operation, "reason": reason}
        if tx_hash:
            details["tx_hash"] = tx_hash
        super().__init__(message, details)

class TokenNetworkError(TokenError):
    """Raised when there's a network error"""
    def __init__(self, operation: str, reason: str):
        self.operation = operation
        self.reason = reason
        message = f"Network error during {operation}: {reason}"
        details = {"operation": operation, "reason": reason}
        super().__init__(message, details)

class InvalidTokenAmountError(TokenError):
    """Raised when token amount is invalid"""
    def __init__(self, amount: float, reason: str):
        self.amount = amount
        self.reason = reason
        message = f"Invalid token amount {amount}: {reason}"
        details = {"amount": amount, "reason": reason}
        super().__init__(message, details)

class TokenOperationError(TokenError):
    """Raised when a token operation fails"""
    def __init__(self, operation: str, reason: str, details: Optional[Dict[str, Any]] = None):
        self.operation = operation
        self.reason = reason
        message = f"Token operation error during {operation}: {reason}"
        operation_details = {"operation": operation, "reason": reason}
        if details:
            operation_details.update(details)
        super().__init__(message, operation_details)

class TokenAuthorizationError(TokenError):
    """Raised when there's an authorization error"""
    def __init__(self, user_id: str, operation: str):
        self.user_id = user_id
        self.operation = operation
        message = f"Unauthorized token operation for user {user_id}: {operation}"
        details = {"user_id": user_id, "operation": operation}
        super().__init__(message, details)

class TokenValidationError(TokenError):
    """Raised when token validation fails"""
    def __init__(self, field: str, reason: str):
        self.field = field
        self.reason = reason
        message = f"Token validation error for {field}: {reason}"
        details = {"field": field, "reason": reason}
        super().__init__(message, details)

class TokenTransactionError(TokenError):
    """Raised when there's an error processing a token transaction"""
    def __init__(self, transaction_id: str, operation: str, reason: str, details: Optional[Dict[str, Any]] = None):
        self.transaction_id = transaction_id
        self.operation = operation
        self.reason = reason
        message = f"Token transaction error {transaction_id} during {operation}: {reason}"
        transaction_details = {
            "transaction_id": transaction_id,
            "operation": operation,
            "reason": reason
        }
        if details:
            transaction_details.update(details)
        super().__init__(message, transaction_details)

class TokenRateLimitError(TokenError):
    """Raised when token operations exceed rate limits"""
    def __init__(self, operation: str, limit: int, window: str):
        self.operation = operation
        self.limit = limit
        self.window = window
        message = f"Rate limit exceeded for {operation}: limit {limit} per {window}"
        details = {
            "operation": operation,
            "limit": limit,
            "window": window
        }
        super().__init__(message, details)

class TokenPricingError(TokenError):
    """Raised when there's an error with token pricing operations"""
    def __init__(
        self,
        operation: str,
        reason: str,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = {
            "operation": operation,
            "reason": reason
        }
        if details:
            error_details.update(details)
        super().__init__(
            message=f"Token pricing error during {operation}: {reason}",
            details=error_details
        )

class InvalidPricingError(TokenError):
    """Raised when token pricing data is invalid"""
    def __init__(
        self,
        message: str,
        service_type: Optional[str] = None,
        token_cost: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = {}
        if service_type:
            error_details["service_type"] = service_type
        if token_cost is not None:
            error_details["token_cost"] = token_cost
        if details:
            error_details.update(details)
        super().__init__(message, error_details)

class InsufficientTokensError(InsufficientBalanceError):
    """Alias for InsufficientBalanceError for backward compatibility."""
    pass

__all__ = [
    "TokenError",
    "TokenNotFoundError",
    "TokenServiceError",
    "TokenRateLimitError",
    "TokenPricingError",
    "InvalidPricingError"
]
