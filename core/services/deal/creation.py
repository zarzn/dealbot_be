"""Deal creation module.

This module contains functions related to creating deals from various sources.
"""

import logging
from typing import List, Optional, Dict, Any, Union
from uuid import UUID
from decimal import Decimal, InvalidOperation
from datetime import datetime
from sqlalchemy import select, and_

from core.models.deal import Deal, DealStatus
from core.exceptions import InvalidDealDataError

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
    """Create a deal from scraped data.
    
    Args:
        deal_data: Dictionary containing deal data from scraping
        
    Returns:
        Created Deal object or None if creation failed
    """
    try:
        # Check if a deal with this URL already exists
        existing_deal_query = select(Deal).where(Deal.url == deal_data['url'])
        existing_result = await self.db.execute(existing_deal_query)
        existing_deal = existing_result.scalar_one_or_none()
        
        if existing_deal:
            logger.info(f"Deal with URL {deal_data['url']} already exists, skipping creation")
            return existing_deal
            
        # Use system admin user ID if no user ID is provided
        if not deal_data.get('user_id'):
            # Get system admin user ID from settings
            from core.config import settings
            system_user_id = settings.SYSTEM_USER_ID
            deal_data['user_id'] = UUID(system_user_id)
            logger.info(f"No user ID provided, using system admin user ID: {system_user_id}")

        # Ensure seller_info contains rating and reviews if available
        if 'seller_info' not in deal_data:
            deal_data['seller_info'] = {}
        
        # If seller_info doesn't have a rating but the product has one, use that
        if 'seller_info' in deal_data and (
            'rating' not in deal_data['seller_info'] or 
            not deal_data['seller_info']['rating']
        ):
            # Check for rating in deal_metadata
            if 'deal_metadata' in deal_data and deal_data['deal_metadata']:
                if 'rating' in deal_data['deal_metadata']:
                    try:
                        rating = deal_data['deal_metadata']['rating']
                        # Convert string ratings to float
                        if isinstance(rating, str):
                            rating = float(rating)
                        deal_data['seller_info']['rating'] = rating
                        logger.info(f"Using rating from deal_metadata: {rating}")
                    except (ValueError, TypeError):
                        logger.warning(f"Failed to parse rating from deal_metadata: {deal_data['deal_metadata'].get('rating')}")
            # Check for rating directly in deal_data
            elif 'rating' in deal_data:
                try:
                    rating = deal_data['rating']
                    if isinstance(rating, str):
                        rating = float(rating)
                    deal_data['seller_info']['rating'] = rating
                    logger.info(f"Using rating from deal_data: {rating}")
                except (ValueError, TypeError):
                    logger.warning(f"Failed to parse rating from deal_data: {deal_data.get('rating')}")
        
        # Similar for reviews count
        if 'seller_info' in deal_data and (
            'reviews' not in deal_data['seller_info'] or 
            not deal_data['seller_info'].get('reviews')
        ):
            # Check for review_count in deal_metadata
            if 'deal_metadata' in deal_data and deal_data['deal_metadata']:
                if 'review_count' in deal_data['deal_metadata']:
                    try:
                        reviews = deal_data['deal_metadata']['review_count']
                        # Convert string to int
                        if isinstance(reviews, str):
                            reviews = int(reviews)
                        deal_data['seller_info']['reviews'] = reviews
                        logger.info(f"Using reviews from deal_metadata: {reviews}")
                    except (ValueError, TypeError):
                        logger.warning(f"Failed to parse reviews from deal_metadata: {deal_data['deal_metadata'].get('review_count')}")
            # Check for reviews directly in deal_data
            elif 'review_count' in deal_data:
                try:
                    reviews = deal_data['review_count']
                    if isinstance(reviews, str):
                        reviews = int(reviews)
                    deal_data['seller_info']['reviews'] = reviews
                    logger.info(f"Using reviews from deal_data: {reviews}")
                except (ValueError, TypeError):
                    logger.warning(f"Failed to parse reviews from deal_data: {deal_data.get('review_count')}")
            
        # Validate and fix price to ensure it's positive (meets ch_positive_price constraint)
        if 'price' in deal_data:
            # Convert to Decimal if it's not already
            if not isinstance(deal_data['price'], Decimal):
                try:
                    deal_data['price'] = Decimal(str(deal_data['price']))
                except (ValueError, TypeError, InvalidOperation):
                    logger.warning(f"Invalid price value: {deal_data['price']}, setting to minimum price")
                    deal_data['price'] = Decimal('0.01')

            # Ensure price is positive (satisfies ch_positive_price constraint)
            if deal_data['price'] <= Decimal('0'):
                logger.warning(f"Price {deal_data['price']} is not positive, setting to minimum price")
                deal_data['price'] = Decimal('0.01')  # Set minimum valid price
        else:
            # If no price is provided, set a default minimum price
            deal_data['price'] = Decimal('0.01')
            logger.warning("No price provided for deal, setting to minimum price")

        # Create new deal
        logger.info(f"Creating new deal from scraped data: {deal_data['title']}")
        logger.info(f"Description available: {bool(deal_data.get('description'))}")
        if deal_data.get('description'):
            logger.info(f"Description length: {len(deal_data['description'])}")
            logger.info(f"Description preview: {deal_data['description'][:100]}")
        else:
            logger.warning("No description available for scraped deal")
            
        new_deal = Deal(
            user_id=deal_data['user_id'],
            market_id=deal_data['market_id'],
            title=deal_data['title'],
            description=deal_data.get('description', ''),
            url=deal_data['url'],
            price=deal_data['price'],
            original_price=deal_data.get('original_price'),
            currency=deal_data['currency'],
            source=deal_data['source'],
            image_url=deal_data.get('image_url'),
            category=deal_data['category'],
            seller_info=deal_data.get('seller_info'),
            deal_metadata=deal_data.get('deal_metadata'),
            found_at=datetime.utcnow(),
            status=DealStatus.ACTIVE
        )
        
        self.db.add(new_deal)
        await self.db.commit()
        await self.db.refresh(new_deal)
        
        logger.info(f"Created new deal from scraped data: {new_deal.id}")
        return new_deal
        
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
            # Use generic name based on ID
            market_name = f"Market {deal.market_id.hex[:8]}"
            
        # Check if deal is tracked by user - carefully to avoid lazy loading
        is_tracked = False
        # Only attempt this if tracked_by_users was eagerly loaded
        if user_id and hasattr(deal, '_sa_instance_state'):
            try:
                # Check if tracked_by_users is already loaded
                if hasattr(deal._sa_instance_state, 'loaded_attributes') and 'tracked_by_users' in deal._sa_instance_state.loaded_attributes:
                    tracking_entries = [t for t in deal.tracked_by_users if t.user_id == user_id]
                    is_tracked = len(tracking_entries) > 0
                    logger.debug(f"Deal tracking status for user {user_id}: {is_tracked}")
            except Exception as e:
                logger.warning(f"Error checking tracking status: {str(e)}")
        
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
            "availability": {"in_stock": True},  # Default availability
            "created_at": deal.created_at.isoformat() if hasattr(deal, "created_at") and deal.created_at else datetime.utcnow().isoformat(),
            "updated_at": deal.updated_at.isoformat() if hasattr(deal, "updated_at") and deal.updated_at else datetime.utcnow().isoformat()
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
        
        # Add the score to the main response body for easier access
        if ai_analysis and 'score' in ai_analysis:
            response['score'] = ai_analysis['score']
            logger.debug(f"Added AI score to response: {ai_analysis['score']}")
        
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