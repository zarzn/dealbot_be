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
from datetime import datetime

from sqlalchemy import select, or_, cast, String

from core.models.deal import Deal
from core.models.market import Market
from core.models.enums import MarketStatus
from core.services.deal.search.post_scraping_filter import (
    post_process_products,
    extract_price_constraints,
    extract_brands_from_query
)
from core.services.deal.search.query_formatter import (
    format_search_query_with_ai,
    get_optimized_query_for_marketplace,
    get_optimized_queries_for_marketplaces
)
from core.integrations.market_factory import MarketIntegrationFactory
from core.utils.logger import get_logger
from core.services.ai import get_ai_service

logger = get_logger(__name__)

# Custom JSON encoder that can handle complex structures and circular references
class SafeJSONEncoder(json.JSONEncoder):
    """JSON encoder that can handle complex structures and circular references."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seen = set()
        
    def default(self, obj):
        obj_id = id(obj)
        
        # Check for circular references
        if obj_id in self._seen:
            return str(obj)
        
        self._seen.add(obj_id)
        
        # Handle different object types
        if isinstance(obj, (datetime, UUID)):
            return str(obj)
        elif isinstance(obj, Decimal):
            return float(obj)
        elif hasattr(obj, '__dict__'):
            return {k: v for k, v in obj.__dict__.items() if not k.startswith('_')}
        
        try:
            return super().default(obj)
        except TypeError:
            return str(obj)

def safe_json_dumps(obj):
    """Safe JSON serialization that can handle circular references.
    
    Args:
        obj: Object to serialize
        
    Returns:
        JSON string representation of the object
    """
    try:
        return json.dumps(obj, cls=SafeJSONEncoder)
    except Exception as e:
        logger.warning(f"Error in safe_json_dumps: {str(e)}")
        
        # Fallback approach: Convert to simpler structure
        if isinstance(obj, dict):
            # Create a simplified version of the dictionary
            simplified = {}
            for k, v in obj.items():
                try:
                    # Attempt to serialize key and value, use string representation if it fails
                    json.dumps({k: v})
                    simplified[k] = v
                except:
                    try:
                        # Try to add just the key with a string value
                        simplified[k] = str(v)
                    except:
                        # If key cannot be serialized either, skip this pair
                        pass
            return json.dumps(simplified)
        elif isinstance(obj, list):
            # Create a simplified version of the list
            simplified = []
            for item in obj:
                try:
                    # Attempt to serialize the item
                    json.dumps(item)
                    simplified.append(item)
                except:
                    # If item cannot be serialized, use string representation
                    try:
                        simplified.append(str(item))
                    except:
                        # If even string representation fails, skip this item
                        pass
            return json.dumps(simplified)
        else:
            # For other types, return an empty structure
            return json.dumps({})

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
                    Market.is_active == True
                )
            )
        )
        
        # Get AI service for query formatting - start this early in parallel
        ai_service = None
        try:
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
        market_factory = MarketIntegrationFactory(scraper_type="oxylabs", db=self.db)
        
        # Get Redis client - try to use the one from the service if available
        if not hasattr(self, "redis_client") or self.redis_client is None:
            # If the service has a _redis attribute, use that
            if hasattr(self, "_redis") and self._redis is not None:
                redis_client = self._redis
            else:
                # Otherwise, use the one we got earlier
                redis_client = await redis_client_task
        else:
            redis_client = self.redis_client
        
        # Process markets from database
        search_markets = []
        if not markets:
            logger.warning("No markets found in database for Oxylabs integration. Only using markets from database.")
        else:
            for market in markets:
                try:
                    market_id = market.id
                    market_name = market.name
                    market_type = market.type.lower() if hasattr(market, 'type') else "unknown"
                    search_markets.append((market_name, market_type, market_id))
                except Exception as e:
                    logger.error(f"Error processing market {market.name}: {str(e)}")
        
        # Get optimized queries for all markets in a single AI request
        market_types = [market_type for _, market_type, _ in search_markets]
        try:
            optimized_queries = await get_optimized_queries_for_marketplaces(
                query, market_types, ai_service
            )
        except Exception as e:
            logger.error(f"Error getting optimized queries in batch: {str(e)}")
            # Create empty dict that will be filled with individual formatting in the market search loop
            optimized_queries = {}
        
        # Define function for market search with optimized queries and post-filtering
        async def process_market_search(market_info):
            market_name, market_type, market_id = market_info
            
            # Set a timeout based on market type
            timeout = 25.0  # Default timeout: 25 seconds
            
            # Adaptive timeouts based on market type
            if market_type.lower() == 'google_shopping':
                timeout = 60.0  # Google Shopping needs more time
            elif market_type.lower() == 'amazon':
                timeout = 60.0  # Amazon timeout
            elif market_type.lower() == 'walmart':
                timeout = 25.0  # Walmart timeout
            
            # Create a cache key specific to this market
            market_cache_key = f"{cache_key}:{market_type.lower()}"
            cached_results = None
            
            try:
                # Try to get cached results first
                if redis_client:
                    try:
                        cached_data = await redis_client.get(market_cache_key)
                        if cached_data:
                            cached_results = json.loads(cached_data)
                            logger.info(f"Using cached results for {market_type}")
                    except Exception as e:
                        # Don't attempt to reconnect to localhost if the redis_client fails
                        logger.warning(f"Error accessing Redis cache for {market_type}: {str(e)}")
                
                if cached_results:
                    # Process cached results
                    return process_products_from_results(
                        cached_results, 
                        market_type, 
                        market_id,
                        market_name
                    )
                    
                # If not cached, perform actual search
                logger.info(f"Starting search for {market_name} with timeout of {timeout} seconds")
                
                # Format query for this specific market if needed
                formatted_query = query
                if market_type.lower() in optimized_queries:
                    formatted_query = optimized_queries[market_type.lower()].get("formatted_query", query)
                    logger.info(f"Optimized query for {market_name}: '{query}' -> '{formatted_query}'")
                
                # Create search params with country/geo_location
                search_params = {
                    "limit": max_products,
                }
                
                # Only add geo_location for non-Amazon markets
                if market_type.lower() != "amazon":
                    search_params["geo_location"] = "US"  # Default location
                else:
                    logger.info(f"Skipping geo_location parameter for Amazon search")
                
                # Make the search request through the market factory
                try:
                    async with asyncio.timeout(timeout):
                        # Search for products in the specified market
                        result = await market_factory.search_products(
                            market=market_type.lower(),
                            query=formatted_query,
                            **search_params
                        )
                        
                        # Cache the result if successful
                        if result and not isinstance(result, list) and "error" not in result:
                            try:
                                if redis_client:
                                    import json  # Import json in this scope
                                    # Use safe_json_dumps to handle circular references
                                    serialized_result = safe_json_dumps(result)
                                    if serialized_result:
                                        await redis_client.setex(
                                            market_cache_key,
                                            600,  # 10 minutes TTL
                                            serialized_result
                                        )
                                        logger.info(f"Successfully cached {market_type} results")
                                    else:
                                        logger.warning(f"Could not serialize {market_type} results for caching")
                            except Exception as e:
                                logger.warning(f"Failed to cache {market_type} results: {str(e)}")
                except asyncio.TimeoutError:
                    logger.warning(f"Search for {market_type} timed out after {timeout} seconds")
                    return []
                except Exception as e:
                    logger.error(f"Error searching {market_type}: {str(e)}")
                    return []
                
                logger.info(f"Search for {market_name} completed in {time.time() - start_time:.2f} seconds")
                
                # Process the results and create deals
                # Check for OxylabsResult object - if we get one, extract just the results field
                if hasattr(result, 'results') and not isinstance(result, dict) and not isinstance(result, list):
                    logger.info(f"Got OxylabsResult object from {market_type} search, extracting results field")
                    processed_result = result.results
                else:
                    processed_result = result
                
                return process_products_from_results(
                    processed_result, 
                    market_type, 
                    market_id,
                    market_name
                )
                
            except Exception as e:
                logger.error(f"Error processing market search for {market_type}: {str(e)}")
                return []
                
        def process_products_from_results(products, market_type, market_id, market_name):
            # Check if we got valid products
            if not products:
                logger.warning(f"No products returned from {market_type}")
                return []
                
            # Extract products list from various result structures
            products_list = []
            
            # Detailed logging of product structure for debugging
            logger.debug(f"Processing {market_type} products of type {type(products)}")
            if isinstance(products, dict):
                logger.debug(f"{market_type} product keys: {list(products.keys())}")
            
            # Handle the Amazon special case
            if market_type.lower() == 'amazon':
                # Handle different Amazon response structures
                try:
                    # Log structure of the response
                    if isinstance(products, dict):
                        logger.info(f"Amazon response keys: {list(products.keys())}")
                        
                        # Direct paid/organic structure
                        if "paid" in products and isinstance(products["paid"], list):
                            logger.info(f"Found {len(products['paid'])} paid products in Amazon direct structure")
                            products_list.extend(products["paid"])
                        
                        if "organic" in products and isinstance(products["organic"], list):
                            logger.info(f"Found {len(products['organic'])} organic products in Amazon direct structure")
                            products_list.extend(products["organic"])
                        
                        # Nested content structure
                        if "content" in products and isinstance(products["content"], dict):
                            content = products["content"]
                            logger.info(f"Amazon content keys: {list(content.keys())}")
                            
                            # Direct content.results structure
                            if "results" in content and isinstance(content["results"], dict):
                                results = content["results"]
                                logger.info(f"Amazon content.results keys: {list(results.keys())}")
                                
                                if "paid" in results and isinstance(results["paid"], list):
                                    logger.info(f"Found {len(results['paid'])} paid products in content.results")
                                    products_list.extend(results["paid"])
                                
                                if "organic" in results and isinstance(results["organic"], list):
                                    logger.info(f"Found {len(results['organic'])} organic products in content.results")
                                    products_list.extend(results["organic"])
                            
                            # Direct content.organic/paid structure
                            if "paid" in content and isinstance(content["paid"], list):
                                logger.info(f"Found {len(content['paid'])} paid products in content")
                                products_list.extend(content["paid"])
                            
                            if "organic" in content and isinstance(content["organic"], list):
                                logger.info(f"Found {len(content['organic'])} organic products in content")
                                products_list.extend(content["organic"])
                        
                        # Search results in top level
                        if "results" in products and isinstance(products["results"], list):
                            logger.info(f"Found {len(products['results'])} products in direct results list")
                            products_list.extend(products["results"])
                    
                    # In case the products object is already a list
                    elif isinstance(products, list):
                        logger.info(f"Amazon products returned as direct list of {len(products)} items")
                        products_list = products
                        
                    logger.info(f"Successfully extracted {len(products_list)} Amazon products")
                    
                except Exception as e:
                    logger.error(f"Error processing Amazon products: {str(e)}", exc_info=True)
                    # Return empty list on error
                    return []
            else:
                # For other markets, use standard processing
                if isinstance(products, dict):
                    # First check for paid/organic sections
                    paid_products = []
                    organic_products = []
                    
                    if "paid" in products and isinstance(products["paid"], list):
                        paid_products = products["paid"]
                        logger.info(f"Found {len(paid_products)} paid/sponsored products from {market_name}")
                    
                    if "organic" in products and isinstance(products["organic"], list):
                        organic_products = products["organic"]
                        logger.info(f"Found {len(organic_products)} organic products from {market_name}")
                    
                    # Combine paid and organic, prioritizing organic results up to limit
                    if paid_products or organic_products:
                        # Prioritize organic results but include some sponsored if needed
                        products_list = organic_products.copy()
                        
                        # Add some paid results at the beginning if we got any
                        # but limit them to about 20% of the total desired products
                        sponsored_limit = min(len(paid_products), max(2, int(max_products * 0.2)))
                        if sponsored_limit > 0:
                            products_list = paid_products[:sponsored_limit] + products_list
                    
                    # If still no products, try standard paths
                    if not products_list:
                        # Try different paths for extracting products
                        if "results" in products:
                            results = products["results"]
                            if isinstance(results, dict):
                                # Check for nested paid/organic structure
                                if "paid" in results and isinstance(results["paid"], list):
                                    products_list.extend(results["paid"])
                                if "organic" in results and isinstance(results["organic"], list):
                                    products_list.extend(results["organic"])
                            elif isinstance(results, list):
                                products_list = results
                        elif "content" in products and isinstance(products["content"], dict):
                            content = products["content"]
                            if "products" in content and isinstance(content["products"], list):
                                products_list = content["products"]
                            elif "organic" in content and isinstance(content["organic"], list):
                                products_list = content["organic"]
                            elif "paid" in content and isinstance(content["paid"], list):
                                products_list = content["paid"]
                            elif "shopping_results" in content and isinstance(content["shopping_results"], list):
                                products_list = content["shopping_results"]
                elif isinstance(products, list):
                    # The result itself is a list of products
                    products_list = products
            
            # Log number of products found
            logger.info(f"Found {len(products_list)} raw products from {market_name}")
            
            # Apply post-scraping filters
            logger.debug(f"Applying post-scraping filters for {market_name} products")
            
            # Skip post-processing if no products were found
            if not products_list:
                logger.warning(f"No products to post-process for {market_name}")
                return []
                
            try:
                filtered_products = post_process_products(
                    products=products_list,
                    query=query,
                    min_price=min_price,
                    max_price=max_price,
                    brands=brands
                )
                
                logger.info(f"Post-filtering: {len(products_list)} -> {len(filtered_products)} products from {market_name}")
            except Exception as e:
                logger.error(f"Error in post-processing products: {str(e)}", exc_info=True)
                # If post-processing fails, return the raw products
                filtered_products = products_list
                logger.info(f"Using raw products due to post-processing failure: {len(filtered_products)} products")
            
            # Add search query and market data to products
            for product in filtered_products:
                product["search_query"] = query
                product["source"] = market_type.lower()
                product["market_type"] = market_type
                product["market_id"] = str(market_id)
                product["market_name"] = market_name
                
            # Filter out products with zero or negative prices
            valid_products = [p for p in filtered_products if 
                             "price" in p and 
                             p["price"] is not None and 
                             (isinstance(p["price"], (int, float, Decimal)) and float(p["price"]) > 0)]
            
            if len(valid_products) < len(filtered_products):
                logger.warning(f"Filtered out {len(filtered_products) - len(valid_products)} products with invalid prices from {market_name}")
            
            # Return the valid products for later processing instead of creating deals here
            return valid_products
        
        # Execute all market searches in true parallel, with a global timeout
        overall_search_timeout = 45.0  # Increased from 15.0 seconds to 45.0 seconds
        
        logger.info(f"Starting parallel market searches with {len(search_markets)} markets and global timeout of {overall_search_timeout} seconds")
        
        # Collect all products from all markets
        all_valid_products = []
        
        try:
            # Execute all market searches in parallel with a global timeout
            products_by_market = await asyncio.wait_for(
                asyncio.gather(
                    *[process_market_search(market_info) for market_info in search_markets],
                    return_exceptions=False  # We handle exceptions in the process_market_search function
                ),
                timeout=overall_search_timeout
            )
            
            # Combine products from all markets
            for market_products in products_by_market:
                if market_products:  # Skip empty lists
                    all_valid_products.extend(market_products)
            
            logger.info(f"All market searches completed successfully within {overall_search_timeout} seconds")
                    
        except asyncio.TimeoutError:
            logger.warning(f"Global market search timeout after {overall_search_timeout} seconds - using partial results")
        
        logger.info(f"Collected a total of {len(all_valid_products)} valid products from all markets")
        
        # Sort by relevance score (if available)
        if hasattr(self, 'compute_relevance_score'):
            for product in all_valid_products:
                product['_relevance_score'] = self.compute_relevance_score(product, query)
            
            all_valid_products.sort(key=lambda p: p.get('_relevance_score', 0.0), reverse=True)
        
        # Limit to max_products
        all_valid_products = all_valid_products[:max_products]
        
        # Now create deals from the products
        created_deals = []
        for product in all_valid_products:
            try:
                logger.debug(f"Creating deal from product: {product.get('title', 'Unknown')[:30]}...")
                deal = await self._create_deal_from_scraped_data(product)
                if deal:
                    created_deals.append(deal)
                else:
                    logger.warning(f"Failed to create deal from product: {product.get('title', 'Unknown')[:30]}...")
            except Exception as e:
                logger.error(f"Failed to create deal from product: {str(e)}")

        logger.info(f"Created {len(created_deals)} deals from {len(all_valid_products)} valid products")
        
        # Cache the results for future searches
        if redis_client and created_deals:
            try:
                # Serialize the deals
                import json  # Import json in this scope
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
                serialized_deals_json = safe_json_dumps(serialized_deals)
                if serialized_deals_json:
                    await redis_client.set(
                        cache_key,
                        serialized_deals_json,
                        expire=3600  # Cache for 1 hour
                    )
                    logger.info(f"Cached {len(serialized_deals)} deals for key {cache_key}")
                else:
                    logger.warning(f"Could not serialize deals for caching")
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
        
        # Check if we have a cache hit
        cache_key = f"{market_type.lower()}_search:{query}"
        use_cache = kwargs.pop('use_cache', True)
        
        # Get the redis client - try to use the one from the service if available
        redis_client = None
        if hasattr(self, "_redis") and self._redis is not None:
            redis_client = self._redis
        elif hasattr(self, "redis_client") and self.redis_client is not None:
            redis_client = self.redis_client
        
        # Try to get results from cache first
        if use_cache and redis_client:
            try:
                cached_data = await redis_client.get(cache_key)
                if cached_data:
                    try:
                        cached_products = json.loads(cached_data)
                        logger.info(f"Cache hit for {market_type} search: '{query}'")
                        return cached_products
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON in cache for {market_type}: {cache_key}")
            except Exception as e:
                logger.warning(f"Error checking cache for {market_type}: {str(e)}")
        
        # Set adaptive timeouts
        if market_type.lower() == 'google_shopping':
            timeout = 60.0  # Google Shopping needs more time (increased from 40.0)
        elif market_type.lower() == 'amazon':
            timeout = 20.0  # Amazon is usually faster
        
        logger.info(f"Starting search for {market_type} with timeout {timeout}s")
        
        try:
            # Run the search with a timeout
            async with asyncio.timeout(timeout):
                try:
                    # Execute the search
                    # If we have a max_results param, use it for limit
                    search_kwargs = kwargs.copy()
                    if 'max_results' in search_kwargs:
                        search_kwargs['limit'] = search_kwargs.pop('max_results')
                    
                    # Ensure limit is set if not already
                    if 'limit' not in search_kwargs:
                        search_kwargs['limit'] = limit
                    
                    # Make the search request
                    products = await search_provider(query, **search_kwargs)
                    
                    # Cache the results if successful
                    if products and use_cache and redis_client:
                        try:
                            # Use a reasonable cache TTL based on market
                            cache_ttl = 3600  # Default: 1 hour
                            if market_type.lower() == 'amazon':
                                cache_ttl = 1800  # 30 minutes for Amazon
                            
                            # Use safe_json_dumps to handle circular references
                            serialized_products = safe_json_dumps(products)
                            if serialized_products:
                                await redis_client.set(cache_key, serialized_products, ex=cache_ttl)
                                logger.info(f"Cached {market_type} search results with TTL {cache_ttl}s")
                            else:
                                logger.warning(f"Could not serialize {market_type} products for caching")
                        except Exception as e:
                            logger.warning(f"Error caching {market_type} search results: {str(e)}")
                    
                    return products
                except Exception as e:
                    logger.error(f"Error in {market_type} search: {str(e)}", exc_info=True)
                    return None
        except asyncio.TimeoutError:
            logger.warning(f"Search for {market_type} timed out after {timeout} seconds")
            
            # Try to use stale cache data if available
            stale_cache_key = f"{market_type.lower()}_search:{query}"
            if redis_client:
                try:
                    stale_data = await redis_client.get(stale_cache_key)
                    if stale_data:
                        try:
                            stale_products = json.loads(stale_data)
                            logger.info(f"Using stale cached data for {market_type} after timeout")
                            return stale_products
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON in stale cache for {market_type}")
                except Exception as e:
                    logger.warning(f"Error checking stale cache for {market_type}: {str(e)}")
            
            # Skip the results for this market as requested
            logger.info(f"Skipping {market_type} results for query: {query} due to timeout")
            return None
            
    except Exception as e:
        logger.error(f"Error searching {market_type}: {str(e)}", exc_info=True)
        logger.info(f"Skipping {market_type} results for query: {query} due to error")
        return None 