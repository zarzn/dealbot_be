"""
Deal creation utilities for the search module.

This module provides functions for creating deals from various data sources,
including products, dictionaries, and external data.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple, Union
from uuid import UUID, uuid4
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select

from core.models.deal import Deal
from core.models.market import Market
from core.models.enums import MarketCategory, MarketType, DealSource
from core.utils.logger import get_logger

logger = get_logger(__name__)

async def create_deal_from_product(
    self,
    product: Dict[str, Any],
    query: str,
    market_type: str = None,
    user_id: Optional[UUID] = None,
    goal_id: Optional[UUID] = None,
    source: str = "api"
) -> Optional[Deal]:
    """Create a deal from a product object.
    
    Args:
        product: Product data dictionary
        query: Search query used to find the product
        market_type: Market type (e.g., amazon, walmart, google_shopping)
        user_id: Optional user ID
        goal_id: Optional goal ID
        source: Source of the product data
        
    Returns:
        Created Deal object or None if creation failed
    """
    try:
        from decimal import Decimal
        from core.models.market import Market
        from core.models.enums import MarketCategory, MarketType
        
        # If no user ID is provided, use system user
        if not user_id:
            from core.config import settings
            system_user_id = getattr(settings, "SYSTEM_USER_ID", None)
            if system_user_id:
                user_id = UUID(system_user_id)
            else:
                logger.error("No user ID provided and no SYSTEM_USER_ID in settings")
                return None
                
        # Required fields
        if 'title' not in product or not product['title']:
            logger.warning("Product missing title, skipping")
            return None
            
        if 'price' not in product or product['price'] is None:
            logger.warning("Product missing price, skipping")
            return None
            
        if 'url' not in product or not product['url']:
            logger.warning("Product missing URL, skipping")
            return None
            
        # Get market_id from market_type
        market_id = None
        market_name = None
        
        if market_type:
            # Find the market by type
            market_query = select(Market).where(Market.type == market_type)
            market_result = await self.db.execute(market_query)
            market = market_result.scalar_one_or_none()
            
            if market:
                market_id = market.id
                market_name = market.name
                logger.info(f"Found market ID {market_id} and name {market_name} for type {market_type}")
            else:
                logger.warning(f"No market found for type: {market_type}, using default")
        
        # If market_name is not found, set it based on the source or market_type
        if not market_name:
            # Check if market_name is provided in the product data
            if 'market_name' in product and product['market_name']:
                market_name = product['market_name']
            # Otherwise determine market name from market_type
            elif market_type:
                market_name = market_type.capitalize()
                # Map common market types to readable names
                market_name_map = {
                    'amazon': 'Amazon',
                    'walmart': 'Walmart',
                    'ebay': 'eBay',
                    'google_shopping': 'Google Shopping',
                    'target': 'Target',
                    'bestbuy': 'Best Buy',
                    'api': 'Web API'
                }
                if market_type.lower() in market_name_map:
                    market_name = market_name_map[market_type.lower()]
            # If no market_name or market_type, use the source
            else:
                source_name = product.get('source', source)
                if source_name == 'api':
                    # Determine a better name than 'api'
                    if 'amazon' in str(product.get('url', '')).lower():
                        market_name = 'Amazon'
                    elif 'walmart' in str(product.get('url', '')).lower():
                        market_name = 'Walmart'
                    elif 'target' in str(product.get('url', '')).lower():
                        market_name = 'Target'
                    elif 'ebay' in str(product.get('url', '')).lower():
                        market_name = 'eBay'
                    elif 'bestbuy' in str(product.get('url', '')).lower():
                        market_name = 'Best Buy'
                    else:
                        market_name = 'Web Marketplace'
                else:
                    market_name = source_name.capitalize()
        
        if not market_id:
            logger.warning("No market ID available, cannot create deal")
            return None
            
        # Get all valid MarketCategory enum values
        valid_categories = [category.value for category in MarketCategory]
        logger.info(f"Valid market categories: {valid_categories}")
        
        # Default to OTHER category
        mapped_category = MarketCategory.OTHER.value
        
        # Map from the AI query analysis if available
        ai_query_analysis = product.get('ai_query_analysis', {})
        if ai_query_analysis and ai_query_analysis.get('category'):
            category_from_ai = ai_query_analysis.get('category', '').lower()
            logger.info(f"AI suggested category: {category_from_ai}")
            
            # Check if the AI suggested category directly matches a valid enum value (case-insensitive)
            for enum_category in MarketCategory:
                if enum_category.value.lower() == category_from_ai.lower():
                    mapped_category = enum_category.value
                    logger.info(f"Direct match found: AI category '{category_from_ai}' maps to enum value '{mapped_category}'")
                    break
        
        # Final validation to ensure we only use valid MarketCategory values
        if mapped_category not in valid_categories:
            logger.warning(f"Category '{mapped_category}' is not in valid MarketCategory enum values, defaulting to 'other'")
            mapped_category = MarketCategory.OTHER.value
        
        # Convert to a valid format for creating a deal
        deal_data = {
            "user_id": user_id,
            "market_id": market_id,
            "goal_id": goal_id,
            "title": product.get('title', ''),
            "description": product.get('description', ''),
            "url": product.get('url', ''),
            "source": market_name if market_name else source,  # Use market_name if available, otherwise fallback to source parameter
            "currency": product.get('currency', 'USD'),
            "category": mapped_category
        }
        
        # Store search query in deal metadata
        if not deal_data.get("deal_metadata"):
            deal_data["deal_metadata"] = {}
        
        deal_data["deal_metadata"]["search_query"] = query
        
        # Store market_name in deal_metadata instead of directly in deal_data
        if market_name:
            deal_data["deal_metadata"]["market_name"] = market_name
        
        # Handle price - ensure it's a Decimal
        try:
            deal_data['price'] = Decimal(str(product['price']))
            if deal_data['price'] <= Decimal('0'):
                deal_data['price'] = Decimal('0.01')  # Minimum valid price
        except (ValueError, TypeError, Exception) as e:
            logger.warning(f"Invalid price format: {product['price']}, setting to minimum: {str(e)}")
            deal_data['price'] = Decimal('0.01')
            
        # Handle original price if available
        if 'original_price' in product and product['original_price']:
            try:
                original_price = Decimal(str(product['original_price']))
                if original_price > deal_data['price']:
                    deal_data['original_price'] = original_price
                else:
                    logger.warning("Original price not greater than price, ignoring")
            except (ValueError, TypeError, Exception) as e:
                logger.warning(f"Invalid original price format: {product['original_price']}, ignoring: {str(e)}")
                
        # Handle images
        if 'image_url' in product and product['image_url']:
            deal_data['image_url'] = product['image_url']
        elif 'image' in product and product['image']:
            deal_data['image_url'] = product['image']
        elif 'images' in product and product['images'] and len(product['images']) > 0:
            # Take the first image if it's a list
            if isinstance(product['images'], list):
                deal_data['image_url'] = product['images'][0]
            elif isinstance(product['images'], str):
                deal_data['image_url'] = product['images']
        
        # Initialize seller_info with default values
        seller_info = {
            "name": "Unknown Seller",
            "rating": None,
            "reviews": None
        }
        
        # Safely get seller from product or its metadata
        try:
            # First try to get seller directly from product
            if 'seller' in product and product['seller']:
                seller_info["name"] = product['seller']
            
            # Try to get rating and reviews from different possible locations
            if 'rating' in product:
                try:
                    seller_info['rating'] = float(product['rating'])
                except (ValueError, TypeError):
                    pass
                    
            if 'review_count' in product:
                try:
                    seller_info['reviews'] = int(product['review_count'])
                except (ValueError, TypeError):
                    pass
            
            # Check metadata for additional info
            if 'metadata' in product and isinstance(product['metadata'], dict):
                metadata = product['metadata']
                
                # Check for seller info in metadata
                if 'seller' in metadata and metadata['seller']:
                    seller_info['name'] = metadata['seller']
                    
                # Check for rating in metadata
                if 'rating' in metadata and metadata['rating'] is not None:
                    try:
                        seller_info['rating'] = float(metadata['rating'])
                    except (ValueError, TypeError):
                        pass
                        
                # Check for reviews in metadata
                if 'review_count' in metadata and metadata['review_count'] is not None:
                    try:
                        seller_info['reviews'] = int(metadata['review_count'])
                    except (ValueError, TypeError):
                        pass
                        
                # Add all other metadata as deal_metadata
                if "deal_metadata" not in deal_data:
                    deal_data['deal_metadata'] = {}
                deal_data['deal_metadata'].update(metadata)
        except Exception as e:
            logger.warning(f"Error processing seller info: {str(e)}, using defaults")
            # Keep using the default seller_info
        
        # Always add seller_info, even if only defaults
        deal_data['seller_info'] = seller_info
        
        # Create deal using repository
        logger.info(f"Creating deal from product: {deal_data['title']} with category: {deal_data['category']}")
        deal = await self._repository.create(deal_data)
        
        # Cache deal
        await self._cache_deal(deal)
        
        return deal
        
    except Exception as e:
        logger.error(f"Error creating deal from product: {str(e)}")
        return None

async def create_deal_from_dict(self, deal_data: Dict[str, Any]) -> Optional[Deal]:
    """Create a deal from a dictionary.
    
    Args:
        deal_data: Dictionary containing deal data
        
    Returns:
        Created Deal or None if creation failed
    """
    try:
        # Validate required fields
        required_fields = ["title", "price", "market_id"]
        for field in required_fields:
            if field not in deal_data or deal_data[field] is None:
                if field == "title":
                    logger.warning(f"Missing required field '{field}', setting default value")
                    deal_data[field] = "Untitled Deal"
                elif field == "price":
                    logger.warning(f"Missing required field '{field}', setting default value")
                    deal_data[field] = 0.0
                else:
                    logger.warning(f"Missing required field '{field}', but continuing with attempt")
        
        # Ensure we have deal_metadata
        if "deal_metadata" not in deal_data or not deal_data["deal_metadata"]:
            deal_data["deal_metadata"] = {}
            
        # Extract or generate external_id from deal_metadata
        external_id = None
        if "external_id" in deal_data:
            external_id = deal_data["external_id"]
            # Also ensure it's in deal_metadata
            if "deal_metadata" in deal_data and isinstance(deal_data["deal_metadata"], dict):
                deal_data["deal_metadata"]["external_id"] = external_id
        elif deal_data["deal_metadata"] and "external_id" in deal_data["deal_metadata"]:
            external_id = deal_data["deal_metadata"]["external_id"]
        else:
            # Generate a new UUID for external_id
            from uuid import uuid4
            external_id = str(uuid4())
            # Update deal_metadata with the new external_id
            deal_data["deal_metadata"]["external_id"] = external_id
            logger.info(f"Generated new external_id for deal: {external_id}")
        
        # Ensure source is valid
        from core.models.enums import DealSource
        valid_sources = [source_enum.value for source_enum in DealSource]
        source = deal_data.get("source", "api")
        
        # If source is invalid, try to determine from market or URL
        if source not in valid_sources:
            # Try to derive from market_id
            market_id = deal_data.get("market_id")
            if market_id:
                try:
                    from core.models.market import Market
                    from sqlalchemy import select
                    
                    market_query = select(Market).where(Market.id == market_id)
                    market_result = await self.db.execute(market_query)
                    market = market_result.scalar_one_or_none()
                    
                    if market and hasattr(market, 'type') and market.type:
                        market_type = market.type.lower()
                        if market_type in [s.lower() for s in valid_sources]:
                            source = market_type
                        else:
                            source = "scraper"
                except Exception as e:
                    logger.warning(f"Error getting market info: {str(e)}")
                    source = "api"  # Default if we can't determine
            
            # If still invalid, try URL
            if source not in valid_sources:
                url = deal_data.get("url", "")
                if url:
                    if "amazon" in url.lower():
                        source = "amazon"
                    elif "walmart" in url.lower():
                        source = "walmart"
                    elif "ebay" in url.lower():
                        source = "ebay"
                    elif "google" in url.lower():
                        source = "google_shopping"  # Ensure underscore format
                    else:
                        source = "api"  # Default to API if no valid source can be determined
                else:
                    source = "api"
                    
            logger.info(f"Adjusted invalid source to: {source}")
            deal_data["source"] = source
        
        # Ensure Google Shopping always uses underscore format
        if source == "google shopping":
            source = "google_shopping"
            logger.info("Normalized 'google shopping' to 'google_shopping'")
        
        # Prepare defaults for get_or_create_deal
        market_id = deal_data.get("market_id")
        defaults = {
            "title": deal_data.get("title", "Untitled Deal"),
            "description": deal_data.get("description", ""),
            "price": deal_data.get("price", 0),
            "original_price": deal_data.get("original_price"),
            "url": deal_data.get("url", ""),
            "image_url": deal_data.get("image_url", ""),
            "category": deal_data.get("category", "other"),
            "status": deal_data.get("status", "active"),
            "source": source,
            "deal_metadata": deal_data.get("deal_metadata", {})
        }
        
        # Ensure deal_metadata contains external_id
        if external_id and "external_id" not in defaults["deal_metadata"]:
            defaults["deal_metadata"]["external_id"] = external_id
            
        # Log the attempt to create or get a deal
        logger.debug(f"Attempting to get_or_create_deal with external_id={external_id}, market_id={market_id}")
        
        # Create or get the deal - properly await the async operation
        deal, created = await self.get_or_create_deal(
            external_id=external_id,
            market_id=market_id,
            defaults=defaults
        )
        
        if created:
            logger.info(f"Created new deal with external_id {external_id} and id {deal.id}")
        else:
            logger.info(f"Found existing deal with external_id {external_id} and id {deal.id}")
            
        return deal
    except Exception as e:
        logger.error(f"Error creating deal from dict: {str(e)}")
        return None
        
async def get_or_create_deal(
    self, 
    external_id: str, 
    market_id: Optional[UUID], 
    defaults: Dict[str, Any]
) -> Tuple[Deal, bool]:
    """Get or create a deal with the given external_id.
    
    Args:
        external_id: External ID to look up
        market_id: Optional market ID to filter by
        defaults: Default values for deal creation
        
    Returns:
        Tuple of (deal, created) where created is True if a new deal was created
    """
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession
    from core.models.deal import Deal
    from core.models.market import Market
    from uuid import uuid4

    logger.debug(f"Looking for deal with external_id={external_id}, market_id={market_id}")
    
    try:
        # First, try to find an existing deal with this external_id
        query = select(Deal).where(Deal.deal_metadata['external_id'].astext == external_id)
        
        # Add market_id condition if provided
        if market_id:
            query = query.where(Deal.market_id == market_id)
            
        # Execute the query
        result = await self.db.execute(query)
        existing_deal = result.scalar_one_or_none()
        
        if existing_deal:
            logger.debug(f"Found existing deal: {existing_deal.id}")
            return existing_deal, False
            
        # No existing deal found with this external_id, create a new one
        # Validate source value
        source = defaults.get("source", "api")
        from core.models.enums import DealSource
        valid_sources = [source_enum.value for source_enum in DealSource]
        
        if source not in valid_sources:
            # Try to derive source from market_id
            if market_id:
                try:
                    market_query = select(Market).where(Market.id == market_id)
                    market_result = await self.db.execute(market_query)
                    market = market_result.scalar_one_or_none()
                    if market and market.type:
                        # Try to map market type to source
                        if market.type.lower() in [s.lower() for s in valid_sources]:
                            source = market.type.lower()
                        else:
                            source = "scraper"  # Default to scraper for unknown market types
                except Exception as e:
                    logger.warning(f"Error getting market info for source derivation: {str(e)}")
                    source = "scraper"  # Default to scraper if market lookup fails
            else:
                # Try to derive source from URL
                url = defaults.get("url", "")
                if "amazon" in url.lower():
                    source = "amazon"
                elif "walmart" in url.lower():
                    source = "walmart"
                elif "ebay" in url.lower():
                    source = "ebay"
                elif "google" in url.lower():
                    source = "google_shopping"  # Ensure underscore format
                else:
                    source = "api"  # Default to API if no valid source can be determined
            
            logger.warning(f"Invalid source '{defaults.get('source', 'None')}' provided, using derived source '{source}'")
        
        # Ensure Google Shopping always uses underscore format
        if source == "google shopping":
            source = "google_shopping"
            logger.info("Normalized 'google shopping' to 'google_shopping'")
        
        # Ensure deal_metadata is initialized with external_id
        deal_metadata = defaults.get("deal_metadata", {}) or {}
        deal_metadata["external_id"] = external_id
        
        # Create a new Deal object
        new_deal = Deal(
            id=uuid4(),
            title=defaults.get("title", ""),
            description=defaults.get("description", ""),
            price=defaults.get("price", 0.0),
            currency=defaults.get("currency", "USD"),
            original_price=defaults.get("original_price"),
            market_id=market_id,
            url=defaults.get("url", ""),
            image_url=defaults.get("image_url", ""),
            category=defaults.get("category", "other"),
            status=defaults.get("status", "active"),
            source=source,
            deal_metadata=deal_metadata
        )
        
        # Add to the session and flush to get the ID
        self.db.add(new_deal)
        await self.db.flush()
        
        # Refresh to get the complete object with all attributes
        await self.db.refresh(new_deal)
        
        logger.debug(f"Created new deal: {new_deal.id}")
        return new_deal, True
        
    except Exception as e:
        logger.error(f"Error in get_or_create_deal: {str(e)}")
        
        # Create a fallback deal with minimal information if the main process fails
        try:
            # Initialize fallback metadata with external_id
            fallback_metadata = {
                "external_id": external_id
            }
            
            # Validate source for fallback deal
            fallback_source = defaults.get("source", "scraper")
            if fallback_source not in valid_sources:
                logger.warning(f"Invalid source for fallback deal, using 'api' or 'scraper'")
                fallback_source = "api" if "api" in valid_sources else "scraper"
            
            # Create a minimal Deal object
            fallback_deal = Deal(
                id=uuid4(),
                title=defaults.get("title", "Unknown Deal"),
                description=defaults.get("description", ""),
                price=float(defaults.get("price", 0)),
                market_id=market_id,
                url=defaults.get("url", ""),
                image_url=defaults.get("image_url", ""),
                category=defaults.get("category", "other"),
                status="active",
                source=fallback_source,
                deal_metadata=fallback_metadata
            )
            
            # Add to session and return
            self.db.add(fallback_deal)
            await self.db.flush()
            await self.db.refresh(fallback_deal)
            
            logger.warning(f"Created fallback deal: {fallback_deal.id}")
            return fallback_deal, True
            
        except Exception as fallback_error:
            logger.error(f"Failed to create fallback deal: {str(fallback_error)}")
            raise e  # Re-raise the original exception if fallback fails 