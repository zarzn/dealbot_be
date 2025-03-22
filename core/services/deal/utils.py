"""Deal service utility functions.

This module provides utility functions for the DealService.
"""

from typing import Dict, Any, Union, TypeVar, Callable
from uuid import UUID
from datetime import datetime
import logging
import functools

logger = logging.getLogger(__name__)

# Type variables for generic decorator
T = TypeVar('T')
R = TypeVar('R')

def _safe_copy_dict(data: Any) -> Dict[str, Any]:
    """Safely copy a dictionary, handling None and non-dict values.
    
    Args:
        data: The data to copy
        
    Returns:
        A safe copy of the data as a dictionary
    """
    if data is None:
        return {}
    
    if not isinstance(data, dict):
        try:
            # Try to convert to dict if possible
            return dict(data)
        except (TypeError, ValueError):
            # Return a string representation if conversion fails
            return {"value": str(data)}
    
    # Make a shallow copy to avoid modifying the original
    return {k: v for k, v in data.items() if k is not None}

def _deal_to_dict(deal: Any) -> Dict[str, Any]:
    """Convert a deal object to a dictionary.
    
    Args:
        deal: The deal object
        
    Returns:
        Dictionary representation of the deal
    """
    try:
        # Create a basic dict with only the essential properties
        # This avoids any potential circular references
        result = {
            "id": str(deal.id) if hasattr(deal, 'id') and deal.id else None,
            "user_id": str(deal.user_id) if hasattr(deal, 'user_id') and deal.user_id else None,
            "goal_id": (
                str(deal.goal_id) 
                if hasattr(deal, 'goal_id') and deal.goal_id and deal.goal_id != UUID('00000000-0000-0000-0000-000000000000') 
                else None
            ),
            "market_id": str(deal.market_id) if hasattr(deal, 'market_id') and deal.market_id else None,
            "title": deal.title if hasattr(deal, 'title') else "Unknown Deal",
            "description": deal.description if hasattr(deal, 'description') else "",
            "url": deal.url if hasattr(deal, 'url') else None,
            "price": float(deal.price) if hasattr(deal, 'price') and deal.price else 0.0,
            "original_price": float(deal.original_price) if hasattr(deal, 'original_price') and deal.original_price else None,
            "currency": deal.currency if hasattr(deal, 'currency') else "USD",
            "source": deal.source if hasattr(deal, 'source') else "",
            "image_url": deal.image_url if hasattr(deal, 'image_url') else None,
            "category": deal.category if hasattr(deal, 'category') else None,
            "seller_info": _safe_copy_dict(deal.seller_info) if hasattr(deal, 'seller_info') else {},
            "availability": _safe_copy_dict(deal.availability) if hasattr(deal, 'availability') else {"in_stock": True},
            "found_at": deal.found_at.isoformat() if hasattr(deal, 'found_at') and deal.found_at else None,
            "expires_at": deal.expires_at.isoformat() if hasattr(deal, 'expires_at') and deal.expires_at else None,
            "status": deal.status if hasattr(deal, 'status') else "active",
            "priority": deal.priority if hasattr(deal, 'priority') else "medium",
            "deal_score": deal.deal_score if hasattr(deal, 'deal_score') else None,
            "metadata": _safe_copy_dict(deal.metadata) if hasattr(deal, 'metadata') else {},
            "price_metadata": _safe_copy_dict(deal.price_metadata) if hasattr(deal, 'price_metadata') else {},
            "is_flash_deal": deal.is_flash_deal if hasattr(deal, 'is_flash_deal') else False,
        }
        
        # Add computed fields if available
        if hasattr(deal, 'discount_percentage') and deal.discount_percentage:
            result['discount_percentage'] = float(deal.discount_percentage)
        
        if hasattr(deal, 'created_at') and deal.created_at:
            result['created_at'] = deal.created_at.isoformat()
            
        if hasattr(deal, 'updated_at') and deal.updated_at:
            result['updated_at'] = deal.updated_at.isoformat()
            
        return result
    except Exception as e:
        # Fallback for any unexpected errors
        return {
            "id": str(deal.id) if hasattr(deal, 'id') and deal.id else "unknown",
            "title": str(deal.title) if hasattr(deal, 'title') else "Unknown Deal",
            "error": f"Failed to convert deal to dictionary: {str(e)}"
        }

async def _convert_deal_to_dict(deal: Any) -> Dict[str, Any]:
    """Asynchronously convert a deal object to a dictionary.
    
    This is a wrapper around _deal_to_dict for async compatibility.
    
    Args:
        deal: The deal object
        
    Returns:
        Dictionary representation of the deal
    """
    return _deal_to_dict(deal)

def log_exceptions(func: Callable[..., R]) -> Callable[..., R]:
    """Decorator to log exceptions raised by a function."""
    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> R:
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.exception(f"Exception in {func.__name__}: {str(e)}")
            raise
    return wrapper 