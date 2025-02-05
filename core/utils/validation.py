"""Validation utility functions."""

from typing import Any, Dict, List, Optional, Union
from datetime import datetime
import re
from decimal import Decimal
import uuid
from pydantic import BaseModel, ValidationError

from core.exceptions import ValidationError as AppValidationError
from core.utils.logger import get_logger

logger = get_logger(__name__)

# Re-export for convenience
__all__ = [
    'Validator',
    'DataValidator',
    'GoalValidator',
    'DealValidator',
    'NotificationValidator',
    'TokenValidator'
]

class Validator:
    """Base validator class"""
    @staticmethod
    def validate_uuid(value: str) -> bool:
        """Validate UUID string"""
        try:
            uuid.UUID(str(value))
            return True
        except ValueError:
            return False

    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email address"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    @staticmethod
    def validate_url(url: str) -> bool:
        """Validate URL"""
        pattern = r'^https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)$'
        return bool(re.match(pattern, url))

    @staticmethod
    def validate_phone(phone: str) -> bool:
        """Validate phone number"""
        pattern = r'^\+?1?\d{9,15}$'
        return bool(re.match(pattern, phone))

    @staticmethod
    def validate_price(price: Union[str, float, Decimal]) -> bool:
        """Validate price value"""
        try:
            price_decimal = Decimal(str(price))
            return price_decimal >= 0
        except:
            return False

    @staticmethod
    def validate_date(date_str: str, format: str = "%Y-%m-%d") -> bool:
        """Validate date string"""
        try:
            datetime.strptime(date_str, format)
            return True
        except ValueError:
            return False

class DataValidator:
    """Data validation utility class"""
    def __init__(self, schema: BaseModel):
        self.schema = schema
        self.errors: List[Dict[str, Any]] = []

    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate data against schema"""
        try:
            validated_data = self.schema(**data)
            return validated_data.model_dump()
        except ValidationError as e:
            errors = []
            for error in e.errors():
                errors.append({
                    "field": ".".join(str(x) for x in error["loc"]),
                    "message": error["msg"],
                    "type": error["type"]
                })
            raise AppValidationError(errors)

class GoalValidator:
    """Goal-specific validation"""
    @staticmethod
    def validate_price_range(min_price: Optional[float], max_price: Optional[float]) -> bool:
        """Validate price range"""
        if min_price is not None and max_price is not None:
            return 0 <= min_price <= max_price
        return True

    @staticmethod
    def validate_keywords(keywords: List[str]) -> bool:
        """Validate search keywords"""
        return all(
            isinstance(k, str) and len(k.strip()) > 0
            for k in keywords
        )

    @staticmethod
    def validate_brands(brands: List[str]) -> bool:
        """Validate brand names"""
        return all(
            isinstance(b, str) and len(b.strip()) > 0
            for b in brands
        )

    @staticmethod
    def validate_goal_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate complete goal data"""
        errors = []

        # Validate price range
        if not GoalValidator.validate_price_range(
            data.get("min_price"),
            data.get("max_price")
        ):
            errors.append({
                "field": "price_range",
                "message": "Invalid price range",
                "type": "value_error"
            })

        # Validate keywords
        if "keywords" in data and not GoalValidator.validate_keywords(data["keywords"]):
            errors.append({
                "field": "keywords",
                "message": "Invalid keywords",
                "type": "value_error"
            })

        # Validate brands
        if "brands" in data and not GoalValidator.validate_brands(data["brands"]):
            errors.append({
                "field": "brands",
                "message": "Invalid brands",
                "type": "value_error"
            })

        if errors:
            raise AppValidationError(errors)

        return data

class DealValidator:
    """Deal-specific validation"""
    @staticmethod
    def validate_deal_url(url: str) -> bool:
        """Validate deal URL"""
        return Validator.validate_url(url)

    @staticmethod
    def validate_deal_price(
        price: Union[str, float, Decimal],
        original_price: Optional[Union[str, float, Decimal]] = None
    ) -> bool:
        """Validate deal price"""
        try:
            price_decimal = Decimal(str(price))
            if original_price is not None:
                original_price_decimal = Decimal(str(original_price))
                return 0 <= price_decimal <= original_price_decimal
            return price_decimal >= 0
        except:
            return False

    @staticmethod
    def validate_deal_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate complete deal data"""
        errors = []

        # Validate URL
        if not DealValidator.validate_deal_url(data.get("url", "")):
            errors.append({
                "field": "url",
                "message": "Invalid deal URL",
                "type": "value_error"
            })

        # Validate prices
        if not DealValidator.validate_deal_price(
            data.get("price", 0),
            data.get("original_price")
        ):
            errors.append({
                "field": "price",
                "message": "Invalid price values",
                "type": "value_error"
            })

        if errors:
            raise AppValidationError(errors)

        return data

class NotificationValidator:
    """Notification-specific validation"""
    @staticmethod
    def validate_notification_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate notification data"""
        errors = []

        # Validate title
        if not data.get("title") or len(data["title"]) > 255:
            errors.append({
                "field": "title",
                "message": "Invalid title length",
                "type": "value_error"
            })

        # Validate message
        if not data.get("message") or len(data["message"]) > 1000:
            errors.append({
                "field": "message",
                "message": "Invalid message length",
                "type": "value_error"
            })

        if errors:
            raise AppValidationError(errors)

        return data

class TokenValidator:
    """Token-specific validation"""
    @staticmethod
    def validate_wallet_address(address: str) -> bool:
        """Validate wallet address"""
        # Basic Ethereum address validation
        pattern = r'^0x[a-fA-F0-9]{40}$'
        return bool(re.match(pattern, address))

    @staticmethod
    def validate_transaction_hash(tx_hash: str) -> bool:
        """Validate transaction hash"""
        pattern = r'^0x[a-fA-F0-9]{64}$'
        return bool(re.match(pattern, tx_hash))

    @staticmethod
    def validate_token_amount(amount: Union[str, float, Decimal]) -> bool:
        """Validate token amount"""
        try:
            amount_decimal = Decimal(str(amount))
            return amount_decimal > 0
        except:
            return False

    @staticmethod
    def validate_token_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate token transaction data"""
        errors = []

        # Validate wallet address
        if not TokenValidator.validate_wallet_address(data.get("wallet_address", "")):
            errors.append({
                "field": "wallet_address",
                "message": "Invalid wallet address",
                "type": "value_error"
            })

        # Validate amount
        if not TokenValidator.validate_token_amount(data.get("amount", 0)):
            errors.append({
                "field": "amount",
                "message": "Invalid token amount",
                "type": "value_error"
            })

        if errors:
            raise AppValidationError(errors)

        return data
