"""Validation utility functions."""

from typing import Any, Dict, List, Optional, Union
from datetime import datetime
import re
from decimal import Decimal
import uuid
from pydantic import BaseModel, ValidationError
from urllib.parse import urlparse

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
        """Validate URL format.
        
        Args:
            url: URL to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not url or not isinstance(url, str):
            return False
            
        # Trim whitespace
        url = url.strip()
        
        # Basic URL validation first
        try:
            result = urlparse(url)
            
            # Check for scheme and netloc
            valid = all([result.scheme, result.netloc])
            
            # Allow only http and https schemes
            if valid and result.scheme not in ('http', 'https'):
                return False
                
            # Check for minimum required components of a valid URL
            if valid:
                # Must have a domain with at least one dot
                if '.' not in result.netloc:
                    return False
                    
                # Domain-specific validations
                domain = result.netloc.lower()
                
                # Block certain dangerous or private domains
                blocked_domains = [
                    'localhost', '127.0.0.1', '0.0.0.0', 'internal', 
                    '.local', '.test', '.example', '.invalid'
                ]
                if any(bd in domain for bd in blocked_domains):
                    return False
                
            return valid
        except Exception:
            return False

    @staticmethod
    def sanitize_url(url: str) -> str:
        """Sanitize a URL, removing unsafe characters and normalizing format.
        
        Args:
            url: URL to sanitize
            
        Returns:
            Sanitized URL string
        """
        # Handle None value
        if url is None:
            logger.warning("Cannot sanitize None URL")
            return ""
            
        # Handle non-string values
        if not isinstance(url, str):
            try:
                url = str(url)
                logger.warning(f"URL was not a string, converted to: {url}")
            except Exception as e:
                logger.error(f"Failed to convert URL to string: {str(e)}")
                return ""
            
        # Trim whitespace
        url = url.strip()
        if not url:
            return ""
        
        try:
            # Handle URL encoding issues
            # First try to unquote the URL (in case it's double-encoded)
            try:
                from urllib.parse import unquote
                decoded_url = unquote(url)
                # Only use the decoded URL if it looks valid
                if not re.search(r'%[0-9a-fA-F]{2}', decoded_url):
                    url = decoded_url
            except Exception as e:
                logger.warning(f"Error unquoting URL: {str(e)}")
                
            # Basic sanitization to remove unsafe characters
            url = re.sub(r'[\x00-\x1F\x7F]', '', url)  # Remove control characters
            
            # Replace spaces with URL-encoded spaces (%20)
            url = url.replace(' ', '%20')
            
            # Remove unsafe script tags
            url = re.sub(r'<script.*?>.*?</script>', '', url, flags=re.IGNORECASE | re.DOTALL)
            
            # Remove other potentially dangerous HTML tags
            url = re.sub(r'<.*?>', '', url)
            
            # Check for a valid scheme
            try:
                parsed = urlparse(url)
                if parsed.scheme not in ('http', 'https', ''):
                    # Invalid scheme, default to https
                    if '://' in url:  # Only replace if there's an actual scheme separator
                        url = re.sub(r'^[^:]+://', 'https://', url)
                        logger.debug(f"Changed scheme to https: {url}")
                    else:
                        # No scheme, prepend https if the URL starts with a domain-like pattern
                        if re.match(r'^[a-zA-Z0-9][a-zA-Z0-9-]*\.[a-zA-Z]{2,}', url):
                            url = 'https://' + url
                            logger.debug(f"Added https:// to URL: {url}")
                
                # Make sure there are no consecutive slashes in the path
                if parsed.netloc and parsed.path:
                    parsed_path = re.sub(r'//+', '/', parsed.path)
                    # Reconstruct the URL with the sanitized path
                    if parsed.scheme:
                        original = url
                        url = f"{parsed.scheme}://{parsed.netloc}{parsed_path}"
                        if parsed.query:
                            url += f"?{parsed.query}"
                        if parsed.fragment:
                            url += f"#{parsed.fragment}"
                        logger.debug(f"Normalized URL path: {original} -> {url}")
            except Exception as e:
                logger.warning(f"Error parsing URL structure: {str(e)}")
            
            return url
            
        except Exception as e:
            logger.warning(f"Error sanitizing URL: {str(e)}")
            # In case of error, return original URL but remove control characters
            try:
                return re.sub(r'[\x00-\x1F\x7F]', '', url)
            except Exception as e2:
                logger.error(f"Critical error during URL sanitization fallback: {str(e2)}")
                return ""
        
    @staticmethod
    def normalize_url(url: str, source: Optional[str] = None) -> str:
        """Normalize a URL, converting relative URLs to absolute URLs.
        
        Args:
            url: URL to normalize
            source: Optional source identifier (e.g., 'amazon', 'walmart')
            
        Returns:
            Normalized absolute URL
        """
        # Handle non-string URLs
        if url is None:
            logger.warning("Cannot normalize None URL")
            return ""
            
        if not isinstance(url, str):
            try:
                url = str(url)
                logger.warning(f"URL was not a string, converted to: {url}")
            except Exception as e:
                logger.error(f"Failed to convert URL to string: {str(e)}")
                return ""
                
        if not url.strip():
            return ""
            
        # Clean the URL first
        url = Validator.sanitize_url(url)
        
        # Handle triple slash URL issue (https:/// -> https://www.domain.com/)
        if url.startswith("https:///"):
            # First try to determine source from URL patterns if source not provided
            if not source:
                if '/dp/' in url or '/gp/product/' in url:
                    source = 'amazon'
                elif '/ip/' in url:
                    source = 'walmart'
                elif '/itm/' in url:
                    source = 'ebay'
                elif 'tbm=shop' in url or 'shopping' in url:
                    source = 'google_shopping'
            
            # Fix triple slash based on source
            if source == 'amazon' or '/dp/' in url or '/gp/product/' in url:
                url = url.replace("https:///", "https://www.amazon.com/")
            elif source == 'walmart' or '/ip/' in url:
                url = url.replace("https:///", "https://www.walmart.com/")
            elif source == 'ebay' or '/itm/' in url:
                url = url.replace("https:///", "https://www.ebay.com/")
            elif source == 'google_shopping':
                url = url.replace("https:///", "https://www.google.com/")
            else:
                # Default to amazon.com if no source but looks like Amazon
                if '/dp/' in url or '/gp/product/' in url:
                    url = url.replace("https:///", "https://www.amazon.com/")
                else:
                    url = url.replace("https:///", "https://")
        
        # Also check for http:/// format
        if url.startswith("http:///"):
            # Similar source determination as above
            if not source:
                if '/dp/' in url or '/gp/product/' in url:
                    source = 'amazon'
                elif '/ip/' in url:
                    source = 'walmart'
                elif '/itm/' in url:
                    source = 'ebay'
                elif 'tbm=shop' in url or 'shopping' in url:
                    source = 'google_shopping'
            
            # Fix triple slash based on source
            if source == 'amazon' or '/dp/' in url or '/gp/product/' in url:
                url = url.replace("http:///", "http://www.amazon.com/")
            elif source == 'walmart' or '/ip/' in url:
                url = url.replace("http:///", "http://www.walmart.com/")
            elif source == 'ebay' or '/itm/' in url:
                url = url.replace("http:///", "http://www.ebay.com/")
            elif source == 'google_shopping':
                url = url.replace("http:///", "http://www.google.com/")
            else:
                # Generic fallback
                url = url.replace("http:///", "http://")
        
        # If it's already absolute, return it
        if url.startswith(('http://', 'https://')):
            return url
            
        # Handle relative URLs based on source
        if url.startswith('/'):
            # Determine the base URL based on source or path patterns
            if source == 'amazon' or '/dp/' in url or '/gp/product/' in url:
                return f"https://www.amazon.com{url}"
            elif source == 'walmart' or '/ip/' in url:
                return f"https://www.walmart.com{url}"
            elif source == 'ebay' or '/itm/' in url:
                return f"https://www.ebay.com{url}"
            elif source == 'google_shopping':
                return f"https://www.google.com{url}"
            else:
                # Default to amazon.com if source not specified but has amazon-like patterns
                if '/dp/' in url or '/gp/product/' in url:
                    return f"https://www.amazon.com{url}"
                # Generic fallback
                return f"https://www.example.com{url}"
        
        # If it's a domain without scheme, add https://
        if '.' in url and not url.startswith(('http://', 'https://')):
            return f"https://{url}"
            
        return url
    
    @staticmethod
    def validate_and_sanitize_url(url: str) -> tuple[bool, Optional[str]]:
        """Validate and sanitize a URL.
        
        Args:
            url: URL to validate and sanitize
            
        Returns:
            Tuple of (is_valid, sanitized_url)
        """
        # Check if URL is None or not a string
        if url is None:
            logger.warning("URL is None, cannot validate")
            return False, None
        
        if not isinstance(url, str):
            try:
                # Try to convert to string if possible
                url = str(url)
                logger.warning(f"URL was not a string, converted to: {url}")
            except Exception as e:
                logger.error(f"Failed to convert URL to string: {str(e)}")
                return False, None
            
        # Check if URL is empty after conversion
        if not url.strip():
            logger.warning("URL is empty or only whitespace")
            return False, None
        
        try:
            # First sanitize the URL
            sanitized = Validator.sanitize_url(url)
            
            # Now normalize it (convert relative to absolute)
            normalized = Validator.normalize_url(sanitized)
            
            # Check if it's a valid URL after normalization
            if Validator.validate_url(normalized):
                return True, normalized
            
            # If URL doesn't pass strict validation but appears to be from a known marketplace,
            # we'll still return it with a warning
            if ('/dp/' in normalized or '/gp/product/' in normalized or  # Amazon patterns
                '/ip/' in normalized or  # Walmart patterns
                '/itm/' in normalized or  # eBay patterns
                'amazon.com' in normalized or 
                'walmart.com' in normalized or 
                'ebay.com' in normalized or
                'google.com/shopping' in normalized):
                
                logger.warning(f"URL '{normalized}' is not strictly valid but appears to be a marketplace URL; accepting it")
                return True, normalized
                
            # Last resort fallback for URLs with triple slashes
            if normalized.startswith("https:///"):
                fixed_url = normalized.replace("https:///", "https://www.amazon.com/")
                logger.warning(f"Fixed malformed URL: {url} -> {fixed_url}")
                return True, fixed_url
            
            logger.warning(f"URL validation failed for: {url}")
            return False, None
        except Exception as e:
            logger.warning(f"URL validation error: {str(e)}")
            
            # Emergency fallback - if all else fails but we have something
            # that looks like a URL, try to make it usable
            if url and ('amazon.com' in url or 'walmart.com' in url or '/dp/' in url):
                # Last-ditch effort to salvage the URL
                fixed_url = url
                if url.startswith('https:///'):
                    fixed_url = url.replace('https:///', 'https://www.amazon.com/')
                elif not url.startswith(('http://', 'https://')):
                    fixed_url = f"https://www.amazon.com/{url.lstrip('/')}"
                    
                logger.warning(f"Emergency URL fix applied: {url} -> {fixed_url}")
                return True, fixed_url
                
            return False, None

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
        """Validate a deal URL.
        
        Args:
            url: URL to validate
        
        Returns:
            True if valid, False otherwise
        """
        if not url:
            return False
            
        # First normalize the URL to handle relative paths
        normalized_url = Validator.normalize_url(url)
        
        # Then validate the normalized URL
        return Validator.validate_url(normalized_url)

    @staticmethod
    def sanitize_deal_url(url: str) -> str:
        """Sanitize a deal URL.
        
        Args:
            url: URL to sanitize
        
        Returns:
            Sanitized URL
        """
        if not url:
            return ""
            
        return Validator.normalize_url(url)

    @staticmethod
    def validate_and_sanitize_deal_url(url: str) -> tuple[bool, Optional[str]]:
        """Validate and sanitize a deal URL.
        
        Args:
            url: URL to validate and sanitize
            
        Returns:
            Tuple of (is_valid, sanitized_url)
        """
        if not url:
            return False, None
        
        try:
            # First clean the URL
            sanitized = Validator.sanitize_url(url)
            
            # Then normalize it (handle relative URLs)
            normalized = Validator.normalize_url(sanitized)
            
            # Validate the normalized URL
            if Validator.validate_url(normalized):
                return True, normalized
                
            return False, None
        except Exception as e:
            logger.warning(f"Deal URL validation error: {str(e)}")
            return False, None

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
        validated_data = data.copy()

        # Validate and sanitize URL
        if "url" in data and data["url"]:
            is_valid, sanitized_url = DealValidator.validate_and_sanitize_deal_url(data["url"])
            if not is_valid:
                errors.append({
                    "field": "url",
                    "message": "Invalid deal URL",
                    "type": "value_error"
                })
            else:
                validated_data["url"] = sanitized_url

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

        return validated_data

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
