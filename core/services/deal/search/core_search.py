"""
Core search functionality for deals.

This module provides the main search functionality for finding deals
based on various criteria and parameters.
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional, Union
from uuid import UUID
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select, or_, and_, func, text, case, cast, Float, String
from sqlalchemy.orm import selectinload

from core.models.deal import Deal, DealStatus
from core.models.goal import Goal
from core.models.enums import MarketStatus, MarketCategory, MarketType
from core.exceptions import ValidationError, ExternalServiceError
from core.utils.logger import get_logger

logger = get_logger(__name__)

async def search_deals(
    self,
    search: Any,
    user_id: Optional[UUID] = None,
    perform_ai_analysis: bool = False
) -> Dict[str, Any]:
    """Search for deals with optional AI-enhanced capabilities
    
    Args:
        search: Search parameters (query, filters, etc.)
        user_id: Optional user ID for tracking or personalization
        perform_ai_analysis: Whether to perform AI analysis on results
        
    Returns:
        Dictionary with search results and metadata
        
    Raises:
        ValidationError: If search parameters are invalid
        ExternalServiceError: If external services fail
    """
    try:
        # Validate search parameters
        if not hasattr(search, 'query') and not hasattr(search, 'category'):
            raise ValidationError("Search must include either query or category")
            
        # Initialize search response
        response = {
            "deals": [],
            "total": 0,
            "page": getattr(search, 'page', 1),
            "page_size": getattr(search, 'page_size', 20),
            "has_more": False,
            "query": getattr(search, 'query', ""),
            "filters_applied": {},
            "sort_applied": getattr(search, 'sort', "relevance")
        }
            
        # Extract search parameters
        query = getattr(search, 'query', None)
        category = getattr(search, 'category', None)
        min_price = getattr(search, 'min_price', None)
        max_price = getattr(search, 'max_price', None)
        start_date = getattr(search, 'start_date', None)
        end_date = getattr(search, 'end_date', None)
        sort_by = getattr(search, 'sort_by', "relevance")
        sort_order = getattr(search, 'sort_order', "desc")
        market_ids = getattr(search, 'market_ids', None)
        status = getattr(search, 'status', "active")
        include_expired = getattr(search, 'include_expired', False)
        limit = getattr(search, 'limit', 20)
        
        # Use the offset from the search object or calculate it from page/page_size
        if hasattr(search, 'offset') and search.offset is not None:
            offset = search.offset
        else:
            page = getattr(search, 'page', 1)
            page_size = getattr(search, 'page_size', 20)
            offset = (page - 1) * page_size
            
        # Update filters applied
        response["filters_applied"] = {
            "query": query,
            "category": category,
            "min_price": min_price,
            "max_price": max_price,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "market_ids": [str(mid) for mid in market_ids] if market_ids else None,
            "status": status,
            "include_expired": include_expired
        }
            
        # Build search query with eager loading of market relationship
        query_obj = select(Deal).options(selectinload(Deal.market))
            
        # Apply filters
        filters = []
            
        if status and status != "all":
            filters.append(Deal.status == status)
                
        if not include_expired:
            # Either expires_at is null or expires_at is in the future
            filters.append(or_(
                Deal.expires_at == None,
                Deal.expires_at > datetime.utcnow()
            ))
                
        if query:
            # Full text search on title and description
            filters.append(or_(
                Deal.title.ilike(f"%{query}%"),
                Deal.description.ilike(f"%{query}%"),
            ))
                
        if category:
            # Category matching - use validated category with exact match
            # First check if the category is valid to avoid SQL errors
            from core.services.deal.search.utils import is_valid_market_category
            if is_valid_market_category(self, category):
                filters.append(Deal.category == category)
            else:
                logger.warning(f"Invalid category provided: {category}. Ignoring this filter.")
                
        if min_price is not None:
            filters.append(Deal.price >= Decimal(str(min_price)))
                
        if max_price is not None:
            filters.append(Deal.price <= Decimal(str(max_price)))
                
        if start_date:
            filters.append(Deal.found_at >= start_date)
                
        if end_date:
            filters.append(Deal.found_at <= end_date)
                
        if market_ids:
            filters.append(Deal.market_id.in_(market_ids))
                
        if user_id:
            # Personalized results - factor in user preferences
            # This could include deals the user has previously interacted with
            # or deals related to user's goals
            pass
                
        # Apply all filters
        if filters:
            query_obj = query_obj.where(and_(*filters))
                
        # Apply sorting with improved mapping
        logger.info(f"Applying sort: sort_by={sort_by}, sort_order={sort_order}")
        
        # Get the column to sort by
        if sort_by == "price" or sort_by == "price_asc" or sort_by == "price_desc":
            sort_column = Deal.price
            logger.info(f"Sorting by price column")
        elif sort_by == "created_at" or sort_by == "date":
            sort_column = Deal.created_at
            logger.info(f"Sorting by created_at column")
        elif sort_by == "found_at":
            sort_column = Deal.found_at
            logger.info(f"Sorting by found_at column")
        elif sort_by == "title":
            sort_column = Deal.title
            logger.info(f"Sorting by title column")
        elif sort_by == "discount":
            # Sort by calculated discount (original_price - price) / original_price
            # We need to handle cases where original_price is None
            discount_expr = case(
                (Deal.original_price != None, 
                 cast((Deal.original_price - Deal.price) / Deal.original_price * 100, Float)),
                else_=0.0
            )
            logger.info(f"Sorting by discount expression")
            query_obj = query_obj.order_by(
                discount_expr.desc() if sort_order.lower() == "desc" else discount_expr.asc()
            )
            # Skip the standard ordering logic for discount since we already applied it
            sort_column = None
        else:
            # Default sort by relevance (found_at desc)
            sort_column = Deal.found_at
            logger.warning(f"Unknown sort_by value: {sort_by}, defaulting to found_at")
        
        # Apply sort direction if we have a column to sort by
        if sort_column:
            if sort_order and sort_order.lower() == "asc":
                logger.info(f"Applying ASCENDING sort order")
                query_obj = query_obj.order_by(sort_column.asc())
            else:
                logger.info(f"Applying DESCENDING sort order")
                query_obj = query_obj.order_by(sort_column.desc())
            
            # Include sort info in response
            response["sort_applied"] = sort_by
            response["sort_order"] = sort_order
        
        # Add debugging output for the actual SQL query
        from sqlalchemy.dialects import postgresql
        sql_str = str(query_obj.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True}
        ))
        logger.debug(f"Generated SQL query: {sql_str}")
                
        # Count total results using scalar count
        count_query = select(text("COUNT(*)")).select_from(query_obj.subquery())
        total_count = await self._repository.db.scalar(count_query)
        response["total"] = total_count or 0
            
        # Apply pagination using the offset from search object
        query_obj = query_obj.offset(offset).limit(limit)
            
        # Execute query
        result = await self._repository.db.execute(query_obj)
        deals = result.scalars().all()
            
        # Prepare results
        deal_results = []
        for deal in deals:
            # Convert to response format
            from core.services.deal.search.utils import convert_to_response
            deal_dict = convert_to_response(self, deal, user_id, include_ai_analysis=False)
            deal_results.append(deal_dict)
                
        response["deals"] = deal_results
        response["has_more"] = (offset + len(deal_results)) < total_count
            
        # If not enough results, consider real-time scraping
        if len(deal_results) < limit and query:
            logger.info(f"Not enough results for query '{query}', performing real-time scraping")
            try:
                # Import the function directly here to ensure it's in the same async context
                from core.services.deal.search.realtime import perform_realtime_scraping
                
                # Prepare parameters for real-time scraping
                scraping_params = {
                    "query": query,
                    "category": category,
                    "min_price": float(min_price) if min_price is not None else None,
                    "max_price": float(max_price) if max_price is not None else None,
                    "perform_ai_analysis": perform_ai_analysis,
                    "user_id": user_id
                }
                
                # Use direct function call for better async context
                logger.debug(f"Starting real-time scraping with parameters: {scraping_params}")
                try:
                    # Call the function directly without creating a separate task
                    scraped_deals = await perform_realtime_scraping(self, **scraping_params)
                    
                    # Process scraped deals if we got any
                    if scraped_deals and len(scraped_deals) > 0:
                        logger.info(f"Real-time scraping produced {len(scraped_deals)} deals")
                        
                        # Ensure we have market data loaded for all scraped deals
                        # Collect IDs to load markets all at once
                        market_ids_to_load = []
                        for deal in scraped_deals:
                            if deal.market_id and deal.market_id not in market_ids_to_load:
                                market_ids_to_load.append(deal.market_id)
                        
                        # Load all markets for these deals in a single query if needed
                        markets_by_id = {}
                        if market_ids_to_load:
                            from core.models.market import Market
                            try:
                                market_query = select(Market).where(Market.id.in_(market_ids_to_load))
                                market_result = await self._repository.db.execute(market_query)
                                markets = market_result.scalars().all()
                                
                                # Create a dict for quick lookups
                                for market in markets:
                                    markets_by_id[market.id] = market
                            except Exception as e:
                                logger.warning(f"Error loading markets for scraped deals: {str(e)}")
                        
                        # Now process each deal with pre-loaded market data
                        for deal in scraped_deals:
                            # Manually attach market to deal if available (to avoid lazy loading)
                            if deal.market_id and deal.market_id in markets_by_id:
                                deal.__dict__['market'] = markets_by_id[deal.market_id]
                            
                            from core.services.deal.search.utils import convert_to_response
                            deal_dict = convert_to_response(self, deal, user_id, include_ai_analysis=False)
                            if deal_dict not in deal_results:  # Avoid duplicates
                                deal_results.append(deal_dict)
                        
                        # Update response
                        response["deals"] = deal_results[:limit]  # Limit to page size
                        response["total"] = total_count + len(scraped_deals)
                        response["has_more"] = (offset + len(response["deals"])) < response["total"]
                        response["realtime_scraping"] = True
                    else:
                        logger.warning("Real-time scraping returned no deals")
                except asyncio.TimeoutError:
                    logger.warning("Real-time scraping timed out")
                except Exception as inner_e:
                    logger.warning(f"Error during real-time scraping: {str(inner_e)}", exc_info=True)
                
            except Exception as e:
                logger.warning(f"Real-time scraping failed or timed out: {str(e)}", exc_info=True)
                
        # Optionally perform AI analysis on results
        if perform_ai_analysis and response["deals"]:
            try:
                # Analyze results safely to avoid async issues
                analysis_tasks = []
                
                # Make sure we only create tasks for properly formed deals
                for i, deal_dict in enumerate(response["deals"]):
                    if isinstance(deal_dict, dict) and "id" in deal_dict:
                        try:
                            # Create a task but handle each one independently to avoid aborting all analyses
                            task = asyncio.create_task(
                                self.analyze_deal_with_ai(
                                    deal_id=UUID(deal_dict["id"]),
                                    user_id=user_id
                                )
                            )
                            analysis_tasks.append((i, task))
                        except Exception as task_error:
                            logger.warning(f"Error creating AI analysis task for deal {deal_dict.get('id')}: {str(task_error)}")
                                
                # Wait for all analysis tasks
                for i, task in analysis_tasks:
                    try:
                        # Use a reasonable timeout
                        analysis = await asyncio.wait_for(task, timeout=5.0)
                        if analysis:
                            # Only add analysis if we got valid results
                            response["deals"][i]["ai_analysis"] = analysis
                    except asyncio.TimeoutError:
                        logger.warning(f"AI analysis timed out for deal {response['deals'][i].get('id')}")
                    except Exception as e:
                        logger.warning(f"Error in AI analysis for deal {response['deals'][i].get('id')}: {str(e)}")
                            
                response["ai_enhanced"] = True
                    
            except Exception as e:
                logger.error(f"Error performing AI analysis on search results: {str(e)}")
                response["ai_enhanced"] = False
                
        return response
            
    except ValidationError:
        raise
    except ExternalServiceError:
        raise
    except Exception as e:
        logger.error(f"Error searching deals: {str(e)}")
        raise ExternalServiceError(
            service="deal_service",
            operation=f"search_deals: {str(e)}"
        )

async def discover_deal(self, market_id: UUID, product_data: Dict[str, Any]) -> Deal:
    """Discover and create a new deal in a specific market.
    
    Args:
        market_id: The ID of the market
        product_data: Product information to create the deal
        
    Returns:
        The created deal
        
    Raises:
        ExternalServiceError: If deal creation fails
    """
    try:
        # Generate deal data
        from core.config import settings
        system_user_id = settings.SYSTEM_USER_ID  # System user for discovered deals
        
        # Ensure price is valid
        price = Decimal(product_data.get("price", "0.01"))
        if price <= Decimal("0"):
            price = Decimal("0.01")
            
        # Create deal data
        deal_data = {
            "user_id": UUID(system_user_id),
            "market_id": market_id,
            "title": product_data.get("title"),
            "description": product_data.get("description", ""),
            "price": price,
            "original_price": Decimal(product_data.get("original_price", "0")) if product_data.get("original_price") else None,
            "currency": product_data.get("currency", "USD"),
            "source": "discovery",
            "url": product_data.get("url"),
            "image_url": product_data.get("image_url"),
            "category": product_data.get("category", "Uncategorized"),
            "seller_info": product_data.get("seller_info", {}),
            "deal_metadata": product_data.get("metadata", {}),
            "price_metadata": product_data.get("price_metadata", {}),
            "status": DealStatus.ACTIVE.value
        }
        
        # Create the deal
        from core.services.deal.search.deal_creation import create_deal_from_dict
        deal = await create_deal_from_dict(self, deal_data)
        
        # Try to match with goals
        await self.match_with_goals(deal.id)
        
        return deal
    except Exception as e:
        logger.error(f"Failed to discover deal: {str(e)}")
        raise ExternalServiceError(
            service="deal_service",
            operation=f"discover_deal: {str(e)}"
        ) 