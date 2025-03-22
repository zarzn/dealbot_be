"""
Utility functions for deal search.

This module provides utility functions for deal search operations,
including validation, conversion, and helper functions.
"""

import logging
from typing import List, Dict, Any, Optional, Union
from uuid import UUID, uuid5, NAMESPACE_DNS
from datetime import datetime

from core.models.enums import MarketCategory, MarketType
from core.utils.logger import get_logger

logger = get_logger(__name__)

def is_valid_market_category(self, category: str) -> bool:
    """
    Check if a category string is valid for the marketplace.
    
    Args:
        category: The category string to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        # Check if it's a valid enum value
        return category.lower() in [c.value.lower() for c in MarketCategory]
    except (AttributeError, ValueError):
        return False

def get_market_id_for_category(self, category: str) -> UUID:
    """Get the market ID for a given category.
    
    Args:
        category: Category name
        
    Returns:
        UUID: Market ID for the category
    """
    try:
        # TODO: Implement proper market selection based on category
        from uuid import uuid5, NAMESPACE_DNS
        
        # Use UUID5 for deterministic generation based on category
        return uuid5(NAMESPACE_DNS, category.lower())
    except Exception as e:
        logger.error(f"Error getting market ID for category {category}: {str(e)}")
        # Fallback to a default market ID
        from uuid import uuid5, NAMESPACE_DNS
        return uuid5(NAMESPACE_DNS, "default_market")

def extract_market_type(url: str) -> Optional[MarketType]:
    """Extract market type from URL.
    
    Args:
        url: URL to extract market type from
        
    Returns:
        MarketType enum value or None if not recognized
    """
    try:
        if 'amazon' in url:
            return MarketType.AMAZON
        elif 'walmart' in url:
            return MarketType.WALMART
        elif 'ebay' in url:
            return MarketType.EBAY
        elif 'google' in url or 'googleshopping' in url:
            return MarketType.GOOGLE_SHOPPING
        elif 'bestbuy' in url:
            return MarketType.BESTBUY
        return None
    except Exception:
        return None

def extract_product_id(url: str) -> Optional[str]:
    """Extract product ID from URL.
    
    Args:
        url: URL to extract product ID from
        
    Returns:
        Product ID string or None if not recognized
    """
    try:
        # Amazon: /dp/XXXXXXXXXX or /gp/product/XXXXXXXXXX
        if 'amazon' in url:
            if '/dp/' in url:
                return url.split('/dp/')[1].split('/')[0]
            elif '/product/' in url:
                return url.split('/product/')[1].split('/')[0]
        # Walmart: /ip/XXXXX
        elif 'walmart' in url:
            return url.split('/ip/')[1].split('/')[0]
        # eBay: /itm/XXXXX
        elif 'ebay' in url:
            return url.split('/itm/')[1].split('/')[0]
        # Best Buy: /site/XXXXX.p
        elif 'bestbuy' in url:
            return url.split('/')[-1].split('.p')[0]
        return None
    except Exception:
        return None

def convert_to_response(self, deal, user_id=None, include_ai_analysis=False):
    """Convert a Deal model object to a response dictionary.
    
    Args:
        deal: Deal model object
        user_id: Optional user ID
        include_ai_analysis: Whether to include AI analysis
        
    Returns:
        Dictionary representation of the deal for API response
    """
    if not deal:
        return None
    
    # Base deal information
    deal_dict = {
        "id": str(deal.id),
        "title": deal.title,
        "description": deal.description,
        "price": float(deal.price) if deal.price else None,
        "original_price": float(deal.original_price) if deal.original_price else None,
        "currency": deal.currency,
        "url": deal.url,
        "image_url": deal.image_url,
        "category": deal.category,
        "status": deal.status,
        "found_at": deal.found_at.isoformat() if deal.found_at else None,
        "expires_at": deal.expires_at.isoformat() if deal.expires_at else None,
        "source": deal.source,
        "metadata": deal.metadata or {},
        # Add the required fields that were missing
        "market_id": str(deal.market_id) if hasattr(deal, 'market_id') and deal.market_id else None,
        "seller_info": deal.seller_info if hasattr(deal, 'seller_info') and deal.seller_info else {},
        "availability": deal.availability if hasattr(deal, 'availability') and deal.availability else {},
        "created_at": deal.created_at.isoformat() if hasattr(deal, 'created_at') and deal.created_at else datetime.utcnow().isoformat(),
        "updated_at": deal.updated_at.isoformat() if hasattr(deal, 'updated_at') and deal.updated_at else datetime.utcnow().isoformat()
    }
    
    # Add market information if available without triggering lazy loading
    # Use market_id to identify if market exists, but don't access market relationship directly
    if hasattr(deal, 'market_id') and deal.market_id:
        # Just include the market ID reference without loading the full market object
        deal_dict["market"] = {
            "id": str(deal.market_id)
        }
        
        # If market is already loaded (but don't trigger a load)
        if 'market' in deal.__dict__ and deal.__dict__['market'] is not None:
            market = deal.__dict__['market']
            deal_dict["market"].update({
                "name": market.name,
                "type": market.type
            })
    
    # Add user-specific information if user_id is provided
    if user_id:
        # Check if the user has saved this deal
        is_saved = False
        if hasattr(self, '_repository') and hasattr(self._repository, 'is_deal_saved_by_user'):
            try:
                is_saved = self._repository.is_deal_saved_by_user(deal.id, user_id)
            except Exception as e:
                logger.error(f"Error checking if deal is saved: {str(e)}")
        
        deal_dict["user_actions"] = {
            "is_saved": is_saved
        }
    
    # Add AI analysis if requested
    if include_ai_analysis and hasattr(deal, 'ai_analysis'):
        deal_dict["ai_analysis"] = deal.ai_analysis
    
    return deal_dict 