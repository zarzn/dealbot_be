"""Deal search module.

This module provides functionality for searching and discovering deals.
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional, Union, Tuple, Callable
from uuid import UUID, uuid4
from datetime import datetime, timedelta
from decimal import Decimal
import json
import re
import time

from sqlalchemy import select, or_, and_, func, text, case, cast, Float, String, literal

from core.models.deal import Deal, DealStatus
from core.models.goal import Goal, GoalStatus
from core.models.market import Market
from core.models.enums import MarketStatus, MarketCategory, MarketType
from core.exceptions import (
    ValidationError,
    ExternalServiceError
)
# Directly import API classes for proper type checking
from core.utils.ecommerce import AmazonAPI, WalmartAPI, EcommerceAPIError

logger = logging.getLogger(__name__)

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
        sort_by = getattr(search, 'sort', "relevance")
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
            
        # Build search query
        query_obj = select(Deal)
            
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
            if self._is_valid_market_category(category):
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
                
        # Apply sorting
        if sort_by == "price_asc":
            query_obj = query_obj.order_by(Deal.price.asc())
        elif sort_by == "price_desc":
            query_obj = query_obj.order_by(Deal.price.desc())
        elif sort_by == "date_desc":
            query_obj = query_obj.order_by(Deal.found_at.desc())
        elif sort_by == "date_asc":
            query_obj = query_obj.order_by(Deal.found_at.asc())
        elif sort_by == "discount":
            # Sort by calculated discount (original_price - price) / original_price
            # We need to handle cases where original_price is None
            discount_expr = case(
                (Deal.original_price != None, 
                 cast((Deal.original_price - Deal.price) / Deal.original_price * 100, Float)),
                else_=0.0
            )
            query_obj = query_obj.order_by(discount_expr.desc())
        else:
            # Default sort by relevance (found_at desc)
            query_obj = query_obj.order_by(Deal.found_at.desc())
                
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
            deal_dict = self._convert_to_response(deal, user_id, include_ai_analysis=False)
            deal_results.append(deal_dict)
                
        response["deals"] = deal_results
        response["has_more"] = (offset + len(deal_results)) < total_count
            
        # If not enough results, consider real-time scraping
        if len(deal_results) < limit and query:
            logger.info(f"Not enough results for query '{query}', performing real-time scraping")
            try:
                # Perform real-time scraping asynchronously
                scraping_task = asyncio.create_task(
                    self._perform_realtime_scraping(
                        query=query,
                        category=category,
                        min_price=float(min_price) if min_price else None,
                        max_price=float(max_price) if max_price else None,
                        perform_ai_analysis=perform_ai_analysis
                    )
                )
                    
                # Wait for scraping with timeout - increase from 15 to 45 seconds 
                # to accommodate the individual 30-second timeouts per market
                scraped_deals = await asyncio.wait_for(scraping_task, timeout=90.0)
                    
                # Process scraped deals
                for deal in scraped_deals:
                    deal_dict = self._convert_to_response(deal, user_id, include_ai_analysis=False)
                    if deal_dict not in deal_results:  # Avoid duplicates
                        deal_results.append(deal_dict)
                        
                # Update response
                response["deals"] = deal_results[:limit]  # Limit to page size
                response["total"] = total_count + len(scraped_deals)
                response["has_more"] = (offset + len(response["deals"])) < response["total"]
                response["realtime_scraping"] = True
                    
            except asyncio.TimeoutError:
                logger.warning("Real-time scraping timed out after 90 seconds")
            except Exception as e:
                logger.warning(f"Real-time scraping failed or timed out: {str(e)}")
                
        # Optionally perform AI analysis on results
        if perform_ai_analysis and response["deals"]:
            try:
                # Analyze results in parallel
                analysis_tasks = []
                for i, deal in enumerate(response["deals"]):
                    if isinstance(deal, dict) and "id" in deal:
                        task = asyncio.create_task(
                            self.analyze_deal_with_ai(
                                deal_id=UUID(deal["id"]),
                                user_id=user_id
                            )
                        )
                        analysis_tasks.append((i, task))
                            
                # Wait for all analysis tasks
                for i, task in analysis_tasks:
                    try:
                        analysis = await asyncio.wait_for(task, timeout=5.0)
                        if analysis:
                            response["deals"][i]["ai_analysis"] = analysis
                    except (asyncio.TimeoutError, Exception) as e:
                        logger.warning(f"AI analysis timed out for deal {response['deals'][i].get('id')}: {str(e)}")
                            
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
                
async def _perform_realtime_scraping(
    self, 
    query: str, 
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    ai_query_analysis: Optional[Dict[str, Any]] = None,
    perform_ai_analysis: bool = False,  # Controls only batch AI analysis, not query parsing
    max_products: int = 15  # Maximum number of products to return
) -> List[Deal]:
    """Perform real-time scraping for products matching the query.
    
    Args:
        query: Search query
        category: Optional category to filter by
        min_price: Optional minimum price to filter by
        max_price: Optional maximum price to filter by
        ai_query_analysis: Optional dictionary with AI analysis results
        perform_ai_analysis: Whether to perform batch AI analysis on results
        max_products: Maximum number of products to return after filtering
        
    Returns:
        List of created deals
    """
    start_time = time.time()
    
    try:
        # Initialize variables
        created_deals = []
        all_products = []
        all_filtered_products = []
        product_scores = {}
        
        # Get a Redis client for caching - do this in parallel with other operations
        from core.services.redis import get_redis_client
        redis_client_task = asyncio.create_task(get_redis_client())
        
        # Generate a cache key for this search
        import hashlib
        cache_key = f"scrape:{hashlib.md5(query.encode()).hexdigest()}"
        if category:
            cache_key += f":{category}"
        if min_price:
            cache_key += f":min{min_price}"
        if max_price:
            cache_key += f":max{max_price}"
        
        # Extract search keywords in parallel with other operations
        import re
        search_keywords = re.sub(r'[^\w\s]', ' ', query.lower()).split()
        common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for'}
        search_keywords = [word for word in search_keywords if word not in common_words and len(word) > 2]
        
        # Start market query in parallel with all other operations
        from sqlalchemy import select, or_
        from core.models.market import Market
        from core.models.enums import MarketStatus
        from core.integrations.market_factory import MarketIntegrationFactory
        
        # Create a task for querying active markets
        market_query_task = asyncio.create_task(
            self.db.execute(
                select(Market).where(
                    Market.is_active == True,
                    or_(
                        Market._status == MarketStatus.ACTIVE.value.lower(),
                        cast(Market._status, String).ilike('active')
                    )
                )
            )
        )
        
        # Get AI query analysis if needed - start this early in parallel
        ai_analysis_task = None
        if not ai_query_analysis:
            try:
                from core.services.ai import get_ai_service
                ai_service_task = asyncio.create_task(get_ai_service())
                
                # We'll gather and check this later
                ai_analysis_task = ai_service_task
            except Exception as e:
                logger.warning(f"Error setting up AI service task: {str(e)}")
        
        # Wait for Redis client to check cache
        redis_client = await redis_client_task
        cached_deals = None
        
        if redis_client:
            try:
                cached_data = await redis_client.get(cache_key)
                if cached_data:
                    import json
                    from core.models.deal import Deal
                    from sqlalchemy import select
                    
                    # Try to use cached results
                    serialized_deals = json.loads(cached_data)
                    deal_ids = [deal.get('id') for deal in serialized_deals if deal.get('id')]
                    
                    # Get the actual Deal objects from the database if we have IDs
                    if deal_ids:
                        cached_deals_task = asyncio.create_task(
                            self.db.execute(select(Deal).where(Deal.id.in_(deal_ids)))
                        )
                        # We'll check this later
            except Exception as e:
                logger.error(f"Error checking cache for search results: {str(e)}")
                cached_deals = None
        
        # Wait for market query to complete
        market_result = await market_query_task
        markets = market_result.scalars().all()
        logger.info(f"Found {len(markets)} active markets for real-time scraping")
        
        # Check if we have cached results
        if cached_deals is not None:
            cached_result = await cached_deals_task
            deals = cached_result.scalars().all()
            if deals:
                logger.info(f"Using cached search results for query: '{query}'")
                elapsed_time = time.time() - start_time
                logger.info(f"Served cached results in {elapsed_time:.2f} seconds")
                return list(deals)
        
        # Process AI analysis if needed
        if ai_analysis_task is not None:
            try:
                ai_service = await ai_service_task
                if ai_service and ai_service.llm:
                    logger.info("Performing AI analysis on search query")
                    
                    # Create a task for AI analysis with timeout
                    ai_query_task = asyncio.create_task(
                        ai_service.analyze_search_query(
                            query=query,
                            category=category
                        )
                    )
                    
                    # Set a shorter timeout for AI analysis to ensure we meet our time budget
                    try:
                        ai_query_analysis = await asyncio.wait_for(ai_query_task, timeout=10.0)
                        logger.info(f"AI query analysis results: {ai_query_analysis}")
                    except asyncio.TimeoutError:
                        logger.warning("AI query analysis timed out after 10 seconds - continuing without it")
                        ai_query_analysis = None
                    except Exception as e:
                        logger.warning(f"AI query analysis failed: {str(e)}")
                        ai_query_analysis = None
            except Exception as e:
                logger.warning(f"Error initializing AI service: {str(e)}")
                ai_query_analysis = None
        
        # Process in parallel: Prepare market information list
        search_markets = []
        market_factory = MarketIntegrationFactory()
        
        for market in markets:
            try:
                market_id = market.id
                market_name = market.name
                market_type = market.type.lower() if hasattr(market, 'type') else "unknown"
                search_markets.append((market_name, market_type, market_id))
            except Exception as e:
                logger.error(f"Error processing market {market.name}: {str(e)}")
        
        # Define function for market search with improved error handling and timeout
        async def process_market_search(market_info):
            market_name, market_type, market_id = market_info
            
            # Set a shorter timeout based on market type to ensure we meet our time budget
            market_timeout = 10.0  # Reduce default timeout to 10 seconds to meet 15-20 second goal
            if market_type.lower() == 'google_shopping':
                market_timeout = 15.0  # Still give Google Shopping a bit more time, but reduced
            
            try:
                # Use the _search_products method with appropriate timeout based on market type
                search_task = market_factory.search_products(
                    market=market_type,
                    query=query,
                    limit=15  # Limit results to avoid excessive processing
                )
                
                # Apply timeout at this level
                products = await asyncio.wait_for(search_task, timeout=market_timeout)
                
                # Check if we got valid products
                if products and isinstance(products, list):
                    logger.info(f"Found {len(products)} products from {market_name}")
                    
                    # Add market info to products
                    for product in products:
                        if isinstance(product, dict):
                            product['market'] = market_type
                            product['market_id'] = str(market_id)
                            product['market_name'] = market_name
                    
                    return products
                else:
                    logger.warning(f"No valid products returned from {market_name}")
                    return []
                    
            except asyncio.TimeoutError:
                logger.warning(f"Search for {market_name} timed out after {market_timeout} seconds")
                return []
            except Exception as e:
                logger.error(f"Error searching {market_name}: {str(e)}")
                return []
        
        # Execute all market searches in true parallel, with a global timeout
        overall_search_timeout = 15.0  # Set to meet our 15-20 second goal
        try:
            # Execute all market searches in parallel with a global timeout
            task_results = await asyncio.wait_for(
                asyncio.gather(
                    *[process_market_search(market_info) for market_info in search_markets],
                    return_exceptions=False  # We handle exceptions in the process_market_search function
                ),
                timeout=overall_search_timeout
            )
            
            # Combine results from all tasks
            for product_list in task_results:
                if product_list:  # Skip empty lists
                    all_products.extend(product_list)
                    
        except asyncio.TimeoutError:
            logger.warning(f"Global market search timeout after {overall_search_timeout} seconds - using partial results")
        
        logger.info(f"Collected a total of {len(all_products)} products from all markets")
        
        # Filter and sort products concurrently
        async def filter_and_score_products():
            filtered_products = []
            scores = {}
            
            for product in all_products:
                try:
                    # Apply price filtering
                    product_price = float(product.get('price', 0))
                    
                    # Skip products with price 0 (likely errors)
                    if product_price == 0:
                        continue
                        
                    # Apply min price filter
                    if min_price is not None and product_price < min_price:
                        continue
                        
                    # Apply max price filter
                    if max_price is not None and product_price > max_price:
                        continue
                        
                    # Apply keyword relevance filtering
                    product_name = product.get('title', '').lower()
                    product_desc = product.get('description', '').lower()
                    
                    # Calculate a basic match score
                    match_score = 0
                    for keyword in search_keywords:
                        if keyword in product_name:
                            match_score += 2  # Double weight for title matches
                        if keyword in product_desc:
                            match_score += 1  # Single weight for description matches
                            
                    product_id = product.get('id', str(uuid4()))
                    scores[product_id] = match_score
                    product['_id'] = product_id  # Store ID for sorting
                    
                    # Add product to filtered list
                    filtered_products.append(product)
                    
                except Exception as e:
                    logger.error(f"Error filtering product: {str(e)}")
            
            return filtered_products, scores
        
        # Execute filtering concurrently
        all_filtered_products, product_scores = await filter_and_score_products()
        
        logger.info(f"Filtered down to {len(all_filtered_products)} products")
        
        # Sort products by score
        if product_scores:
            all_filtered_products.sort(
                key=lambda p: product_scores.get(p.get('_id', ''), 0), 
                reverse=True
            )
        
        # Limit to max_products
        all_filtered_products = all_filtered_products[:max_products]
        
        # Create deal creation tasks in parallel
        async def create_deal_task(product):
            try:
                # Add AI query analysis to product if available
                if ai_query_analysis:
                    product['ai_query_analysis'] = ai_query_analysis
                
                # Convert to deal
                deal = await self._create_deal_from_product(
                    product=product,
                    query=query,
                    market_type=product.get('market')
                )
                
                if deal:
                    logger.info(f"Created deal for product: {product.get('title', '')[:30]}...")
                    return deal
                else:
                    logger.warning(f"Failed to create deal for product: {product.get('title', '')[:30]}...")
                    return None
            except Exception as e:
                logger.error(f"Error creating deal from product: {str(e)}")
                return None
        
        # Create deals in parallel with a timeout
        deal_creation_timeout = 10.0  # Set timeout to meet our goal
        try:
            # Use asyncio.gather to create all deals in parallel
            deal_results = await asyncio.wait_for(
                asyncio.gather(
                    *[create_deal_task(product) for product in all_filtered_products],
                    return_exceptions=False
                ),
                timeout=deal_creation_timeout
            )
            
            # Filter out None values
            created_deals = [deal for deal in deal_results if deal is not None]
            
        except asyncio.TimeoutError:
            logger.warning(f"Deal creation timed out after {deal_creation_timeout} seconds - using partial results")
        
        logger.info(f"Successfully created {len(created_deals)} deals from real-time scraping")
        
        # Cache the result in the background to avoid blocking
        if redis_client and created_deals:
            async def cache_results():
                try:
                    # Convert deals to serializable format
                    import json
                    from core.services.redis import UUIDEncoder
                    from core.services.deal.utils import _deal_to_dict
                    
                    # Serialize the deals
                    deals_data = [_deal_to_dict(deal) for deal in created_deals]
                    serialized_deals = json.dumps(deals_data, cls=UUIDEncoder)
                    
                    # Cache for 5 minutes (300 seconds)
                    await redis_client.set(cache_key, serialized_deals, ex=300)
                    logger.debug(f"Cached search results for query: '{query}'")
                except Exception as e:
                    logger.error(f"Error caching search results: {str(e)}")
            
            # Start caching in the background to avoid waiting
            asyncio.create_task(cache_results())
        
        return created_deals
        
    except Exception as e:
        logger.error(f"Error in real-time scraping: {str(e)}", exc_info=True)
        return []
    finally:
        # Log warnings if the operation takes too long
        elapsed_time = time.time() - start_time
        if elapsed_time > 20:
            logger.warning(f"Real-time scraping operation took longer than target: {elapsed_time:.1f} seconds")
        else:
            logger.info(f"Real-time scraping completed in {elapsed_time:.1f} seconds")

async def _filter_deals(
    self,
    products: List[Dict[str, Any]],
    query: str,
    normalized_terms: List[str],
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    brands: Optional[List[str]] = None,
    features: Optional[List[str]] = None,
    quality_requirement: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
    """Filter products based on various criteria and calculate relevance scores.
    
    Args:
        products: List of product dictionaries to filter
        query: Original search query
        normalized_terms: Normalized search terms for matching
        min_price: Minimum price filter
        max_price: Maximum price filter
        brands: List of desired brands to filter by
        features: List of desired features to filter by
        quality_requirement: Quality requirement string
        
    Returns:
        Tuple of (filtered_products, product_scores)
    """
    logger.info(f"Filtering {len(products)} products with criteria: min_price={min_price}, max_price={max_price}")
    
    # Initialize scores dictionary and filtered products list
    product_scores = {}
    filtered_products = []
    
    # Define basic similarity and term matching functions
    def basic_similarity(string1, string2):
        """Calculate basic similarity between two strings."""
        if not string1 or not string2:
            return 0
            
        s1 = string1.lower()
        s2 = string2.lower()
        
        # Direct match
        if s1 == s2:
            return 1.0
            
        # Substring match
        if s1 in s2 or s2 in s1:
            return 0.8
            
        # Word match - count matching words
        words1 = set(s1.split())
        words2 = set(s2.split())
        common_words = words1.intersection(words2)
        
        if not words1 or not words2:
            return 0
            
        return len(common_words) / max(len(words1), len(words2))
    
    def flexible_term_match(term, text):
        """Check if a term matches flexibly in text."""
        if not term or not text:
            return False
            
        term = term.lower()
        text = text.lower()
        
        # Direct match
        if term in text:
            return True
            
        # Handle plurals
        if term.endswith('s') and term[:-1] in text:
            return True
        if not term.endswith('s') and f"{term}s" in text:
            return True
            
        # Handle hyphenation
        if '-' in term:
            non_hyphen = term.replace('-', '')
            if non_hyphen in text:
                return True
                
        if ' ' in term:
            hyphenated = term.replace(' ', '-')
            if hyphenated in text:
                return True
                
        return False
    
    # Process each product
    for product in products:
        # Skip products with no price or missing essential data
        if 'price' not in product or product['price'] is None:
            continue
            
        if 'title' not in product or not product['title']:
            continue
            
        # Initialize score
        score = 0.0
        score_reasons = []
        
        # Convert price to float for comparison
        try:
            price = float(product['price'])
        except (ValueError, TypeError):
            continue
            
        # Apply price filtering
        if min_price is not None and price < min_price:
            continue
            
        if max_price is not None and price > max_price:
            continue
            
        # Score: term matching in title
        title = product.get('title', '').lower()
        title_match_score = 0
        
        for term in normalized_terms:
            if flexible_term_match(term, title):
                title_match_score += 1
                
        if normalized_terms:
            title_match_ratio = title_match_score / len(normalized_terms)
            score += title_match_ratio * 0.4  # Title matches are important
            score_reasons.append(f"Title match: {title_match_ratio:.2f}")
        
        # Score: term matching in description
        description = product.get('description', '').lower()
        desc_match_score = 0
        
        for term in normalized_terms:
            if flexible_term_match(term, description):
                desc_match_score += 1
                
        if normalized_terms and description:
            desc_match_ratio = desc_match_score / len(normalized_terms)
            score += desc_match_ratio * 0.2  # Description matches less important than title
            score_reasons.append(f"Description match: {desc_match_ratio:.2f}")
        
        # Score: brand matching if brands are specified
        if brands:
            brand_matches = 0
            product_brand = product.get('brand', '').lower()
            
            if not product_brand and 'metadata' in product:
                # Try to find brand in metadata
                product_brand = product['metadata'].get('brand', '').lower()
                
            for brand in brands:
                if flexible_term_match(brand.lower(), product_brand) or \
                   flexible_term_match(brand.lower(), title) or \
                   flexible_term_match(brand.lower(), description):
                    brand_matches += 1
                    
            if brand_matches > 0:
                brand_match_ratio = brand_matches / len(brands)
                score += brand_match_ratio * 0.2
                score_reasons.append(f"Brand match: {brand_match_ratio:.2f}")
        
        # Score: feature matching if features are specified
        if features:
            feature_matches = 0
            for feature in features:
                if flexible_term_match(feature.lower(), title) or \
                   flexible_term_match(feature.lower(), description):
                    feature_matches += 1
                    
            if feature_matches > 0:
                feature_match_ratio = feature_matches / len(features)
                score += feature_match_ratio * 0.2
                score_reasons.append(f"Feature match: {feature_match_ratio:.2f}")
        
        # Discount bonus: if original price is available, give bonus for bigger discounts
        if 'original_price' in product and product['original_price'] and product['original_price'] > price:
            try:
                original_price = float(product['original_price'])
                discount_percent = (original_price - price) / original_price * 100
                
                if discount_percent >= 50:
                    score += 0.2
                    score_reasons.append("Large discount (50%+)")
                elif discount_percent >= 30:
                    score += 0.1
                    score_reasons.append("Good discount (30%+)")
                elif discount_percent >= 15:
                    score += 0.05
                    score_reasons.append("Moderate discount (15%+)")
            except (ValueError, TypeError):
                pass
        
        # Quality score based on reviews/ratings if available
        review_count = 0
        rating = 0
        
        if 'rating' in product:
            try:
                rating = float(product['rating'])
            except (ValueError, TypeError):
                pass
                
        if 'review_count' in product:
            try:
                review_count = int(product['review_count'])
            except (ValueError, TypeError):
                pass
        
        # Metadata might have this info if not in the main product data
        if 'metadata' in product:
            metadata = product['metadata']
            if not rating and 'rating' in metadata:
                try:
                    rating = float(metadata['rating'])
                except (ValueError, TypeError):
                    pass
                    
            if not review_count and 'review_count' in metadata:
                try:
                    review_count = int(metadata['review_count'])
                except (ValueError, TypeError):
                    pass
        
        # Add score for high ratings with sufficient reviews
        if rating > 0 and review_count > 0:
            rating_score = 0
            
            if rating >= 4.5 and review_count >= 100:
                rating_score = 0.15
                score_reasons.append("Excellent rating (4.5+ with 100+ reviews)")
            elif rating >= 4.0 and review_count >= 50:
                rating_score = 0.1
                score_reasons.append("Very good rating (4.0+ with 50+ reviews)")
            elif rating >= 3.5 and review_count >= 20:
                rating_score = 0.05
                score_reasons.append("Good rating (3.5+ with 20+ reviews)")
                
            score += rating_score
        
        # Store the score
        product_scores[product.get('id', str(uuid4()))] = score
        
        # Add product to filtered products
        product['relevance_score'] = score
        product['relevance_reasons'] = score_reasons
        filtered_products.append(product)
    
    # Sort filtered products by score
    filtered_products.sort(key=lambda p: p.get('relevance_score', 0), reverse=True)
    
    logger.info(f"Filtered down to {len(filtered_products)} products that match criteria")
    if filtered_products:
        logger.info(f"Top product score: {filtered_products[0].get('relevance_score', 0)}")
        
    return filtered_products, product_scores

async def _create_deal_from_product(
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

async def _monitor_deals(self) -> None:
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

async def _fetch_deals_from_api(self, api: Any, goals: List[Dict]) -> List[Dict]:
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

def _build_search_params(self, goal: Dict) -> Dict:
    """Build search parameters from goal constraints"""
    return {
        'keywords': goal.get('keywords', []),
        'price_range': (goal.get('min_price'), goal.get('max_price')),
        'brands': goal.get('brands', []),
        'categories': goal.get('categories', [])
    }

async def _process_and_store_deals(self, deals: List[Dict]) -> None:
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

def _is_valid_market_category(self, category: str) -> bool:
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
        deal = await self.create_deal_from_dict(deal_data)
        
        # Try to match with goals
        await self.match_with_goals(deal.id)
        
        return deal
    except Exception as e:
        logger.error(f"Failed to discover deal: {str(e)}")
        raise ExternalServiceError(
            service="deal_service",
            operation=f"discover_deal: {str(e)}"
        )

def _get_market_id_for_category(self, category: str) -> UUID:
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

async def _search_products(
    self,
    query: str,
    market_type: str,
    search_provider: Callable,
    real_time: bool = False,
    limit: int = 25,
    **kwargs
) -> Optional[List[Dict[str, Any]]]:
    """Search for products with a provider.
    
    Args:
        query: Search query
        market_type: Market type
        search_provider: Search provider function
        real_time: Whether to search in real-time
        limit: Maximum number of products to return
        **kwargs: Additional arguments for the search provider
        
    Returns:
        List of products or None if search failed
    """
    if not query or not market_type:
        logger.warning("Missing query or market_type")
        return None
        
    # Set different timeouts based on market type
    timeout = 30.0  # Default timeout
    if market_type.lower() == 'google_shopping':
        timeout = 60.0  # Extended timeout for Google Shopping to match ScraperAPI setting
        
    try:
        logger.info(f"Searching for {market_type} products with query: {query}")
        start_time = time.time()
        
        # Call the search provider with a timeout
        task = search_provider(
            query=query,
            real_time=real_time,
            limit=limit,
            **kwargs
        )
        
        try:
            products = await asyncio.wait_for(task, timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"Search for {market_type} timed out after {timeout} seconds")
            return None
            
        end_time = time.time()
        search_time = end_time - start_time
        
        if products:
            logger.info(f"Found {len(products)} {market_type} products in {search_time:.2f} seconds")
            return products
        else:
            logger.warning(f"No {market_type} products found in {search_time:.2f} seconds")
            return None
            
    except Exception as e:
        logger.error(f"Error searching for {market_type} products: {e}", exc_info=True)
        return None