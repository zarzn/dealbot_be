"""E-commerce utilities module for API integrations."""

from typing import Dict, Any, Optional
from .amazon_api import AmazonAPI
from .walmart_api import WalmartAPI

class EcommerceAPIError(Exception):
    """Base exception for e-commerce API errors."""
    def __init__(
        self,
        message: str,
        service_name: str,
        operation: str,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.service_name = service_name
        self.operation = operation
        self.details = details or {}
        super().__init__(self.message)

__all__ = [
    'AmazonAPI',
    'WalmartAPI',
    'EcommerceAPIError'
] 