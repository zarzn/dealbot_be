"""ScraperAPI integration service.

This module provides integration with ScraperAPI for web scraping capabilities.
"""

from typing import Optional, Dict, Any, List, Union
import aiohttp
import asyncio
from datetime import datetime
from urllib.parse import urlencode, quote_plus, quote
from pydantic import SecretStr
import json

from core.config import settings
from core.utils.logger import get_logger
from core.exceptions.market_exceptions import (
    MarketIntegrationError,
    MarketRateLimitError,
    MarketConnectionError,
    ProductNotFoundError
)
from core.utils.redis import RedisClient

logger = get_logger(__name__)

class ScraperAPIService:
    """Service for interacting with ScraperAPI."""
    
    def __init__(
        self,
        api_key: Optional[Union[str, SecretStr]] = None,
        base_url: Optional[str] = None,
        redis_client: Optional[RedisClient] = None
    ):
        # Handle API key initialization
        if api_key is None:
            api_key = settings.SCRAPER_API_KEY
        
        if isinstance(api_key, SecretStr):
            self.api_key = api_key.get_secret_value()
        else:
            self.api_key = str(api_key)

        self.base_url = base_url or settings.SCRAPER_API_BASE_URL
        self.redis_client = redis_client or RedisClient()
        
        # Configure limits from settings
        self.concurrent_limit = settings.SCRAPER_API_CONCURRENT_LIMIT
        self.requests_per_second = settings.SCRAPER_API_REQUESTS_PER_SECOND
        self.monthly_limit = settings.SCRAPER_API_MONTHLY_LIMIT
        
        # Initialize rate limiting semaphore
        self.semaphore = asyncio.Semaphore(self.concurrent_limit)
        
        # Configure timeout
        self.timeout = aiohttp.ClientTimeout(
            total=60,  # 60 seconds total timeout
            connect=10,  # 10 seconds connection timeout
            sock_connect=10,  # 10 seconds to establish socket connection
            sock_read=30  # 30 seconds to read socket data
        )

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
                                            expire=cache_ttl
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
        if not self.redis_client:
            logger.warning("Redis client not available, skipping credit tracking")
            return
            
        try:
            credits = 5 if request_type == 'ecommerce' else 1
            date_key = datetime.utcnow().strftime('%Y-%m')
            
            async with self.redis_client.pipeline() as pipe:
                pipe.incrby(f'scraper_api:credits:{date_key}', credits)
                pipe.expire(f'scraper_api:credits:{date_key}', 60 * 60 * 24 * 35)  # 35 days
                await pipe.execute()
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
        cache_ttl: int = 1800  # 30 minutes
    ) -> List[Dict[str, Any]]:
        """Search Amazon for products matching the query."""
        logger.debug(f"Searching Amazon for query: '{query}', page: {page}")
        
        # Use the structured data endpoint
        target_url = "https://api.scraperapi.com/structured/amazon/search"
        
        params = {
            'query': query,
            'country': 'us'
        }
        
        if page > 1:
            params['page'] = str(page)

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
                elif 'data' in response and isinstance(response['data'], (list, dict)):
                    products = response['data'] if isinstance(response['data'], list) else [response['data']]
                    logger.debug("Found products in 'data' key")
                else:
                    # Log more details about the response structure
                    logger.warning(f"No recognized product array found in response. Available keys: {list(response.keys())}")
                    logger.debug("Full response structure:")
                    for key, value in response.items():
                        if isinstance(value, (list, dict)):
                            logger.debug(f"{key}: {type(value)} with {len(value)} items")
                        else:
                            logger.debug(f"{key}: {type(value)} = {value}")
            elif isinstance(response, list):
                products = response
                logger.debug("Response was directly a list of products")
            else:
                logger.error(f"Unexpected response type: {type(response)}")
                raise MarketIntegrationError(
                    market="amazon",
                    operation="search_products",
                    reason=f"Unexpected response type: {type(response)}",
                    details={'response_preview': str(response)[:500]}
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
                    
                    # Extract image URL
                    image_url = None
                    for img_field in ['image', 'main_image', 'productImage', 'image_url', 'thumbnail']:
                        if img_field in product and product[img_field]:
                            image_url = str(product[img_field])
                            break
                    
                    normalized_product = {
                        'id': product_id,
                        'asin': product_id,
                        'title': title,
                        'name': title,
                        'price': price,
                        'price_string': f"${price:.2f}",
                        'currency': 'USD',
                        'url': f"https://www.amazon.com/dp/{product_id}",
                        'market_type': 'amazon',
                        'rating': float(product.get('rating', {}).get('averageRating', product.get('averageRating', 0.0))) if isinstance(product.get('rating'), dict) else float(product.get('rating', product.get('averageRating', 0.0))),
                        'review_count': int(product.get('rating', {}).get('numberOfReviews', product.get('numberOfReviews', 0))) if isinstance(product.get('rating'), dict) else int(product.get('reviews', product.get('numberOfReviews', 0))),
                        'image_url': image_url or '',
                        'availability': bool(product.get('available', True)),
                        'metadata': {
                            'source': 'amazon',
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
            return normalized_products
            
        except Exception as e:
            logger.error(f"Amazon search failed: {str(e)}", exc_info=True)
            raise MarketIntegrationError(
                market="amazon",
                operation="search_products",
                reason=f"Search failed: {str(e)}"
            )
    
    async def get_amazon_product(
        self,
        product_id: str,
        cache_ttl: int = 1800  # 30 minutes
    ) -> Dict[str, Any]:
        """Get Amazon product details."""
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

            # Normalize the response
            normalized_product = {
                'id': product_id,
                'asin': product_id,
                'name': result.get('name'),
                'title': result.get('name'),
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
                
            return normalized_product
            
        except ProductNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Amazon product fetch failed: {str(e)}")
            raise MarketIntegrationError(
                market="amazon",
                operation="get_product",
                reason=f"Product fetch failed: {str(e)}"
            )
    
    async def search_walmart_products(
        self,
        query: str,
        page: int = 1,
        cache_ttl: int = 1800  # 30 minutes
    ) -> List[Dict[str, Any]]:
        """Search for products on Walmart."""
        try:
            # Properly encode the query for Walmart
            encoded_query = quote_plus(query)
            # Use the browse API endpoint which tends to be more reliable
            target_url = f"https://www.walmart.com/browse/search?q={encoded_query}&page={page}&sort=best_match"
            
            logger.debug(f"Searching Walmart for query: '{query}', page: {page}")
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
                    
                    normalized_product = {
                        'id': product_id,
                        'title': title,
                        'name': title,
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
            return normalized_products
            
        except Exception as e:
            logger.error(f"Walmart search failed: {str(e)}", exc_info=True)
            raise MarketIntegrationError(
                market="walmart",
                operation="search_products",
                reason=f"Search failed: {str(e)}"
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

        return {
            'id': product_id,
            'title': title,
            'name': title,
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