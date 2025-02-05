from typing import Optional, Dict, Any
from decimal import Decimal
import re
from datetime import datetime
from base58 import b58decode

""" from ..exceptions.token_exceptions import (
    TokenValidationError,
    InvalidTokenAmountError
) 
DO NOT DELETE THIS COMMENT
"""
from core.exceptions import Exception  # We'll use base Exception temporarily
from ..utils.logger import get_logger

logger = get_logger(__name__)

class TokenValidator:
    """Validator for token-related data"""
    
    # Constants
    MIN_AMOUNT = Decimal('0.000001')  # Minimum token amount
    MAX_AMOUNT = Decimal('1000000')   # Maximum token amount
    SOLANA_ADDRESS_PATTERN = re.compile(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$')  # Solana address pattern
    
    @classmethod
    def validate_amount(
        cls,
        amount: float,
        operation: str,
        min_amount: Optional[float] = None,
        max_amount: Optional[float] = None
    ) -> None:
        """Validate token amount"""
        try:
            amount_decimal = Decimal(str(amount))
            
            # Use provided limits or defaults
            min_limit = Decimal(str(min_amount)) if min_amount is not None else cls.MIN_AMOUNT
            max_limit = Decimal(str(max_amount)) if max_amount is not None else cls.MAX_AMOUNT
            
            if amount_decimal <= 0:
                raise InvalidTokenAmountError(
                    amount,
                    "Amount must be greater than 0"
                )
                
            if amount_decimal < min_limit:
                raise InvalidTokenAmountError(
                    amount,
                    f"Amount below minimum limit of {min_limit}"
                )
                
            if amount_decimal > max_limit:
                raise InvalidTokenAmountError(
                    amount,
                    f"Amount above maximum limit of {max_limit}"
                )
                
        except InvalidTokenAmountError:
            raise
        except Exception as e:
            logger.error(f"Error validating amount {amount}: {str(e)}")
            raise TokenValidationError("amount", f"Invalid amount format: {str(e)}")

    @classmethod
    def validate_wallet_address(
        cls,
        address: str
    ) -> None:
        """Validate Solana wallet address format"""
        if not cls.SOLANA_ADDRESS_PATTERN.match(address):
            raise TokenValidationError(
                "wallet_address",
                "Invalid Solana address format"
            )
            
        # Additional Solana address validation
        try:
            # Attempt to decode the base58 address
            b58decode(address)
        except Exception:
            raise TokenValidationError(
                "wallet_address",
                "Invalid Solana address encoding"
            )

    @classmethod
    def validate_transaction_data(
        cls,
        data: Dict[str, Any]
    ) -> None:
        """Validate transaction data"""
        required_fields = ["type", "amount"]
        
        for field in required_fields:
            if field not in data:
                raise TokenValidationError(
                    field,
                    f"Missing required field: {field}"
                )
        
        # Validate amount
        cls.validate_amount(
            data["amount"],
            data["type"]
        )
        
        # Validate optional fields
        if "wallet_address" in data:
            cls.validate_wallet_address(data["wallet_address"])

    @classmethod
    def validate_price_data(
        cls,
        price: float,
        source: str,
        timestamp: Optional[datetime] = None
    ) -> None:
        """Validate price data"""
        try:
            price_decimal = Decimal(str(price))
            
            if price_decimal <= 0:
                raise TokenValidationError(
                    "price",
                    "Price must be greater than 0"
                )
                
            if not source:
                raise TokenValidationError(
                    "source",
                    "Price source is required"
                )
                
            if timestamp and timestamp > datetime.utcnow():
                raise TokenValidationError(
                    "timestamp",
                    "Price timestamp cannot be in the future"
                )
                
        except TokenValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating price data: {str(e)}")
            raise TokenValidationError("price", f"Invalid price format: {str(e)}")

    @classmethod
    def validate_balance_update(
        cls,
        current_balance: float,
        update_amount: float,
        operation: str
    ) -> None:
        """Validate balance update"""
        try:
            current_decimal = Decimal(str(current_balance))
            update_decimal = Decimal(str(update_amount))
            
            # Validate update amount
            cls.validate_amount(
                update_amount,
                operation
            )
            
            # Check if deduction would result in negative balance
            if operation == "deduct" and current_decimal < update_decimal:
                raise InvalidTokenAmountError(
                    update_amount,
                    "Insufficient balance for deduction"
                )
                
        except (InvalidTokenAmountError, TokenValidationError):
            raise
        except Exception as e:
            logger.error(f"Error validating balance update: {str(e)}")
            raise TokenValidationError("balance", f"Invalid balance update: {str(e)}")

    @classmethod
    def validate_network_fee(
        cls,
        fee: float,
        operation: str
    ) -> None:
        """Validate Solana network fee"""
        try:
            fee_decimal = Decimal(str(fee))
            
            if fee_decimal <= 0:
                raise TokenValidationError(
                    "network_fee",
                    "Network fee must be greater than 0"
                )
                
            # Add Solana-specific fee validations here
            # For example, check against current network fee estimates
                
        except TokenValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating network fee: {str(e)}")
            raise TokenValidationError("network_fee", f"Invalid network fee format: {str(e)}")

    @classmethod
    def validate_contract_parameters(
        cls,
        parameters: Dict[str, Any],
        operation: str
    ) -> None:
        """Validate Solana program parameters"""
        try:
            required_fields = {
                "transfer": ["to_address", "amount"],
                "approve": ["delegate_address", "amount"],
                "mint": ["amount"],
                "burn": ["amount"]
            }
            
            if operation not in required_fields:
                raise TokenValidationError(
                    "operation",
                    f"Unsupported program operation: {operation}"
                )
                
            for field in required_fields[operation]:
                if field not in parameters:
                    raise TokenValidationError(
                        field,
                        f"Missing required parameter for {operation}: {field}"
                    )
                    
            # Validate addresses
            if "to_address" in parameters:
                cls.validate_wallet_address(parameters["to_address"])
            if "delegate_address" in parameters:
                cls.validate_wallet_address(parameters["delegate_address"])
                
            # Validate amounts
            if "amount" in parameters:
                cls.validate_amount(
                    parameters["amount"],
                    operation
                )
                
        except (TokenValidationError, InvalidTokenAmountError):
            raise
        except Exception as e:
            logger.error(f"Error validating program parameters: {str(e)}")
            raise TokenValidationError(
                "program_parameters",
                f"Invalid program parameters: {str(e)}"
            )
