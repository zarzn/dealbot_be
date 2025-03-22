"""Deal validation module.

This module provides functionality for validating deals.
"""

import logging
import re
import aiohttp
from typing import Dict, Any, Optional, Tuple, List
from uuid import UUID
from decimal import Decimal
from datetime import datetime

from core.exceptions import (
    ValidationError,
    InvalidDealDataError,
    ExternalServiceError
)

logger = logging.getLogger(__name__)

async def validate_deal(
    self, 
    deal_id: UUID, 
    user_id: Optional[UUID] = None,
    validation_type: str = "all",
    criteria: Optional[Dict[str, Any]] = None,
    validate_url: Optional[bool] = None,
    validate_price: Optional[bool] = None
) -> Dict[str, Any]:
    """Validate a deal against specified criteria.
    
    Args:
        deal_id: The ID of the deal to validate
        user_id: The user requesting validation
        validation_type: Type of validation to perform
        criteria: Custom validation criteria
        validate_url: Whether to validate the URL
        validate_price: Whether to validate the price
        
    Returns:
        Dictionary with validation results
        
    Raises:
        ValidationError: If validation fails
    """
    try:
        # Get deal from repository
        deal = await self._repository.get_by_id(deal_id)
        if not deal:
            raise ValidationError(f"Deal {deal_id} not found")
            
        # Initialize validation results
        validation_results = {
            "deal_id": str(deal_id),
            "validation_type": validation_type,
            "timestamp": datetime.utcnow().isoformat(),
            "is_valid": True,
            "issues": [],
            "warnings": [],
            "validations": {}
        }
        
        # Determine which validations to perform
        if validation_type == "all" or validation_type == "url" or validate_url:
            # Validate URL
            url_valid = await self._validate_url(deal.url)
            validation_results["validations"]["url"] = {
                "is_valid": url_valid,
                "checked_url": deal.url
            }
            
            if not url_valid:
                validation_results["is_valid"] = False
                validation_results["issues"].append("Deal URL is invalid or unreachable")
                
        if validation_type == "all" or validation_type == "price" or validate_price:
            # Validate price
            price_valid = await self._validate_price(deal.price, deal.original_price)
            validation_results["validations"]["price"] = {
                "is_valid": price_valid,
                "checked_price": str(deal.price),
                "checked_original_price": str(deal.original_price) if deal.original_price else None
            }
            
            if not price_valid:
                validation_results["is_valid"] = False
                validation_results["issues"].append("Deal price is invalid or inconsistent")
                
        if validation_type == "all" or validation_type == "metadata":
            # Validate metadata
            metadata_result = {
                "is_valid": True,
                "missing_fields": []
            }
            
            # Check for required metadata fields
            required_fields = ["title", "price", "url"]
            for field in required_fields:
                if not getattr(deal, field, None):
                    metadata_result["is_valid"] = False
                    metadata_result["missing_fields"].append(field)
                    
            validation_results["validations"]["metadata"] = metadata_result
            
            if not metadata_result["is_valid"]:
                validation_results["is_valid"] = False
                validation_results["issues"].append(f"Missing required fields: {', '.join(metadata_result['missing_fields'])}")
                
        if validation_type == "all" or validation_type == "expiration":
            # Validate expiration
            expiration_result = {
                "is_valid": True,
                "is_expired": False
            }
            
            # Check if deal is expired
            if deal.expires_at and deal.expires_at < datetime.utcnow():
                expiration_result["is_valid"] = False
                expiration_result["is_expired"] = True
                
            validation_results["validations"]["expiration"] = expiration_result
            
            if expiration_result["is_expired"]:
                validation_results["is_valid"] = False
                validation_results["issues"].append("Deal has expired")
                
        if validation_type == "all" or validation_type == "custom":
            # Custom validations based on criteria
            if criteria:
                custom_result = {
                    "is_valid": True,
                    "criteria_matched": True,
                    "details": {}
                }
                
                # Check price range
                if "min_price" in criteria and deal.price < Decimal(str(criteria["min_price"])):
                    custom_result["is_valid"] = False
                    custom_result["criteria_matched"] = False
                    custom_result["details"]["price_too_low"] = True
                    
                if "max_price" in criteria and deal.price > Decimal(str(criteria["max_price"])):
                    custom_result["is_valid"] = False
                    custom_result["criteria_matched"] = False
                    custom_result["details"]["price_too_high"] = True
                    
                # Check category
                if "category" in criteria and criteria["category"] and deal.category:
                    if criteria["category"].lower() not in deal.category.lower():
                        custom_result["criteria_matched"] = False
                        custom_result["details"]["category_mismatch"] = True
                        
                validation_results["validations"]["custom"] = custom_result
                
                if not custom_result["criteria_matched"]:
                    validation_results["warnings"].append("Deal does not match custom criteria")
                    
        return validation_results
        
    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Error validating deal {deal_id}: {str(e)}")
        raise ValidationError(f"Failed to validate deal: {str(e)}")

async def validate_deal_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate deal data before creation or update.
    
    Args:
        data: Deal data to validate
        
    Returns:
        Validated and normalized deal data
        
    Raises:
        InvalidDealDataError: If data is invalid
    """
    try:
        validated_data = data.copy()
        
        # Check required fields for new deals
        if "id" not in data:  # Only for new deals
            required_fields = ["title", "price"]
            missing_fields = [field for field in required_fields if field not in data or not data[field]]
            if missing_fields:
                raise InvalidDealDataError(f"Missing required fields: {', '.join(missing_fields)}")
                
        # Validate URL format
        if "url" in data and data["url"]:
            url = data["url"]
            # Simple URL validation
            if not url.startswith(("http://", "https://")):
                validated_data["url"] = f"https://{url}"
                
            # Check URL length
            if len(validated_data["url"]) > 2048:  # Max URL length
                raise InvalidDealDataError("URL is too long (max 2048 characters)")
                
        # Validate price
        if "price" in data:
            try:
                price = Decimal(str(data["price"]))
                
                # Price must be positive
                if price <= Decimal('0'):
                    validated_data["price"] = Decimal('0.01')  # Set to minimum valid price
                    logger.warning(f"Adjusted zero or negative price to 0.01")
                else:
                    validated_data["price"] = price  # Store as Decimal
            except (ValueError, TypeError, InvalidOperation):
                raise InvalidDealDataError(f"Invalid price format: {data['price']}")
                
        # Validate original price
        if "original_price" in data and data["original_price"]:
            try:
                original_price = Decimal(str(data["original_price"]))
                
                # Original price must be positive
                if original_price <= Decimal('0'):
                    validated_data["original_price"] = None  # Remove invalid original price
                    logger.warning(f"Removed zero or negative original price")
                else:
                    validated_data["original_price"] = original_price
                    
                # Original price should be >= price
                if "price" in validated_data and validated_data["original_price"] < validated_data["price"]:
                    # Swap them if original is lower than current
                    validated_data["original_price"], validated_data["price"] = validated_data["price"], validated_data["original_price"]
                    logger.warning(f"Swapped price and original_price because original was lower")
            except (ValueError, TypeError, InvalidOperation):
                validated_data["original_price"] = None
                logger.warning(f"Removed invalid original price: {data['original_price']}")
                
        # Validate currency
        if "currency" in data and data["currency"]:
            # Ensure currency is a 3-letter code
            currency = data["currency"].upper()
            if not re.match(r'^[A-Z]{3}$', currency):
                validated_data["currency"] = "USD"  # Default to USD for invalid currencies
                logger.warning(f"Replaced invalid currency '{data['currency']}' with USD")
            else:
                validated_data["currency"] = currency
                
        # Validate dates
        for date_field in ["expires_at", "found_at"]:
            if date_field in data and data[date_field]:
                try:
                    # If it's a string, convert to datetime
                    if isinstance(data[date_field], str):
                        validated_data[date_field] = datetime.fromisoformat(data[date_field].replace('Z', '+00:00'))
                    # If it's already a datetime, keep it
                    elif isinstance(data[date_field], datetime):
                        pass
                    else:
                        raise ValueError(f"Invalid date format for {date_field}")
                except (ValueError, TypeError):
                    validated_data[date_field] = None
                    logger.warning(f"Removed invalid date for {date_field}: {data[date_field]}")
                    
        # Validate JSON fields
        for json_field in ["seller_info", "deal_metadata", "price_metadata"]:
            if json_field in data:
                if data[json_field] is None:
                    validated_data[json_field] = {}
                elif not isinstance(data[json_field], dict):
                    try:
                        # Try to convert to dict
                        validated_data[json_field] = dict(data[json_field])
                    except (ValueError, TypeError):
                        validated_data[json_field] = {}
                        logger.warning(f"Converted invalid {json_field} to empty dict")
                        
        return validated_data
        
    except InvalidDealDataError:
        raise
    except Exception as e:
        logger.error(f"Error validating deal data: {str(e)}")
        raise InvalidDealDataError(f"Failed to validate deal data: {str(e)}")

async def _validate_url(self, url: str) -> bool:
    """Validate if a URL is accessible and returns valid content.
    
    Args:
        url: The URL to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not url:
        return False
        
    try:
        async with aiohttp.ClientSession() as session:
            async with session.head(url, allow_redirects=True, timeout=10) as response:
                return response.status < 400  # Valid if status code is not an error
    except Exception as e:
        logger.warning(f"Failed to validate URL {url}: {str(e)}")
        return False

async def _validate_price(self, price: Decimal, original_price: Optional[Decimal]) -> bool:
    """Validate price and original price relationship.
    
    Args:
        price: Current price
        original_price: Original price before discount
        
    Returns:
        True if valid, False otherwise
    """
    # Price must be positive
    if price <= Decimal('0'):
        return False
        
    # If original price exists, it should be >= price
    if original_price is not None and original_price < price:
        return False
        
    return True 