from typing import Optional, Dict, Any

class TokenError(Exception):
    """Base class for token-related exceptions"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

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