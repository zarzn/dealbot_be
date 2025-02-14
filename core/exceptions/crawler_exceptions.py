"""Crawler-related exceptions module."""

from typing import Dict, Any, Optional, List
from .base_exceptions import BaseError, ValidationError

class CrawlerError(BaseError):
    """Base class for crawler-related errors."""
    
    def __init__(
        self,
        message: str = "Crawler operation failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.details = details or {}
        
    def _get_details(self) -> Dict[str, Any]:
        return self.details

class CrawlerRequestError(CrawlerError):
    """Raised when a crawler request fails."""
    
    def __init__(
        self,
        url: str,
        status_code: Optional[int] = None,
        error_details: Optional[Dict[str, Any]] = None,
        message: str = "Crawler request failed"
    ):
        super().__init__(
            message=message,
            details={
                "url": url,
                "status_code": status_code,
                "error_details": error_details or {}
            }
        )

class CrawlerParsingError(CrawlerError):
    """Raised when parsing of crawled content fails."""
    
    def __init__(
        self,
        url: str,
        selector: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None,
        message: str = "Content parsing failed"
    ):
        super().__init__(
            message=message,
            details={
                "url": url,
                "selector": selector,
                "error_details": error_details or {}
            }
        )

class CrawlerRateLimitError(CrawlerError):
    """Raised when crawler hits rate limits."""
    
    def __init__(
        self,
        domain: str,
        current_rate: float,
        limit: float,
        reset_time: Optional[str] = None,
        message: str = "Rate limit exceeded"
    ):
        super().__init__(
            message=message,
            details={
                "domain": domain,
                "current_rate": current_rate,
                "limit": limit,
                "reset_time": reset_time
            }
        )

class CrawlerBlockedError(CrawlerError):
    """Raised when crawler is blocked by the target site."""
    
    def __init__(
        self,
        domain: str,
        ip_address: Optional[str] = None,
        block_details: Optional[Dict[str, Any]] = None,
        message: str = "Crawler blocked by target site"
    ):
        super().__init__(
            message=message,
            details={
                "domain": domain,
                "ip_address": ip_address,
                "block_details": block_details or {}
            }
        )

class InvalidCrawlerConfigError(CrawlerError):
    """Raised when crawler configuration is invalid."""
    
    def __init__(
        self,
        config_errors: List[str],
        message: str = "Invalid crawler configuration"
    ):
        super().__init__(
            message=message,
            details={"config_errors": config_errors}
        )

__all__ = [
    'CrawlerError',
    'CrawlerRequestError',
    'CrawlerParsingError',
    'CrawlerRateLimitError',
    'CrawlerBlockedError',
    'InvalidCrawlerConfigError'
] 