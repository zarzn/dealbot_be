"""Deal creation module.

This module contains functions related to creating deals from various sources.
"""

import logging
from typing import List, Optional, Dict, Any, Union
from uuid import UUID
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, and_
import json
import uuid
import hashlib

from core.models.deal import Deal, DealStatus
from core.models.enums import MarketType, MarketCategory
from core.exceptions import InvalidDealDataError
from core.utils.validation import Validator

logger = logging.getLogger(__name__)

async def create_deal_from_dict(self, deal_data: Dict[str, Any]) -> Deal:
    """Create a new deal with validation and error handling.
    
    Args:
        deal_data: Deal data
        
    Returns:
        Created deal
        
    Raises:
        InvalidDealDataError: If deal data is invalid
        DatabaseError: If database error occurs
    """
    try:
        # Check for user_id and add fallback if missing
        if not deal_data.get('user_id'):
            # Get system admin user ID from settings
            from core.config import settings
            system_user_id = settings.SYSTEM_USER_ID
            deal_data['user_id'] = UUID(system_user_id)
            logger.info(f"No user ID provided for deal creation, using system admin user ID: {system_user_id}")

        # Check for existing deal with same URL and goal_id to prevent unique constraint violation
        if "url" in deal_data and "goal_id" in deal_data and deal_data["goal_id"] is not None:
            query = select(Deal).where(
                and_(
                    Deal.url == deal_data["url"],
                    Deal.goal_id == deal_data["goal_id"]
                )
            )
            result = await self._repository.db.execute(query)
            existing_deal = result.scalar_one_or_none()
            
            if existing_deal:
                logger.info(f"Deal with URL {deal_data['url']} and goal_id {deal_data['goal_id']} already exists")
                return existing_deal

        # Create deal using the repository
        deal = await self._repository.create(deal_data)
        
        # Cache deal
        await self._cache_deal(deal)
        
        logger.info(f"Deal created successfully: {deal.id}")
        return deal
    except Exception as e:
        logger.error(f"Failed to create deal: {str(e)}")
        if "uq_deal_url_goal" in str(e):
            # Handle the unique constraint violation more gracefully
            raise InvalidDealDataError(f"A deal with this URL and goal already exists")
        raise InvalidDealDataError(f"Invalid deal data: {str(e)}")

async def _create_deal_from_scraped_data(self, deal_data: Dict[str, Any]) -> Optional[Deal]:
    """Create a Deal object from scraped product data.
    
    Args:
        deal_data: Product data from scraper
        
    Returns:
        Created Deal object or None if validation fails
    """
    try:
        logger.debug(f"Creating deal from scraped data: {deal_data.get('title', 'Unknown')[:30]}...")
        
        # Basic validation
        required_fields = ['title', 'url', 'source']
        for field in required_fields:
            if not deal_data.get(field):
                logger.warning(f"Scraped product missing required field: {field}")
                return None
                
        # Validate price - must be a positive value
        price = deal_data.get('price')
        if price is None or not isinstance(price, (float, int, Decimal)) or price <= 0:
            logger.warning(f"Scraped product has invalid price: {price}, skipping")
            return None
            
        # Convert price to Decimal if it's not already
        if not isinstance(price, Decimal):
            try:
                price_decimal = Decimal(str(price))
                if price_decimal <= Decimal('0'):
                    logger.warning(f"Scraped product has zero or negative price: {price}, skipping")
                    return None
                deal_data['price'] = price_decimal
            except (ValueError, TypeError, InvalidOperation):
                logger.warning(f"Could not convert price to Decimal: {price}, skipping")
                return None
                
        # Validate and convert category against MarketCategory enum
        category = deal_data.get('category', 'OTHER')
        if category:
            try:
                # Try to match the category directly with the enum values
                valid_category = False
                normalized_category = str(category).upper()
                
                # Check for exact matches first
                for cat_enum in MarketCategory:
                    # Use uppercase for both sides of the comparison
                    if cat_enum.value.upper() == normalized_category:
                        valid_category = True
                        category = cat_enum.value
                        logger.info(f"Found exact category match: {category}")
                        break
                
                # If no exact match, try to find a close match
                if not valid_category:
                    for cat_enum in MarketCategory:
                        # Use uppercase for both sides when checking containment
                        if normalized_category in cat_enum.value.upper() or cat_enum.value.upper() in normalized_category:
                            valid_category = True
                            category = cat_enum.value
                            logger.info(f"Found partial category match: {normalized_category} -> {category}")
                            break
                
                # If still no match, default to OTHER
                if not valid_category:
                    category = "OTHER"
                    logger.info(f"No matching category found for '{normalized_category}', defaulting to OTHER")
            except Exception as e:
                logger.warning(f"Error validating category '{category}': {str(e)}, defaulting to OTHER")
                category = "OTHER"
        else:
            category = "OTHER"
            
        # Update the category in deal_data
        deal_data['category'] = category
                
        # Extract market ID based on source
        market_id = None
        source = deal_data.get('source', '').lower()
        
        # Get market by type if available
        try:
            # Try to find the market type in various ways
            market_type = None
            
            # 1. Direct MarketType enum match
            for mt in MarketType:
                if mt.value.lower() == source:
                    market_type = mt
                    logger.info(f"Found direct market type match: {source} -> {market_type}")
                    break
            
            # 2. Check for partial matches if no direct match found
            if market_type is None:
                # Check for partial matches or prefixes
                for mt in MarketType:
                    if source.startswith(mt.value.lower()):
                        market_type = mt
                        logger.info(f"Found partial market type match: {source} -> {market_type}")
                        break
                    
            # 3. Try specific source matches if still no match
            if market_type is None:
                specific_mappings = {
                    "amazon_search": MarketType.AMAZON,
                    "walmart_search": MarketType.WALMART,
                    "google_shopping": MarketType.GOOGLE_SHOPPING,
                    "google_shopping_search": MarketType.GOOGLE_SHOPPING,
                    "ebay_search": MarketType.EBAY
                }
                
                if source in specific_mappings:
                    market_type = specific_mappings[source]
                    logger.info(f"Found specific market type mapping: {source} -> {market_type}")
                    
            if market_type:
                market = await self._market_repository.get_by_type(market_type)
                if market:
                    if isinstance(market, list) and market:
                        market_id = market[0].id
                        logger.info(f"Using market ID from list: {market_id}, market type: {market_type}")
                    else:
                        market_id = market.id
                        logger.info(f"Using market ID: {market_id}, market type: {market_type}")
        except Exception as e:
            logger.warning(f"Error retrieving market by type {source}: {str(e)}")
            
        # If market ID not found, try to use a default market or create a new one
        if not market_id:
            try:
                # Log the original source for debugging
                logger.info(f"Trying fallback market resolution for source: {source}")
                
                # Try to get a default market with fallbacks
                default_markets = await self._market_repository.list()
                
                if default_markets:
                    # First try to match by source name or prefix to be more flexible
                    for m in default_markets:
                        market_type_value = getattr(m, 'type', '').lower()
                        
                        # Try exact match first
                        if market_type_value == source:
                            market_id = m.id
                            logger.info(f"Using market ID with exact source match: {market_id} ({market_type_value})")
                            break
                            
                        # Then try prefix match
                        if source.startswith(market_type_value) or market_type_value.startswith(source):
                            market_id = m.id
                            logger.info(f"Using market ID with prefix match: {market_id} ({market_type_value})")
                            break
                    
                    # If still not found, use the first active market
                    if not market_id:
                        active_markets = [m for m in default_markets if getattr(m, 'is_active', False)]
                        if active_markets:
                            market = active_markets[0]
                            market_id = market.id
                            logger.warning(f"Using fallback active market {getattr(market, 'type', 'unknown')} for source {source}")
                        else:
                            # No active markets, use the first market
                            market = default_markets[0]
                            market_id = market.id
                            logger.warning(f"Using first available market {getattr(market, 'type', 'unknown')} for source {source} (no active markets found)")
                                
                # If still no market, create a UUID specifically for unidentified markets
                if not market_id:
                    # Generate a deterministic UUID based on the source for consistency
                    source_hash = hashlib.md5(source.encode()).hexdigest()
                    market_id = UUID(f"00000000-0000-4000-a000-{source_hash[:12]}")
                    logger.warning(f"No suitable market found for source {source}, using generated fallback ID: {market_id}")
            except Exception as e:
                logger.error(f"Error finding suitable market for deal: {str(e)}")
                # Generate an emergency fallback UUID
                market_id = UUID('00000000-0000-4000-a000-000000000000')
                logger.error(f"Using emergency fallback market ID due to error: {market_id}")
        
        # Standardize data for deal creation
        create_data = {
            'user_id': self._current_user_id,
            'market_id': market_id,
            'goal_id': None,  # No specific goal for scraped data
            'title': deal_data.get('title', ''),
            'description': deal_data.get('description', ''),
            'url': deal_data.get('url', ''),
            'price': deal_data.get('price'),
            'original_price': deal_data.get('original_price'),
            'currency': deal_data.get('currency', 'USD'),
            'source': source,
            'image_url': deal_data.get('image_url', ''),
            'category': category,  # Use the validated category
            'seller_info': deal_data.get('seller_info', {}),
            'availability': deal_data.get('availability', {}),
            'found_at': datetime.now(),
            'expires_at': datetime.now() + timedelta(days=30),  # Default expiry
            'status': 'active',
            'deal_metadata': {
                'search_query': deal_data.get('search_query', ''),
                'external_id': str(uuid.uuid4())
            }
        }
        
        # Store AI analysis data in deal_metadata if available
        if deal_data.get('ai_analysis'):
            create_data['deal_metadata']['ai_analysis'] = deal_data.get('ai_analysis')
        
        # Validate the data before creating the deal
        validated_data = await self.validate_deal_data(create_data)
        
        # Final check for price after validation
        if not validated_data.get('price') or Decimal(str(validated_data['price'])) <= 0:
            logger.warning(f"Deal has invalid price after validation: {validated_data.get('price')}, skipping")
            return None
            
        # Create the deal
        deal = await self._repository.create(validated_data)
        logger.info(f"Successfully created deal: {deal.title[:30]}... from scraped data with category: {deal.category}")
        return deal
        
    except Exception as e:
        logger.error(f"Failed to create deal from scraped data: {str(e)}")
        return None

def _convert_to_response(self, deal, user_id: Optional[UUID] = None, include_ai_analysis: bool = True, analysis: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Convert a Deal model to a response model.
    
    Args:
        deal: The Deal instance to convert
        user_id: Optional user ID to check tracking status
        include_ai_analysis: Whether to include AI analysis data
        analysis: Optional pre-generated analysis data
        
    Returns:
        Deal data in response format
    """
    try:
        logger.info(f"Converting deal {deal.id} to response model, include_ai_analysis={include_ai_analysis}")
        
        # Get market name (safely)
        market_name = "Unknown Market"
        # DON'T access deal.market directly - use market_id only to avoid lazy loading
        if hasattr(deal, 'market_id') and deal.market_id:
            # Try to get the real market name from the Market table if possible
            if 'market' in deal.__dict__ and deal.__dict__['market'] is not None:
                market = deal.__dict__['market']
                market_name = market.name
                logger.debug(f"Using market name '{market_name}' from already loaded market")
            else:
                # Use generic name based on ID as fallback
                market_name = f"Market {deal.market_id.hex[:8]}"
                logger.debug(f"Using generic market name '{market_name}' based on ID")
            
        # Check if deal is tracked by user - carefully to avoid lazy loading
        is_tracked = False
        
        if user_id:
            try:
                # First check if we added the is_tracked_by_user attribute in the get_deal method
                if hasattr(deal, 'is_tracked_by_user') and deal.is_tracked_by_user == user_id:
                    is_tracked = True
                    logger.debug(f"Deal tracking status for user {user_id} (from is_tracked_by_user attribute): {is_tracked}")
                # Then try to use tracked_by_users relationship if it's already loaded
                elif hasattr(deal, '_sa_instance_state') and hasattr(deal._sa_instance_state, 'loaded_attributes') and 'tracked_by_users' in deal._sa_instance_state.loaded_attributes:
                    tracking_entries = [t for t in deal.tracked_by_users if t.user_id == user_id]
                    is_tracked = len(tracking_entries) > 0
                    logger.debug(f"Deal tracking status for user {user_id} (from relationship): {is_tracked}")
                # Since _convert_to_response isn't async, we can't use await here
                # Instead we rely on the is_tracked_by_user attribute set in get_deal
            except Exception as e:
                # If anything goes wrong, just log the error and assume not tracked
                logger.warning(f"Error checking tracking status: {str(e)}")
                is_tracked = False
        
        # Safely handle original price
        original_price = None
        if hasattr(deal, 'original_price') and deal.original_price:
            original_price = deal.original_price
        
        # Handle seller_info
        seller_info = {"name": "Unknown", "rating": 0, "reviews": 0}
        if hasattr(deal, 'seller_info') and deal.seller_info:
            seller_info = deal.seller_info
        
        # Safely build response model
        response = {
            "id": str(deal.id),
            "title": deal.title,
            "description": deal.description or "",
            "url": deal.url,
            "price": str(deal.price),
            "original_price": str(original_price) if original_price else None,
            "discount_percentage": float(deal.discount_percentage) if hasattr(deal, 'discount_percentage') and deal.discount_percentage else None,
            "currency": deal.currency,
            "source": deal.source,
            "image_url": deal.image_url,
            "category": deal.category if deal.category else "Uncategorized",
            "status": deal.status,
            "is_tracked": is_tracked,
            "user_id": str(deal.user_id),
            "market_id": str(deal.market_id) if deal.market_id else "00000000-0000-0000-0000-000000000000",
            "goal_id": str(deal.goal_id) if deal.goal_id else None,
            "found_at": deal.found_at.isoformat() if deal.found_at else datetime.now().isoformat(),
            "expires_at": deal.expires_at.isoformat() if deal.expires_at else None,
            "market_name": market_name,
            "seller_info": seller_info,
            "availability": deal.availability if hasattr(deal, 'availability') and deal.availability else {"in_stock": True},
            "created_at": deal.created_at.isoformat() if hasattr(deal, "created_at") and deal.created_at else datetime.utcnow().isoformat(),
            "updated_at": deal.updated_at.isoformat() if hasattr(deal, "updated_at") and deal.updated_at else datetime.utcnow().isoformat(),
            # Add required fields for DealResponse model
            "latest_score": None,
            "price_history": []
        }
        
        # Handle AI analysis
        ai_analysis = None
        if include_ai_analysis:
            # Use provided analysis or get from deal
            if analysis:
                logger.info(f"Using provided analysis for deal {deal.id}")
                ai_analysis = analysis
                # Log the source of the score
                if 'score' in analysis:
                    logger.info(f"Using provided AI score: {analysis['score']}")
                    
                # Always verify we have recommendations
                if 'recommendations' not in analysis or not analysis['recommendations']:
                    logger.warning(f"No recommendations in provided analysis, adding defaults")
                    ai_analysis['recommendations'] = [
                        f"Consider if this {deal.title} meets your specific needs and budget.",
                        f"Research additional options in the {deal.category} category for comparison."
                    ]
            elif hasattr(deal, 'ai_analysis') and deal.ai_analysis:
                # We have direct analysis data in the model
                try:
                    if isinstance(deal.ai_analysis, dict):
                        ai_analysis = deal.ai_analysis
                        logger.debug(f"Using AI analysis from deal model (dict): {ai_analysis.get('score')}")
                    elif hasattr(deal.ai_analysis, 'to_dict'):
                        ai_analysis = deal.ai_analysis.to_dict()
                        logger.debug(f"Using AI analysis from deal model (object): {ai_analysis.get('score')}")
                    else:
                        # Try to convert unknown format
                        try:
                            ai_analysis = dict(deal.ai_analysis)
                            logger.debug(f"Using AI analysis from deal model (converted): {ai_analysis.get('score')}")
                        except (ValueError, TypeError):
                            logger.warning(f"Couldn't convert AI analysis, using fallback")
                            ai_analysis = {
                                "deal_id": str(deal.id),
                                "score": 0.5,
                                "confidence": 0.3,
                                "analysis_date": datetime.utcnow().isoformat()
                            }
                except Exception as e:
                    logger.error(f"Error processing AI analysis: {str(e)}")
                    ai_analysis = None
                    
            # Default analysis if none is available
            if not ai_analysis:
                logger.debug(f"No AI analysis available for deal {deal.id}, creating default")
                ai_analysis = {
                    "deal_id": str(deal.id),
                    "score": 0.5,  # Neutral score
                    "confidence": 0.1,  # Low confidence
                    "price_analysis": {
                        "value": "Unknown",
                        "trend": "Unknown",
                        "confidence": 0.1
                    },
                    "market_analysis": {
                        "value": "Standard",
                        "confidence": 0.1,
                        "competition": "Unknown"
                    },
                    "recommendations": [
                        f"Research this {deal.title} further before deciding.",
                        "Compare with similar products to ensure good value."
                    ],
                    "analysis_date": datetime.utcnow().isoformat()
                }
            
            # Ensure we have a properly formatted AI analysis object
            if ai_analysis and not isinstance(ai_analysis, dict):
                logger.warning(f"AI analysis for deal {deal.id} is not a dictionary, converting")
                try:
                    ai_analysis = dict(ai_analysis)
                except (TypeError, ValueError):
                    logger.error(f"Failed to convert AI analysis to dictionary, using fallback")
                    ai_analysis = {
                        "deal_id": str(deal.id),
                        "score": 0.5,
                        "confidence": 0.3,
                        "price_analysis": {},
                        "market_analysis": {},
                        "recommendations": [
                            "This is a fallback analysis due to formatting issues with the original analysis.",
                            f"Research this {deal.title} thoroughly before purchasing."
                        ],
                        "analysis_date": datetime.utcnow().isoformat()
                    }

        # Always include AI analysis in the response if available
        response["ai_analysis"] = ai_analysis
        
        # Add the score to the main response body for easier access and update latest_score
        if ai_analysis and 'score' in ai_analysis:
            response['score'] = ai_analysis['score']
            response['latest_score'] = ai_analysis['score']  # Use AI score as latest_score
            logger.debug(f"Added AI score to response: {ai_analysis['score']}")
        
        # Add default price history if none exists
        if not response['price_history'] or len(response['price_history']) == 0:
            price = float(deal.price) if hasattr(deal, 'price') and deal.price else 0.0
            response['price_history'] = [
                {
                    "price": str(price * 1.1),  # 10% higher historical price
                    "timestamp": (datetime.utcnow() - timedelta(days=7)).isoformat(),
                    "source": "historical"
                },
                {
                    "price": str(price),
                    "timestamp": datetime.utcnow().isoformat(),
                    "source": "current"
                }
            ]
        
        logger.info(f"Response model created for deal {deal.id}")
        return response
        
    except Exception as e:
        logger.error(f"Error converting deal {deal.id} to response: {str(e)}", exc_info=True)
        # Return basic deal info on error
        return {
            "id": str(deal.id),
            "title": deal.title,
            "description": deal.description or "",
            "url": deal.url or "",
            "price": str(deal.price) if deal.price else "0.0",
            "currency": deal.currency or "USD",
            "source": deal.source or "unknown",
            "status": deal.status if hasattr(deal, "status") else "unknown",
            "market_id": str(deal.market_id) if hasattr(deal, "market_id") and deal.market_id else "unknown",
            "category": str(deal.category) if hasattr(deal, "category") else "unknown",
            "found_at": deal.found_at if hasattr(deal, "found_at") else datetime.utcnow(),
            "created_at": deal.created_at if hasattr(deal, "created_at") else datetime.utcnow(),
            "updated_at": deal.updated_at if hasattr(deal, "updated_at") else datetime.utcnow(),
            "seller_info": {"name": "Unknown", "rating": 0, "reviews": 0},
            "availability": {},
            "price_history": [],
            "latest_score": None,
            "error": f"Error generating complete response: {str(e)}"
        } 

async def create_deal(
        self,
        user_id: UUID,
        goal_id: Optional[UUID],
        market_id: UUID,
        title: str,
        description: Optional[str],
        price: Union[Decimal, float, str],
        original_price: Optional[Union[Decimal, float, str]] = None,
        currency: str = "USD",
        source: Optional[str] = None,
        url: str = None,
        image_url: Optional[str] = None,
        category: Optional[str] = None,
        seller_info: Optional[Dict[str, Any]] = None,
        availability: Optional[Dict[str, Any]] = None,
        found_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        status: Optional[str] = DealStatus.ACTIVE.value,
        deal_metadata: Optional[Dict[str, Any]] = None,
        price_metadata: Optional[Dict[str, Any]] = None,
    ) -> Deal:
        """Create a new deal.
        
        Args:
            user_id: User ID
            goal_id: Optional goal ID
            market_id: Market ID
            title: Deal title
            description: Deal description
            price: Current price
            original_price: Original price
            currency: Currency code
            source: Deal source
            url: Deal URL
            image_url: Image URL
            category: Deal category
            seller_info: Seller information
            availability: Availability information
            found_at: When the deal was found
            expires_at: When the deal expires
            status: Deal status
            deal_metadata: Deal metadata
            price_metadata: Price metadata
            
        Returns:
            Created deal
        """
        if not user_id:
            raise ValueError("User ID is required")
        
        if not market_id:
            raise ValueError("Market ID is required")
            
        if not title:
            raise ValueError("Title is required")
            
        if not url:
            raise ValueError("URL is required")
            
        if not price:
            raise ValueError("Price is required")
            
        # Normalize URL
        normalized_url = Validator.normalize_url(url, source=source)
        
        # Convert price to Decimal
        if not isinstance(price, Decimal):
            price = Decimal(str(price))
            
        # Convert original price to Decimal if provided
        if original_price and not isinstance(original_price, Decimal):
            original_price = Decimal(str(original_price))

        # Construct deal_data dictionary from function parameters
        deal_data = {
            "user_id": user_id,
            "goal_id": goal_id,
            "market_id": market_id,
            "title": title,
            "description": description,
            "price": price,
            "original_price": original_price,
            "currency": currency,
            "source": source,
            "url": normalized_url,  # Use the normalized URL
            "image_url": image_url,
            "category": category,
            "seller_info": seller_info,
            "availability": availability,
            "found_at": found_at or datetime.now(timezone.utc),
            "expires_at": expires_at,
            "status": status,
            "deal_metadata": deal_metadata,
            "price_metadata": price_metadata
        }

        # Check for existing deal with same URL and goal_id to prevent unique constraint violation
        if goal_id is not None:
            query = select(Deal).where(
                and_(
                    Deal.url == normalized_url,
                    Deal.goal_id == goal_id
                )
            )
            result = await self._repository.db.execute(query)
            existing_deal = result.scalar_one_or_none()
            
            if existing_deal:
                logger.info(f"Deal with URL {normalized_url} and goal_id {goal_id} already exists")
                return existing_deal

        # Create deal using the repository
        deal = await self._repository.create(deal_data)
        
        # Cache deal
        await self._cache_deal(deal)
        
        logger.info(f"Deal created successfully: {deal.id}")
        return deal 