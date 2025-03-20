"""ScraperAPI integration service.

This module provides integration with ScraperAPI for web scraping capabilities.
"""

from typing import Optional, Dict, Any, List, Union
import aiohttp
import json
import logging
import asyncio
from datetime import datetime
import time
from urllib.parse import urlencode, quote_plus, quote

from pydantic import SecretStr
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.utils.logger import get_logger
from core.exceptions.market_exceptions import (
    MarketIntegrationError,
    MarketRateLimitError,
    MarketConnectionError,
    ProductNotFoundError
)
from core.services.redis import get_redis_service
from core.models.enums import MarketType
# Import this conditionally to avoid circular imports
from core.services.market_metrics import MarketMetricsService

logger = get_logger(__name__)

class ScraperAPIService:
    """Service for interacting with ScraperAPI."""
    
    def __init__(
        self,
        api_key: Optional[Union[str, SecretStr]] = None,
        base_url: Optional[str] = None,
        redis_client: Optional[Any] = None,
        db: Optional[AsyncSession] = None
    ):
        # Handle API key initialization
        if api_key is None:
            api_key = settings.SCRAPER_API_KEY
        
        if isinstance(api_key, SecretStr):
            self.api_key = api_key.get_secret_value()
        else:
            self.api_key = str(api_key)

        self.base_url = base_url or settings.SCRAPER_API_BASE_URL
        self.redis_client = redis_client
        self.db = db
        self.metrics_service = None
        if db:
            self.metrics_service = MarketMetricsService(db)
        # Redis client will be initialized asynchronously in the first request
        
        # Rate limiting
        self.semaphore = asyncio.Semaphore(5)  # Limit concurrent requests
        self.timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout
        
        # Configure limits from settings
        self.concurrent_limit = settings.SCRAPER_API_CONCURRENT_LIMIT
        self.requests_per_second = settings.SCRAPER_API_REQUESTS_PER_SECOND
        self.monthly_limit = settings.SCRAPER_API_MONTHLY_LIMIT

    def _get_api_key(self) -> str:
        """Get API key value, handling both string and SecretStr types."""
        if isinstance(self.api_key, SecretStr):
            return self.api_key.get_secret_value()
        return str(self.api_key)

    async def _make_request(
        self,
        target_url: str,
        params: Optional[Dict[str, Any]] = None,
        cache_ttl: Optional[int] = None,
        retries: int = 3
    ) -> Dict[str, Any]:
        """Make a request to ScraperAPI with retries and caching."""
        params = params or {}
        
        # Initialize Redis client if needed
        if self.redis_client is None:
            await self._init_redis_client()
        
        # Check if this is a structured data endpoint
        is_structured = 'structured' in target_url
        
        # For non-structured endpoints, construct the URL with parameters
        if not is_structured:
            request_params = {
                'api_key': self._get_api_key(),
                'url': target_url,
                'country_code': 'us'
            }
            request_params.update(params)
            url = f"{self.base_url}?{urlencode(request_params)}"
            # Clear params since they're now in the URL
            params = {}
        else:
            # For structured endpoints, ensure API key is in params
            if 'api_key' not in params:
                params['api_key'] = self._get_api_key()
            url = target_url

        # Check cache if TTL provided
        cached_response = None
        if cache_ttl and self.redis_client:
            try:
                cache_key = f"scraper_api:{url}:{str(params)}"
                cached_response = await self.redis_client.get(cache_key)
                if cached_response:
                    logger.debug(f"Cache hit for {url}")
                    return cached_response
            except Exception as e:
                logger.warning(f"Redis cache error (ignoring and continuing): {str(e)}")
                # Continue without caching if Redis fails

        async with self.semaphore:
            for attempt in range(retries):
                try:
                    async with aiohttp.ClientSession(timeout=self.timeout) as session:
                        logger.debug(f"Making request to ScraperAPI (attempt {attempt + 1}/{retries}): {url}")
                        logger.debug(f"Request params: {params}")
                        
                        async with session.get(url, params=params, ssl=False) as response:
                            response_text = await response.text()
                                
                        logger.debug(f"Response status: {response.status}")
                        logger.debug(f"Response headers: {dict(response.headers)}")
                        logger.debug(f"Response text preview: {response_text[:1000]}...")

                        if response.status == 200:
                            try:
                                result = await response.json()
                                logger.debug(f"Successfully parsed JSON response: {str(result)[:1000]}...")

                                # Validate response structure
                                if not isinstance(result, (dict, list)):
                                    raise MarketIntegrationError(
                                        market="scraper_api",
                                        operation="parse_response",
                                        reason=f"Invalid response type: {type(result)}",
                                        details={'response': str(result)[:500]}
                                    )

                                # Cache successful response if TTL provided
                                if cache_ttl and self.redis_client:
                                    try:
                                        await self.redis_client.set(
                                            cache_key,
                                            result,
                                            ex=cache_ttl
                                        )
                                    except Exception as e:
                                        logger.warning(f"Redis cache saving error (ignoring and continuing): {str(e)}")
                                        # Continue without caching if Redis fails

                                # Track credit usage
                                await self._track_credit_usage('ecommerce')
                                return result

                            except json.JSONDecodeError:
                                logger.error(f"Failed to parse JSON response")
                                logger.error(f"Raw response text: {response_text[:1000]}")
                                raise MarketIntegrationError(
                                    market="scraper_api",
                                    operation="parse_response",
                                    reason="Failed to parse JSON response",
                                    details={'response_text': response_text[:500]}
                                )

                        elif response.status == 429:
                            logger.warning(f"Rate limit exceeded (attempt {attempt + 1}/{retries})")
                            logger.warning(f"Response headers: {dict(response.headers)}")
                            if attempt < retries - 1:
                                wait_time = int(response.headers.get('Retry-After', 60))
                                logger.info(f"Waiting {wait_time} seconds before retry")
                                await asyncio.sleep(wait_time)
                                continue
                            raise MarketRateLimitError(
                                market="scraper_api",
                                limit=60,
                                reset_time=response.headers.get('Retry-After', '60s')
                            )
                        elif response.status == 401:
                            logger.error("Unauthorized - Invalid API key")
                            logger.error(f"API Key used: {self._get_api_key()[:5]}...")
                            raise MarketIntegrationError(
                                market="scraper_api",
                                operation="api_request",
                                reason="Unauthorized - Invalid API key"
                            )
                        elif response.status == 404:
                            logger.warning(f"Product not found - Status 404")
                            logger.warning(f"Response headers: {dict(response.headers)}")
                            raise ProductNotFoundError(
                                market="scraper_api",
                                product_id=params.get('asin', 'unknown')
                            )
                        else:
                            logger.error(f"Request failed with status {response.status}")
                            logger.error(f"Response headers: {dict(response.headers)}")
                            logger.error(f"Response text: {response_text[:1000]}")
                            raise MarketIntegrationError(
                                market="scraper_api",
                                operation="api_request",
                                reason=f"Request failed with status {response.status}",
                                details={
                                    'status': response.status,
                                    'headers': dict(response.headers),
                                    'response_text': response_text[:500]
                                }
                            )

                except asyncio.TimeoutError:
                    logger.warning(f"Request timeout (attempt {attempt + 1}/{retries})")

                    if attempt == retries - 1:
                        raise MarketConnectionError(
                            market="scraper_api",
                            reason=f"Request timed out after {retries} retries"
                        )
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff

                except Exception as e:
                    logger.error(f"Request failed (attempt {attempt + 1}/{retries}): {str(e)}")
                    if attempt == retries - 1:
                        if isinstance(e, ProductNotFoundError):
                            raise
                        raise MarketIntegrationError(
                            market="scraper_api",
                            operation="api_request",
                            reason=f"Request failed after {retries} attempts: {str(e)}",
                            details={'last_error': str(e)}
                        )
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
    
    async def _track_credit_usage(self, request_type: str = 'ecommerce'):
        """Track API credit usage."""
        # Initialize Redis client if needed
        if self.redis_client is None:
            await self._init_redis_client()
            
        if not self.redis_client:
            logger.warning("Redis client not available, skipping credit tracking")
            return
            
        try:
            credits = 5 if request_type == 'ecommerce' else 1
            date_key = datetime.utcnow().strftime('%Y-%m')
            key = f'scraper_api:credits:{date_key}'
            
            # Use direct Redis client methods instead of pipeline
            try:
                await self.redis_client.incrby(key, credits)
                await self.redis_client.expire(key, 60 * 60 * 24 * 35)  # 35 days
            except Exception as e:
                logger.warning(f"Redis credit tracking operation failed: {str(e)}")
        except Exception as e:
            logger.warning(f"Redis credit tracking error (ignoring and continuing): {str(e)}")
            # Continue without tracking if Redis fails

    async def get_credit_usage(self, date_key: Optional[str] = None) -> Optional[int]:
        """Get API credit usage for a given month.
        
        Args:
            date_key: Month to get usage for in YYYY-MM format. Defaults to current month.
            
        Returns:
            Number of credits used or None if no data found.
        """
        if not self.redis_client:
            logger.warning("Redis client not available, cannot get credit usage")
            return None
            
        try:
            if date_key is None:
                date_key = datetime.utcnow().strftime('%Y-%m')
                
            credits = await self.redis_client.get(f'scraper_api:credits:{date_key}')
            return int(credits) if credits is not None else None
        except Exception as e:
            logger.warning(f"Redis credit usage retrieval error: {str(e)}")
            return None
    
    async def search_amazon(
        self,
        query: str,
        page: int = 1,
        cache_ttl: int = 1800,  # 30 minutes
        limit: int = 15  # Explicitly limit to 15 products
    ) -> List[Dict[str, Any]]:
        """Search Amazon for products matching the query."""
        logger.debug(f"Searching Amazon for query: '{query}', page: {page}")
        
        # Use the structured data endpoint
        target_url = "https://api.scraperapi.com/structured/amazon/search"
        
        params = {
            'query': query,
            'country': 'us',
            'limit': str(limit)  # Add explicit limit parameter
        }
        
        if page > 1:
            params['page'] = str(page)

        start_time = time.time()
        success = False
        error_msg = None
        
        try:
            response = await self._make_request(
                target_url=target_url,
                params=params,
                cache_ttl=cache_ttl
            )
            
            logger.debug(f"Raw Amazon search result type: {type(response)}")
            logger.debug(f"Raw Amazon search result preview: {str(response)[:1000]}...")
            
            # Handle different response structures
            products = []
            if isinstance(response, dict):
                # Log all available top-level keys for debugging
                logger.debug(f"Available top-level keys: {list(response.keys())}")
                
                # Check for results in different possible locations
                if 'results' in response:
                    products = response['results']
                    logger.debug("Found products in 'results' key")
                elif 'products' in response:
                    products = response['products']
                    logger.debug("Found products in 'products' key")
                elif 'search_results' in response:
                    products = response['search_results']
                    logger.debug("Found products in 'search_results' key")
                elif 'data' in response and isinstance(response['data'], list):
                    products = response['data']
                    logger.debug("Found products in 'data' key")
                elif 'items' in response:
                    products = response['items'] 
                    logger.debug("Found products in 'items' key")
                else:
                    # No recognizable product list structure found
                    logger.warning(f"No recognizable product list found in response. Keys: {list(response.keys())}")
                    return []
            elif isinstance(response, list):
                # Sometimes the response is directly a list of products
                products = response
                logger.debug("Response is directly a list of products")
            else:
                logger.warning(f"Unexpected response type: {type(response)}")
                return []
                
            logger.debug(f"Found {len(products)} products before validation")
            
            if not products:
                logger.warning("No products found in the response")
                return []
                
            # Validate and normalize product data
            normalized_products = []
            error_count = 0
            
            for idx, product in enumerate(products):
                try:
                    if not isinstance(product, dict):
                        logger.warning(f"Invalid product data at index {idx}: {product}")
                        continue
                        
                    # Extract product ID (ASIN)
                    product_id = None
                    for id_field in ['asin', 'id', 'product_id', 'productId']:
                        if id_field in product:
                            product_id = str(product[id_field])
                            break
                    
                    if not product_id:
                        logger.warning(f"Product at index {idx} missing ID field")
                        continue
                        
                    # Extract title
                    title = None
                    for title_field in ['title', 'name', 'product_name', 'productName']:
                        if title_field in product and product[title_field]:
                            title = str(product[title_field]).strip()
                            break
                    
                    if not title:
                        logger.warning(f"Product {product_id} missing title field")
                        continue
                        
                    # Extract and normalize price
                    price = None
                    try:
                        for price_field in ['price', 'current_price', 'deal_price', 'list_price', 'productPrice']:
                            if price_field in product:
                                try:
                                    price_str = str(product[price_field])
                                    # Remove currency symbols and commas
                                    price_str = price_str.replace('$', '').replace(',', '').strip()
                                    # Handle ranges (take the lower price)
                                    if ' - ' in price_str:
                                        price_str = price_str.split(' - ')[0]
                                    price = float(price_str)
                                    break
                                except (ValueError, TypeError) as e:
                                    logger.debug(f"Failed to parse price '{product[price_field]}' for product {product_id}: {e}")
                                    continue
                        
                        if price is None:
                            logger.warning(f"Could not extract valid price for product {product_id}")
                            continue
                    except Exception as e:
                        logger.warning(f"Error extracting price for product {product_id}: {str(e)}")
                        continue
                    
                    # Extract original price / list price
                    original_price = None
                    try:
                        for orig_price_field in ['original_price', 'list_price', 'was_price', 'regular_price', 'msrp', 'strike_price']:
                            if orig_price_field in product and product[orig_price_field]:
                                try:
                                    orig_price_str = str(product[orig_price_field])
                                    # Remove currency symbols and commas
                                    orig_price_str = orig_price_str.replace('$', '').replace(',', '').strip()
                                    # Handle ranges (take the higher price)
                                    if ' - ' in orig_price_str:
                                        orig_price_str = orig_price_str.split(' - ')[1]
                                    original_price = float(orig_price_str)
                                    
                                    # Ensure original price is higher than current price
                                    if original_price <= price:
                                        logger.debug(f"Original price {original_price} is not higher than current price {price}, ignoring")
                                        original_price = None
                                    break
                                except (ValueError, TypeError) as e:
                                    logger.debug(f"Failed to parse original price '{product[orig_price_field]}' for product {product_id}: {e}")
                                    continue
                    except Exception as e:
                        # Non-critical error, just log and continue without original price
                        logger.debug(f"Error extracting original price for product {product_id}: {str(e)}")
                        original_price = None
                    
                    # Extract image URL
                    image_url = None
                    try:
                        for img_field in ['image', 'main_image', 'productImage', 'image_url', 'thumbnail']:
                            if img_field in product and product[img_field]:
                                image_url = str(product[img_field])
                                break
                    except Exception as e:
                        # Non-critical error, just log and continue without image URL
                        logger.debug(f"Error extracting image URL for product {product_id}: {str(e)}")
                        image_url = None
                    
                    # Extract description
                    description = None
                    try:
                        for desc_field in ['description', 'product_description', 'about', 'about_product', 'overview', 'details', 'summary']:
                            if desc_field in product and product[desc_field]:
                                # Check if it's a string or a list
                                if isinstance(product[desc_field], str) and len(product[desc_field].strip()) > 0:
                                    description = product[desc_field].strip()
                                    break
                                elif isinstance(product[desc_field], list) and len(product[desc_field]) > 0:
                                    # Join list items into a string
                                    description = " ".join([str(item) for item in product[desc_field] if item])
                                    break
                        
                        # Fallback to a generic description based on the product title if still no description
                        if not description or len(description.strip()) == 0:
                            description = f"This is a {title} available on Amazon."
                    except Exception as e:
                        # Non-critical error, just log and create a generic description
                        logger.debug(f"Error extracting description for product {product_id}: {str(e)}")
                        description = f"This is a {title} available on Amazon."
                    
                    # Add debug log to check the final description
                    logger.info(f"Final description for product {product_id}: {description[:100]}...")
                    
                    # Create normalized product
                    normalized_product = {
                        'id': product_id,
                        'asin': product_id,
                        'title': title,
                        'name': title,
                        'description': description,
                        'price': price,
                        'price_string': f"${price:.2f}",
                        'original_price': original_price,
                        'currency': 'USD',
                        'url': f"https://www.amazon.com/dp/{product_id}",
                        'market_type': 'amazon',
                        'image_url': image_url or '',
                        'metadata': {
                            'source': 'amazon',
                            'timestamp': datetime.utcnow().isoformat(),
                            'raw_fields': list(product.keys())
                        }
                    }
                    
                    normalized_products.append(normalized_product)
                    
                except Exception as e:
                    error_count += 1
                    logger.error(f"Error processing product at index {idx}: {str(e)}")
                    # Continue with next product instead of failing the entire operation
                    continue
            
            logger.info(f"Successfully normalized {len(normalized_products)} out of {len(products)} products")
            
            # Record market metrics for AMAZON
            await self._record_market_metrics(
                market_type=MarketType.AMAZON,
                success=True,
                response_time=time.time() - start_time,
                error=error_msg
            )
            
            return normalized_products[:15]
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Amazon search failed: {error_msg}")
            
            # Record market metrics for AMAZON with failure
            await self._record_market_metrics(
                market_type=MarketType.AMAZON,
                success=False,
                response_time=time.time() - start_time,
                error=error_msg
            )
            
            # Re-raise the exception
            raise
    
    async def get_amazon_product(
        self,
        product_id: str,
        cache_ttl: int = 1800  # 30 minutes
    ) -> Dict[str, Any]:
        """Get Amazon product details."""
        logger.debug(f"Getting Amazon product details for: {product_id}")
        
        # Start timing
        start_time = time.time()
        success = False
        error_msg = None
        
        try:
            target_url = "https://api.scraperapi.com/structured/amazon/product"
            
            result = await self._make_request(
                target_url,
                params={
                    'asin': product_id,
                    'country': 'us'
                },
                cache_ttl=cache_ttl
            )
            
            if not result:
                raise ProductNotFoundError(
                    market="amazon",
                    product_id=product_id
                )

            # Extract description from various potential fields
            description = None
            for field in ['description', 'product_description', 'about', 'about_product', 'overview']:
                if field in result and result[field]:
                    desc_content = result[field]
                    if isinstance(desc_content, str) and len(desc_content.strip()) > 0:
                        description = desc_content
                        logger.debug(f"Found description in field: {field}")
                        break
                    elif isinstance(desc_content, list) and desc_content:
                        description = " ".join([str(item) for item in desc_content if item])
                        logger.debug(f"Found description list in field: {field}")
                        break

            # Check product information if no description found
            if not description and 'product_information' in result and result['product_information']:
                for key, value in result['product_information'].items():
                    if 'description' in key.lower() and value:
                        description = value if isinstance(value, str) else str(value)
                        logger.debug(f"Found description in product_information: {key}")
                        break

            # Check for features if no description found
            if not description and 'features' in result and result['features']:
                features = result.get('features', [])
                if features and isinstance(features, list):
                    description = " ".join([str(feature) for feature in features if feature])
                    logger.debug("Created description from features")

            # Create generic description as last resort
            if not description or len(description.strip()) == 0:
                title = result.get('name', 'Product')
                description = f"This is a {title} available on Amazon. No detailed description is available."
                logger.debug("Created generic description")

            # Normalize the response
            normalized_product = {
                'id': product_id,
                'asin': product_id,
                'name': result.get('name'),
                'title': result.get('name'),
                'description': description,  # Include the extracted description
                'price': float(result.get('price', {}).get('current_price', 0.0)),
                'price_string': result.get('price', {}).get('current_price_string', '$0.00'),
                'currency': result.get('price', {}).get('currency', 'USD'),
                'url': f"https://www.amazon.com/dp/{product_id}",
                'market_type': 'amazon',
                'rating': float(result.get('rating', {}).get('rating', 0.0)),
                'review_count': int(result.get('rating', {}).get('count', 0)),
                'image_url': result.get('main_image', ''),
                'availability': result.get('stock_status', {}).get('in_stock', False),
                'product_information': result.get('product_information', {}),
                'metadata': {
                    'source': 'amazon',
                    'timestamp': datetime.utcnow().isoformat(),
                    'raw_fields': list(result.keys())
                }
            }
                
            # Mark as successful if we reach this point
            success = True
            
            # Record market metrics for AMAZON
            await self._record_market_metrics(
                market_type=MarketType.AMAZON,
                success=success,
                response_time=time.time() - start_time,
                error=error_msg
            )
            
            return normalized_product
            
        except ProductNotFoundError:
            raise
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Amazon product fetch failed: {error_msg}")
            
            # Record market metrics for AMAZON with failure
            await self._record_market_metrics(
                market_type=MarketType.AMAZON,
                success=False,
                response_time=time.time() - start_time,
                error=error_msg
            )
            
            # Re-raise the exception
            raise MarketIntegrationError(
                market="amazon",
                operation="get_product",
                reason=f"Product fetch failed: {error_msg}"
            )
    
    async def search_walmart_products(
        self,
        query: str,
        page: int = 1,
        cache_ttl: int = 1800,  # 30 minutes
        limit: int = 15  # Explicitly limit to 15 products
    ) -> List[Dict[str, Any]]:
        """Search Walmart for products matching the query."""
        logger.debug(f"Searching Walmart for query: '{query}', page: {page}")
        
        # Start timing
        start_time = time.time()
        success = False
        error_msg = None
        
        try:
            # Properly encode the query for Walmart
            encoded_query = quote_plus(query)
            # Use the browse API endpoint which tends to be more reliable
            target_url = f"https://www.walmart.com/browse/search?q={encoded_query}&page={page}&sort=best_match&limit={limit}"
            
            logger.debug(f"Searching Walmart for query: '{query}', page: {page}, limit: {limit}")
            logger.debug(f"Using target URL: {target_url}")
            
            result = await self._make_request(
                target_url,
                params={
                    'autoparse': 'true',
                    'render_js': 'true',
                    'country_code': 'us',
                    'keep_headers': 'true',
                    'session_number': '1'  # Helps with consistency
                },
                cache_ttl=cache_ttl
            )
            
            logger.debug(f"Raw Walmart search result type: {type(result)}")
            logger.debug(f"Raw Walmart search result preview: {str(result)[:1000]}...")
            
            # Handle different response structures
            products = []
            if isinstance(result, dict):
                # Check for results in different possible locations
                if 'items' in result:
                    products = result['items']
                    logger.debug("Found products in 'items' key")
                elif 'products' in result:
                    products = result['products']
                    logger.debug("Found products in 'products' key")
                elif 'results' in result:
                    products = result['results']
                    logger.debug("Found products in 'results' key")
                elif 'data' in result:
                    if isinstance(result['data'], list):
                        products = result['data']
                        logger.debug("Found products in 'data' key (list)")
                    elif isinstance(result['data'], dict) and 'search' in result['data']:
                        products = result['data']['search'].get('items', [])
                        logger.debug("Found products in 'data.search.items' key")
                    elif isinstance(result['data'], dict) and 'items' in result['data']:
                        products = result['data']['items']
                        logger.debug("Found products in 'data.items' key")
                else:
                    logger.warning(f"No recognized product array found in response. Available keys: {list(result.keys())}")
                    logger.debug("Full response structure:")
                    for key, value in result.items():
                        if isinstance(value, (list, dict)):
                            logger.debug(f"{key}: {type(value)} with {len(value)} items")
                        else:
                            logger.debug(f"{key}: {type(value)} = {value}")
            elif isinstance(result, list):
                products = result
                logger.debug("Response was directly a list of products")
            else:
                logger.error(f"Unexpected response type: {type(result)}")
                raise MarketIntegrationError(
                    market="walmart",
                    operation="search_products",
                    reason=f"Unexpected response type: {type(result)}",
                    details={'response_preview': str(result)[:500]}
                )
                
            logger.debug(f"Found {len(products)} products before validation")
            
            # Validate and normalize product data
            normalized_products = []
            for idx, product in enumerate(products):
                try:
                    if not isinstance(product, dict):
                        logger.warning(f"Invalid product data at index {idx}: {product}")
                        continue
                        
                    # Log available fields for debugging
                    logger.debug(f"Product {idx} available fields: {list(product.keys())}")
                    
                    # Extract product ID
                    product_id = None
                    for id_field in ['id', 'productId', 'itemId', 'product_id', 'item_id', 'sku']:
                        if id_field in product:
                            product_id = str(product[id_field])
                            break
                    
                    if not product_id:
                        logger.warning(f"Product at index {idx} missing ID field")
                        continue
                        
                    # Extract title
                    title = None
                    for title_field in ['title', 'name', 'productName', 'product_name', 'displayName']:
                        if title_field in product and product[title_field]:
                            title = str(product[title_field]).strip()
                            break
                    
                    if not title:
                        logger.warning(f"Product {product_id} missing title field")
                        continue
                        
                    # Extract and normalize price
                    price = None
                    price_info = product.get('priceInfo', product)  # Some responses nest price in priceInfo
                    for price_field in ['price', 'currentPrice', 'salePrice', 'listPrice', 'displayPrice']:
                        price_value = price_info.get(price_field)
                        if price_value:
                            try:
                                if isinstance(price_value, dict):
                                    price_str = str(price_value.get('price', price_value.get('amount', '')))
                                else:
                                    price_str = str(price_value)
                                # Remove currency symbols and commas
                                price_str = price_str.replace('$', '').replace(',', '').strip()
                                # Handle ranges (take the lower price)
                                if ' - ' in price_str:
                                    price_str = price_str.split(' - ')[0]
                                price = float(price_str)
                                break
                            except (ValueError, TypeError) as e:
                                logger.debug(f"Failed to parse price '{price_value}' for product {product_id}: {e}")
                                continue
                    
                    if price is None:
                        logger.warning(f"Could not extract valid price for product {product_id}")
                        continue
                    
                    # Extract image URL
                    image_url = None
                    for img_field in ['image', 'imageUrl', 'thumbnailUrl', 'productImage', 'image_url', 'thumbnail']:
                        if img_field in product:
                            image_url = str(product[img_field])
                            if not image_url.startswith('http'):
                                image_url = f"https:{image_url}"
                            break
                    
                    # Extract description - check multiple possible field names
                    description = None
                    for desc_field in ['description', 'product_description', 'about', 'about_product', 'overview', 'details', 'summary']:
                        if desc_field in product and product[desc_field]:
                            # Check if it's a string or a list
                            if isinstance(product[desc_field], str) and len(product[desc_field].strip()) > 0:
                                description = product[desc_field].strip()
                                logger.debug(f"Found description in field '{desc_field}': {description[:100]}...")
                                break
                            elif isinstance(product[desc_field], list) and len(product[desc_field]) > 0:
                                # Join list items into a string
                                description = " ".join([str(item) for item in product[desc_field] if item])
                                logger.debug(f"Found description in list field '{desc_field}': {description[:100]}...")
                                break
                    
                    # If no description found in primary fields, check for it in other structures
                    if not description:
                        # Check in product_information if it exists
                        if 'product_information' in product and isinstance(product['product_information'], dict):
                            for key, value in product['product_information'].items():
                                if 'description' in key.lower() and value:
                                    description = str(value)
                                    logger.debug(f"Found description in product_information.{key}: {description[:100]}...")
                                    break
                        
                        # Check in the features as a fallback
                        if not description and 'features' in product and isinstance(product['features'], list) and product['features']:
                            description = "Features: " + " ".join(str(f) for f in product['features'])
                            logger.debug(f"Using features as description fallback: {description[:100]}...")
                    
                    # Fallback to a generic description based on the product title if still no description
                    if not description:
                        description = f"Product details for {title}. Check the seller's website for more information."
                        logger.debug(f"Using generic description fallback for product {product_id}")
                    
                    # Now create the normalized product with the description included
                    normalized_product = {
                        'id': product_id,
                        'title': title,
                        'name': title,
                        'description': description,  # Include the description here
                        'price': price,
                        'price_string': f"${price:.2f}",
                        'currency': 'USD',
                        'url': f"https://www.walmart.com/ip/{product_id}",
                        'market_type': 'walmart',
                        'rating': float(product.get('average_rating', 0.0)) if product.get('average_rating') is not None else 0.0,
                        'review_count': int(product.get('review_count', 0)) if product.get('review_count') is not None else 0,
                        'image_url': image_url or '',
                        'availability': bool(product.get('available', product.get('availabilityStatus', 'Available') == 'Available')),
                        'metadata': {
                            'source': 'walmart',
                            'timestamp': datetime.utcnow().isoformat(),
                            'raw_fields': list(product.keys())
                        }
                    }
                    normalized_products.append(normalized_product)
                    
                except Exception as e:
                    logger.error(f"Error processing product at index {idx}: {str(e)}")
                    logger.error(f"Product data: {product}")
                    continue
            
            logger.info(f"Successfully normalized {len(normalized_products)} out of {len(products)} products")
            
            # Record market metrics for WALMART
            await self._record_market_metrics(
                market_type=MarketType.WALMART,
                success=True,
                response_time=time.time() - start_time,
                error=error_msg
            )
            
            return normalized_products[:50]
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Walmart search failed: {error_msg}")
            
            # Record market metrics for WALMART with failure
            await self._record_market_metrics(
                market_type=MarketType.WALMART,
                success=False,
                response_time=time.time() - start_time,
                error=error_msg
            )
            
            # Re-raise the exception
            raise MarketIntegrationError(
                market="walmart",
                operation="search_products",
                reason=f"Search failed: {error_msg}"
            )
    
    async def get_walmart_product(self, product_id: str) -> Dict[str, Any]:
        """Get Walmart product details."""
        try:
            response = await self._make_request(
                target_url="https://api.scraperapi.com/structured/walmart/product",
                params={
                    'product_id': product_id,
                    'country': 'us'
                }
            )

            if not response:
                raise ProductNotFoundError(
                    market="walmart",
                    product_id=product_id
                )

            return self._normalize_walmart_product(response)

        except Exception as e:
            logger.error(f"Walmart product fetch failed: {str(e)}")
            raise MarketIntegrationError(
                market="walmart",
                operation="get_product",
                reason=str(e)
            )
    
    def _normalize_walmart_product(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Walmart product data."""
        if not isinstance(product, dict):
            raise MarketIntegrationError(
                market="walmart",
                operation="normalize_product",
                reason="Invalid product data type"
            )

        # Extract product ID
        product_id = None
        for id_field in ['id', 'productId', 'itemId', 'product_id', 'item_id', 'sku']:
            if id_field in product:
                product_id = str(product[id_field])
                break

        if not product_id:
            raise MarketIntegrationError(
                market="walmart",
                operation="normalize_product",
                reason="Missing product ID"
            )

        # Extract title
        title = None
        for title_field in ['title', 'name', 'productName', 'product_name', 'displayName']:
            if title_field in product and product[title_field]:
                title = str(product[title_field]).strip()
                break

        if not title:
            raise MarketIntegrationError(
                market="walmart",
                operation="normalize_product",
                reason="Missing product title"
            )

        # Extract and normalize price
        price = None
        price_info = product.get('priceInfo', product)
        for price_field in ['price', 'currentPrice', 'salePrice', 'listPrice', 'displayPrice']:
            price_value = price_info.get(price_field)
            if price_value:
                try:
                    if isinstance(price_value, dict):
                        price_str = str(price_value.get('price', price_value.get('amount', '')))
                    else:
                        price_str = str(price_value)
                    price_str = price_str.replace('$', '').replace(',', '').strip()
                    if ' - ' in price_str:
                        price_str = price_str.split(' - ')[0]
                    price = float(price_str)
                    break
                except (ValueError, TypeError):
                    continue

        if price is None:
            raise MarketIntegrationError(
                market="walmart",
                operation="normalize_product",
                reason="Could not extract valid price"
            )

        # Extract image URL
        image_url = None
        for img_field in ['image', 'imageUrl', 'thumbnailUrl', 'productImage', 'image_url', 'thumbnail']:
            if img_field in product:
                image_url = str(product[img_field])
                if not image_url.startswith('http'):
                    image_url = f"https:{image_url}"
                break

        # Extract description - check multiple possible field names
        description = None
        for desc_field in ['description', 'product_description', 'about', 'about_product', 'overview', 'details', 'summary']:
            if desc_field in product and product[desc_field]:
                # Check if it's a string or a list
                if isinstance(product[desc_field], str) and len(product[desc_field].strip()) > 0:
                    description = product[desc_field].strip()
                    logger.debug(f"Found description in field '{desc_field}': {description[:100]}...")
                    break
                elif isinstance(product[desc_field], list) and len(product[desc_field]) > 0:
                    # Join list items into a string
                    description = " ".join([str(item) for item in product[desc_field] if item])
                    logger.debug(f"Found description in list field '{desc_field}': {description[:100]}...")
                    break
        
        # If no description found in primary fields, check for it in other structures
        if not description:
            # Check in product_information if it exists
            if 'product_information' in product and isinstance(product['product_information'], dict):
                for key, value in product['product_information'].items():
                    if 'description' in key.lower() and value:
                        description = str(value)
                        logger.debug(f"Found description in product_information.{key}: {description[:100]}...")
                        break
            
            # Check in the features as a fallback
            if not description and 'features' in product and isinstance(product['features'], list) and product['features']:
                description = "Features: " + " ".join(str(f) for f in product['features'])
                logger.debug(f"Using features as description fallback: {description[:100]}...")
        
        # Fallback to a generic description based on the product title if still no description
        if not description:
            description = f"Product details for {title}. Check the seller's website for more information."
            logger.debug(f"Using generic description fallback for product {product_id}")
        
        # Now create the normalized product with the description included
        normalized_product = {
            'id': product_id,
            'title': title,
            'name': title,
            'description': description,  # Include the description here
            'price': price,
            'price_string': f"${price:.2f}",
            'currency': 'USD',
            'url': f"https://www.walmart.com/ip/{product_id}",
            'market_type': 'walmart',
            'rating': float(product.get('average_rating', 0.0)) if product.get('average_rating') is not None else 0.0,
            'review_count': int(product.get('review_count', 0)) if product.get('review_count') is not None else 0,
            'image_url': image_url or '',
            'availability': bool(product.get('available', product.get('availabilityStatus', 'Available') == 'Available')),
            'metadata': {
                'source': 'walmart',
                'timestamp': datetime.utcnow().isoformat(),
                'raw_fields': list(product.keys())
            }
        }

        return normalized_product

    async def _init_redis_client(self):
        """Initialize the Redis client if it's not provided."""
        if self.redis_client is not None:
            return
        
        try:
            # Use the Redis service instead of creating a new client
            redis_service = await get_redis_service()
            
            # Test connection with a simple ping with timeout
            try:
                # Set a short timeout for ping to avoid blocking
                ping_task = asyncio.create_task(redis_service.ping())
                done, pending = await asyncio.wait([ping_task], timeout=5.0)
                
                if pending:
                    # Ping timed out
                    for task in pending:
                        task.cancel()
                    logger.error("Redis ping timed out")
                    logger.warning("Redis ping test failed, continuing without Redis")
                    self.redis_client = None
                    return
                
                # Check if ping was successful
                if ping_task in done and ping_task.result():
                    self.redis_client = redis_service
                    logger.debug("Redis client initialized successfully")
                else:
                    logger.warning("Redis ping test failed, continuing without Redis")
                    self.redis_client = None
            except asyncio.TimeoutError:
                logger.error("Redis ping timed out")
                logger.warning("Redis ping test failed, continuing without Redis")
                self.redis_client = None
            except Exception as ping_error:
                logger.warning(f"Redis ping test failed: {str(ping_error)}, continuing without Redis")
                self.redis_client = None
        
        except Exception as e:
            logger.warning(f"Failed to initialize Redis client: {str(e)}, continuing without Redis")
            self.redis_client = None

    async def _record_market_metrics(
        self,
        market_type: MarketType,
        success: bool,
        response_time: Optional[float] = None,
        error: Optional[str] = None
    ) -> None:
        """Record metrics for a market request.
        
        Args:
            market_type: Type of market (e.g., AMAZON, WALMART)
            success: Whether the request was successful
            response_time: Response time in seconds (optional)
            error: Error message if the request failed (optional)
        """
        if not self.db:
            logger.warning("Cannot record market metrics: no database session provided")
            return
            
        # Initialize metrics service if needed
        if self.metrics_service is None:
            self.metrics_service = MarketMetricsService(self.db)
            
        try:
            # Record the metrics
            await self.metrics_service.record_market_request(
                market_type=market_type,
                success=success,
                response_time=response_time,
                error=error
            )
        except Exception as e:
            logger.error(f"Failed to record market metrics: {str(e)}", exc_info=True)