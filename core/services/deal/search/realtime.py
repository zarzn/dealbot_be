"""
Real-time scraping module for deal search.

This module provides functionality for real-time scraping of product data
from various e-commerce platforms to supplement search results.
"""

import logging
import asyncio
import time
import json
import hashlib
from typing import List, Dict, Any, Optional, Union
from uuid import UUID, uuid4
from decimal import Decimal

from sqlalchemy import select, or_, cast, String

from core.models.deal import Deal
from core.models.market import Market
from core.models.enums import MarketStatus
from core.services.deal.search.post_scraping_filter import (
    post_process_products,
    extract_price_constraints,
    extract_brands_from_query
)
from core.services.deal.search.query_formatter import get_optimized_query_for_marketplace
from core.integrations.market_factory import MarketIntegrationFactory
from core.utils.logger import get_logger

logger = get_logger(__name__)

async def perform_realtime_scraping(
    self, 
    query: str, 
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    ai_query_analysis: Optional[Dict[str, Any]] = None,
    perform_ai_analysis: bool = False,  # Controls only batch AI analysis, not query parsing
    max_products: int = 15,  # Maximum number of products to return
    user_id: Optional[UUID] = None  # Add user_id parameter
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
        user_id: Optional user ID to associate with created deals
        
    Returns:
        List of created deals
    """
    start_time = time.time()
    
    try:
        # Import required modules
        from sqlalchemy import select, or_
        
        # Initialize variables
        created_deals = []
        all_products = []
        all_filtered_products = []
        product_scores = {}
        search_markets = []
        
        # Extract price constraints if not provided
        if min_price is None or max_price is None:
            extracted_min, extracted_max = extract_price_constraints(query)
            if min_price is None:
                min_price = extracted_min
            if max_price is None:
                max_price = extracted_max
        
        # Extract brands from query for later filtering
        brands = extract_brands_from_query(query)
        logger.info(f"Extracted brands from query: {brands}")
        
        # Get a Redis client for caching - do this in parallel with other operations
        from core.services.redis import get_redis_client
        redis_client_task = asyncio.create_task(get_redis_client())
        
        # Generate a cache key for this search
        cache_key = f"scrape:{hashlib.md5(query.encode()).hexdigest()}"
        if category:
            cache_key += f":{category}"
        if min_price:
            cache_key += f":min{min_price}"
        if max_price:
            cache_key += f":max{max_price}"
        logger.debug(f"Generated cache key: {cache_key}")
        
        # Start market query in parallel with all other operations
        # Import necessary classes
        from sqlalchemy import select, or_
        from core.models.market import Market
        from core.models.enums import MarketStatus
        
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
        
        # Get AI service for query formatting - start this early in parallel
        ai_service = None
        try:
            from core.services.ai import get_ai_service
            ai_service_task = asyncio.create_task(get_ai_service())
        except Exception as e:
            logger.warning(f"Error setting up AI service task: {str(e)}")
            ai_service_task = None
        
        # Wait for Redis client to check cache
        redis_client = await redis_client_task
        cached_deals = None
        
        if redis_client:
            try:
                cached_data = await redis_client.get(cache_key)
                if cached_data:
                    import json
                    
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
        
        # Wait for AI service if we started a task
        if ai_service_task:
            try:
                ai_service = await ai_service_task
            except Exception as e:
                logger.error(f"Error getting AI service: {str(e)}")
                ai_service = None
        
        # Wait for market query to complete
        market_result = await market_query_task
        markets = market_result.scalars().all()
        logger.info(f"Found {len(markets)} active markets for real-time scraping")
        
        # Process markets and prepare for search
        market_factory = MarketIntegrationFactory()
        
        for market in markets:
            try:
                market_id = market.id
                market_name = market.name
                market_type = market.type.lower() if hasattr(market, 'type') else "unknown"
                search_markets.append((market_name, market_type, market_id))
            except Exception as e:
                logger.error(f"Error processing market {market.name}: {str(e)}")
        
        # Define function for market search with optimized queries and post-filtering
        async def process_market_search(market_info):
            market_name, market_type, market_id = market_info
            
            # Set a shorter timeout based on market type to ensure we meet our time budget
            market_timeout = 20.0  # Default timeout: 20 seconds (increased from 10)
            if market_type.lower() == 'google_shopping':
                market_timeout = 30.0  # Google Shopping gets more time (increased from 15)
            
            logger.info(f"Starting search for {market_name} with timeout of {market_timeout} seconds")
            
            try:
                # Format the query for this specific marketplace
                try:
                    optimized_result = await get_optimized_query_for_marketplace(
                        query, market_type, ai_service
                    )
                    optimized_query = optimized_result['formatted_query']
                    parameters = optimized_result['parameters']
                    
                    logger.info(
                        f"Optimized query for {market_name}: '{query}' -> '{optimized_query}'"
                    )
                except Exception as e:
                    logger.error(f"Error optimizing query for {market_name}: {str(e)}. Using original query.")
                    optimized_query = query
                    parameters = {}
                
                # Use the _search_products method with appropriate timeout based on market type
                logger.debug(f"Initiating search for {market_name} with query: '{optimized_query}'")
                search_task = market_factory.search_products(
                    market=market_type,
                    query=optimized_query,
                    limit=15  # Limit results to avoid excessive processing
                )
                
                # Apply timeout at this level
                products = await asyncio.wait_for(search_task, timeout=market_timeout)
                
                # Check if we got valid products
                if products and isinstance(products, list):
                    logger.info(f"Found {len(products)} raw products from {market_name}")
                    
                    # Apply post-scraping filtering
                    logger.debug(f"Applying post-scraping filters for {market_name} products")
                    filtered_products = post_process_products(
                        products=products,
                        query=query,
                        min_price=min_price,
                        max_price=max_price,
                        brands=brands
                    )
                    
                    logger.info(
                        f"Post-filtering: {len(products)} -> {len(filtered_products)} products from {market_name}"
                    )
                    
                    # Add market info to products
                    for product in filtered_products:
                        if isinstance(product, dict):
                            product['market'] = market_type
                            product['market_id'] = str(market_id)
                            product['market_name'] = market_name
                            
                            # Save relevance score for later sorting
                            product_id = product.get('id', str(uuid4()))
                            product['_id'] = product_id
                            relevance_score = product.get('_relevance_score', 0.0)
                            product_scores[product_id] = relevance_score
                    
                    return filtered_products
                else:
                    logger.warning(f"No valid products returned from {market_name} or products not in expected format")
                    if products:
                        logger.debug(f"Received data type: {type(products)}")
                    return []
                    
            except asyncio.TimeoutError:
                logger.warning(f"Search for {market_name} timed out after {market_timeout} seconds")
                return []
            except Exception as e:
                logger.error(f"Error searching {market_name}: {str(e)}", exc_info=True)
                return []
        
        # Execute all market searches in true parallel, with a global timeout
        overall_search_timeout = 45.0  # Increased from 15.0 seconds to 45.0 seconds
        
        logger.info(f"Starting parallel market searches with {len(search_markets)} markets and global timeout of {overall_search_timeout} seconds")
        
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
                    all_filtered_products.extend(product_list)
            
            logger.info(f"All market searches completed successfully within {overall_search_timeout} seconds")
                    
        except asyncio.TimeoutError:
            logger.warning(f"Global market search timeout after {overall_search_timeout} seconds - using partial results")
        
        logger.info(f"Collected a total of {len(all_filtered_products)} filtered products from all markets")
        
        # Sort by relevance score (already calculated during filtering)
        all_filtered_products.sort(
            key=lambda p: product_scores.get(p.get('_id', ''), 0.0),
            reverse=True
        )
        
        # Limit to max_products
        all_filtered_products = all_filtered_products[:max_products]
        
        # Create deals from products
        for product in all_filtered_products:
            try:
                # Extract deal data
                # Determine the source based on market information
                source = "scraper"  # Default fallback
                
                # Try to extract market type from URL
                market_url = product.get("url", "")
                if "amazon" in market_url.lower():
                    source = "amazon"
                elif "walmart" in market_url.lower():
                    source = "walmart"
                elif "ebay" in market_url.lower():
                    source = "ebay"
                elif "target" in market_url.lower():
                    source = "target"
                elif "bestbuy" in market_url.lower():
                    source = "bestbuy"
                elif "google" in market_url.lower():
                    source = "google_shopping"
                
                # If market_id is available, query the database to get the market name
                market_id = product.get("market_id")
                if market_id and hasattr(self, "db"):
                    try:
                        from sqlalchemy import select
                        from core.models.market import Market
                        
                        # Get market by ID
                        market_query = select(Market).where(Market.id == market_id)
                        market_result = await self.db.execute(market_query)
                        market = market_result.scalar_one_or_none()
                        
                        if market:
                            # Use market name in lowercase as source
                            source = market.name.lower()
                            logger.info(f"Using market name '{source}' as deal source")
                    except Exception as market_error:
                        logger.warning(f"Error getting market name: {str(market_error)}")
                
                # Create deal_metadata
                deal_metadata = {
                    "search_query": query
                }
                
                # Add an external_id if the product has an ID
                product_id = product.get("id")
                if product_id and isinstance(product_id, str) and product_id.strip():
                    deal_metadata["external_id"] = product_id
                else:
                    deal_metadata["external_id"] = str(uuid4())
                
                # Add any other metadata from the product
                product_metadata = product.get("metadata", {})
                if product_metadata and isinstance(product_metadata, dict):
                    deal_metadata.update(product_metadata)
                
                deal_data = {
                    "title": product.get("title", ""),
                    "description": product.get("description", ""),
                    "price": float(product.get("price", 0)),
                    "market_id": product.get("market_id"),
                    "url": product.get("url", ""),
                    "image_url": product.get("image", "") or product.get("image_url", ""),
                    "category": category or "other",
                    "status": "active",
                    "source": source,  # Use the market name in lowercase instead of hardcoded "scraper"
                    "user_id": user_id,  # Add user_id to deal_data
                    "deal_metadata": deal_metadata
                }
                
                # Create the deal
                try:
                    from core.services.deal.search.deal_creation import create_deal_from_dict
                    
                    deal_create = await self.create_deal_from_dict(deal_data)
                    if deal_create:
                        created_deals.append(deal_create)
                except Exception as e:
                    logger.error(f"Failed to create deal from product: {str(e)}")
                    continue
            except Exception as e:
                logger.error(f"Error processing product: {str(e)}")
                continue
                
        logger.info(f"Created {len(created_deals)} deals from scraped products")
        
        # Cache the results for future searches
        if redis_client and created_deals:
            try:
                # Serialize the deals
                serialized_deals = []
                for deal in created_deals:
                    deal_dict = {
                        "id": str(deal.id),
                        "title": deal.title,
                        "price": float(deal.price) if deal.price else 0,
                        "market_id": str(deal.market_id) if deal.market_id else None,
                        "url": deal.url
                    }
                    serialized_deals.append(deal_dict)
                    
                # Store in Redis with TTL
                await redis_client.set(
                    cache_key,
                    json.dumps(serialized_deals),
                    expire=3600  # Cache for 1 hour
                )
                logger.info(f"Cached {len(serialized_deals)} deals for key {cache_key}")
            except Exception as e:
                logger.error(f"Error caching search results: {str(e)}")
        
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

async def search_products(
    self,
    query: str,
    market_type: str,
    search_provider: callable,
    real_time: bool = False,
    limit: int = 25,
    **kwargs
) -> Optional[List[Dict[str, Any]]]:
    """Search for products using the specified provider.
    
    Args:
        query: Search query
        market_type: Type of market (e.g. Amazon, Walmart)
        search_provider: Function to call for search
        real_time: Whether this is a real-time search
        limit: Maximum number of results to return
        **kwargs: Additional arguments to pass to search provider
        
    Returns:
        List of products or None
    """
    try:
        logger.info(f"Searching for '{query}' in {market_type} with limit {limit}")
        
        # Set different timeouts based on market type
        timeout = 30.0  # Default timeout (increased from 20.0)
        if market_type.lower() == 'google_shopping':
            timeout = 60.0  # Extended timeout for Google Shopping to match ScraperAPI setting
        
        # Create async task for search
        task = search_provider(
            query=query,
            limit=limit,
            **kwargs
        )
        
        logger.debug(f"Created search task for {market_type} with timeout {timeout} seconds")
        
        # Call the search provider with a timeout
        try:
            products = await asyncio.wait_for(task, timeout=timeout)
            
            if products:
                logger.info(f"Successfully retrieved {len(products) if isinstance(products, list) else 'unknown'} products from {market_type}")
            else:
                logger.warning(f"No products found for '{query}' in {market_type}")
            
            return products
        except asyncio.TimeoutError:
            logger.warning(f"Search for {market_type} timed out after {timeout} seconds")
            return None
        except Exception as e:
            logger.error(f"Error searching {market_type}: {str(e)}", exc_info=True)
            return None
            
    except Exception as e:
        logger.error(f"Error in search_products for {market_type}: {str(e)}", exc_info=True)
        return None 