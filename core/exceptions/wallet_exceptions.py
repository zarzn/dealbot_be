from typing import Optional, Dict, Any

from .base import BaseError

class WalletError(BaseError):
    """Base class for wallet-related exceptions"""
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            error_code="wallet_error",
            details=details
        )

class WalletNotFoundError(WalletError):
    """Raised when wallet is not found"""
    def __init__(self, wallet_address: str):
        super().__init__(
            message=f"Wallet not found: {wallet_address}",
            details={"wallet_address": wallet_address}
        )

class WalletConnectionError(WalletError):
    """Raised when there's an error connecting to a wallet"""
    def __init__(self, wallet_address: str, reason: str):
        super().__init__(
            message=f"Error connecting wallet {wallet_address}: {reason}",
            details={
                "wallet_address": wallet_address,
                "reason": reason
            }
        )

class WalletValidationError(WalletError):
    """Raised when wallet validation fails"""
    def __init__(self, reason: str, wallet_address: Optional[str] = None):
        details = {"reason": reason}
        if wallet_address:
            details["wallet_address"] = wallet_address
        super().__init__(
            message=f"Wallet validation error: {reason}",
            details=details
        )

class WalletAlreadyConnectedError(WalletError):
    """Raised when wallet is already connected to another user"""
    def __init__(self, wallet_address: str):
        super().__init__(
            message=f"Wallet already connected to another user: {wallet_address}",
            details={"wallet_address": wallet_address}
        )

class WalletOperationError(WalletError):
    """Raised when a wallet operation fails"""
    def __init__(self, operation: str, reason: str, wallet_address: Optional[str] = None):
        details = {
            "operation": operation,
            "reason": reason
        }
        if wallet_address:
            details["wallet_address"] = wallet_address
        super().__init__(
            message=f"Wallet operation error during {operation}: {reason}",
            details=details
        ) 