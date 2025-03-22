"""
Monitoring module for deals.

This module provides functionality for monitoring deals, including checking
for expired deals, refreshing data, and notifying users of changes.
"""

import logging
from typing import List, Dict, Any, Optional, Union
from uuid import UUID
from datetime import datetime

from core.models.deal import Deal, DealStatus
from core.utils.ecommerce import AmazonAPI, WalmartAPI, EcommerceAPIError
from core.utils.logger import get_logger

logger = get_logger(__name__)

async def monitor_deals(self) -> None:
    """Background task to monitor deals for changes and notify users
    
    This method runs periodically to:
    1. Check for price changes
    2. Update expired deals
    3. Refresh deal data from sources
    4. Match new deals with user goals
    """
    try:
        logger.info("Starting scheduled deal monitoring")
        
        # Get active goals from repository
        active_goals = await self._repository.get_active_goals()
        
        # Track all deals found
        all_deals = []
        
        # Fetch deals from external APIs based on goals
        try:
            amazon_deals = await self._fetch_deals_from_api(self.amazon_api, active_goals)
            walmart_deals = await self._fetch_deals_from_api(self.walmart_api, active_goals)
            all_deals = amazon_deals + walmart_deals
        except Exception as e:
            logger.error(f"Error fetching deals from API: {str(e)}")
            
            # Fallback to web scraping if APIs failed or returned no results
            if len(all_deals) == 0 and hasattr(self, 'crawler') and self.crawler:
                logger.warning("APIs failed to return results, falling back to web scraping")
                try:
                    for goal in active_goals[:5]:  # Limit to 5 goals to avoid excessive scraping
                        try:
                            category = goal.get('category', '')
                            if category:
                                scraped_deals = await self.crawler.scrape_fallback(category)
                                all_deals.extend(scraped_deals)
                                logger.info(f"Scraping found {len(scraped_deals)} deals for category {category}")
                        except Exception as e:
                            logger.error(f"Failed to scrape deals for goal {goal['id']}: {str(e)}")
                except Exception as e:
                    logger.error(f"Error during fallback scraping: {str(e)}")
        
        # Process and store all collected deals
        if all_deals:
            await self._process_and_store_deals(all_deals)
            logger.info(f"Processed and stored {len(all_deals)} deals from monitoring")
        else:
            logger.warning("No deals found during monitoring cycle")
        
        # Check for expired deals
        await self.check_expired_deals()
        
        logger.info("Scheduled deal monitoring complete")
    except Exception as e:
        logger.error(f"Error during deal monitoring: {str(e)}")

async def fetch_deals_from_api(self, api: Any, goals: List[Dict]) -> List[Dict]:
    """Fetch deals from e-commerce API based on active goals"""
    try:
        deals = []
        for goal in goals:
            params = self._build_search_params(goal)
            api_deals = await api.search_deals(params)
            deals.extend(api_deals)
        return deals
    except EcommerceAPIError as e:
        logger.error(f"Failed to fetch deals from {api.__class__.__name__}: {str(e)}")
        return []

def build_search_params(self, goal: Dict) -> Dict:
    """Build search parameters from goal constraints"""
    return {
        'keywords': goal.get('keywords', []),
        'price_range': (goal.get('min_price'), goal.get('max_price')),
        'brands': goal.get('brands', []),
        'categories': goal.get('categories', [])
    }

async def process_and_store_deals(self, deals: List[Dict]) -> None:
    """Process and store fetched deals"""
    for deal in deals:
        try:
            # Extract required fields to satisfy method parameters
            user_id = deal.get('user_id')
            goal_id = deal.get('goal_id')
            market_id = deal.get('market_id')
            title = deal.get('product_name') or deal.get('title', '')
            price = deal.get('price', 0)
            currency = deal.get('currency', 'USD')
            url = deal.get('url', '')
            
            # Call the create_deal method with all required parameters
            await self.create_deal(
                user_id=user_id,
                goal_id=goal_id,
                market_id=market_id,
                title=title,
                price=price,
                currency=currency,
                url=url,
                description=deal.get('description'),
                original_price=deal.get('original_price'),
                source=deal.get('source', 'manual'),
                image_url=deal.get('image_url'),
                expires_at=deal.get('expires_at'),
                deal_metadata=deal.get('metadata', {})
            )
        except Exception as e:
            logger.error(f"Failed to process deal: {str(e)}")

async def check_expired_deals(self) -> None:
    """Check for deals that have expired and update their status"""
    try:
        # Get current time
        now = datetime.utcnow()
        
        # Find deals that have expired but are still marked as active
        from sqlalchemy import select, and_
        
        query = select(Deal).where(
            and_(
                Deal.status == DealStatus.ACTIVE.value.lower(),
                Deal.expires_at.isnot(None),
                Deal.expires_at < now
            )
        )
        
        result = await self.db.execute(query)
        expired_deals = result.scalars().all()
        
        if expired_deals:
            logger.info(f"Found {len(expired_deals)} expired deals to update")
            
            # Update each expired deal
            for deal in expired_deals:
                deal.status = DealStatus.EXPIRED.value.lower()
                await self.db.flush()
                
                # Notify users if applicable
                if hasattr(self, 'notify_deal_expired'):
                    await self.notify_deal_expired(deal)
                    
            # Commit the changes
            await self.db.commit()
            
            logger.info(f"Updated {len(expired_deals)} deals to expired status")
        else:
            logger.info("No expired deals found")
            
    except Exception as e:
        logger.error(f"Error checking expired deals: {str(e)}") 