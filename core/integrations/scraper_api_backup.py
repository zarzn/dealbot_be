"""ScraperAPI integration service.

This module provides integration with ScraperAPI for web scraping capabilities.
"""

from typing import Optional, Dict, Any, List, Union
import aiohttp
import json
import logging
import asyncio
from datetime import datetime, timedelta
import time
from urllib.parse import urlencode, quote_plus, quote
import random
import uuid
import re

from pydantic import SecretStr
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.utils.logger import get_logger
from core.exceptions.market_exceptions import (
    MarketIntegrationError,
    MarketRateLimitError,
    MarketConnectionError,
    ProductNotFoundError,
    MarketNotFoundError as HTTPNotFoundError,
)
from core.exceptions import ValidationError
from core.services.redis import get_redis_service
from core.models.enums import MarketType, MarketCategory

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
        db: Optional[AsyncSession] = None,
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

        # Initialize time tracking for Redis initialization attempts
        self._last_redis_init_attempt = 0
        self._last_redis_success_log = 0

        # Rate limiting - increase from 5 to 15 concurrent requests for better performance
        self.concurrent_limit = getattr(settings, "SCRAPER_API_CONCURRENT_LIMIT", 15)
        self.semaphore = asyncio.Semaphore(self.concurrent_limit)

        # Define market-specific timeouts with longer durations for slower markets
        self.timeouts = {
            MarketType.AMAZON.value.lower(): aiohttp.ClientTimeout(
                total=20
            ),  # 20 seconds for Amazon
            MarketType.GOOGLE_SHOPPING.value.lower(): aiohttp.ClientTimeout(
                total=60
            ),  # Increased to 60 seconds for Google Shopping
            MarketType.WALMART.value.lower(): aiohttp.ClientTimeout(
                total=25
            ),  # 25 seconds for Walmart
            MarketType.EBAY.value.lower(): aiohttp.ClientTimeout(
                total=30
            ),  # 30 seconds for eBay
            "default": aiohttp.ClientTimeout(total=20),  # Default timeout of 20 seconds
        }

        # Configure limits from settings
        self.requests_per_second = getattr(
            settings, "SCRAPER_API_REQUESTS_PER_SECOND", 8
        )  # Increased from 5 to 8
        self.monthly_limit = getattr(settings, "SCRAPER_API_MONTHLY_LIMIT", 100000)

        # Last request timestamp for rate limiting
        self._last_request_time = time.time()
        self._request_times = (
            []
        )  # Track recent request times for rolling window rate limiting

        # Track request times per market type for market-specific rate limiting
        self._market_request_times = {
            market_type.lower(): [] for market_type in [m.value for m in MarketType]
        }

        # Initialize lock for rate limiting access
        self._rate_limit_lock = asyncio.Lock()

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
        retries: int = 1,  # Changed from 3 to 1 to disable retries
    ) -> Dict[str, Any]:
        """Make a request to ScraperAPI with no retries and caching."""
        params = params or {}

        # Initialize Redis client if needed
        if self.redis_client is None:
            await self._init_redis_client()

        # Determine market type from URL or params
        market_type = "default"
        if "market_type" in params:
            market_type = params["market_type"].lower()
            # Remove market_type from params since it's not an API parameter
            params = {k: v for k, v in params.items() if k != "market_type"}
        elif "structured" in target_url:
            # Extract market from structured endpoint URL (e.g., amazon/search)
            parts = target_url.split("/")
            if len(parts) >= 2 and parts[-2] in [m.value.lower() for m in MarketType]:
                market_type = parts[-2].lower()

        # Apply rate limiting with market type
        await self._apply_rate_limiting(market_type)

        # Check if this is a structured data endpoint
        is_structured = "structured" in target_url

        # For non-structured endpoints, construct the URL with parameters
        if not is_structured:
            request_params = {
                "api_key": self._get_api_key(),
                "url": target_url,
                "country_code": "us",
            }
            request_params.update(params)
            url = f"{self.base_url}?{urlencode(request_params)}"
            # Clear params since they're now in the URL
            params = {}
        else:
            # For structured endpoints, ensure API key is in params
            if "api_key" not in params:
                params["api_key"] = self._get_api_key()
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

        request_start_time = time.time()

        # Get the appropriate timeout for this market type
        timeout = self.timeouts.get(market_type, self.timeouts["default"])
        logger.debug(
            f"Using timeout of {timeout.total} seconds for market type: {market_type}"
        )

        async with self.semaphore:
            for attempt in range(retries):
                try:
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        logger.debug(
                            f"Making request to ScraperAPI (attempt {attempt + 1}/{retries}): {url}"
                        )
                        logger.debug(f"Request params: {params}")

                        async with session.get(
                            url, params=params, ssl=False
                        ) as response:
                            response_text = await response.text()

                        logger.debug(f"Response status: {response.status}")

                        if response.status == 200:
                            try:
                                result = await response.json()
                                logger.debug(
                                    f"Successfully parsed JSON response: {str(result)[:1000]}..."
                                )

                                # Record request completion for rate limiting
                                self._record_request_completion(market_type=market_type)

                                # Track response time for metrics
                                response_time = time.time() - request_start_time
                                if self.metrics_service and "market_type" in params:
                                    await self._record_market_metrics(
                                        market_type=market_type,
                                        success=True,
                                        response_time=response_time,
                                        error=None,
                                    )

                                # Validate response structure
                                if not isinstance(result, (dict, list)):
                                    raise MarketIntegrationError(
                                        market="scraper_api",
                                        operation="parse_response",
                                        reason=f"Invalid response type: {type(result)}",
                                        details={"response": str(result)[:500]},
                                    )

                                # Cache successful response if TTL provided
                                if cache_ttl and self.redis_client:
                                    try:
                                        await self.redis_client.set(
                                            cache_key, result, ex=cache_ttl
                                        )
                                    except Exception as e:
                                        logger.warning(
                                            f"Redis cache saving error (ignoring and continuing): {str(e)}"
                                        )
                                        # Continue without caching if Redis fails

                                # Track credit usage
                                await self._track_credit_usage("ecommerce")
                                return result

                            except json.JSONDecodeError:
                                logger.error(f"Failed to parse JSON response")
                                logger.error(
                                    f"Raw response text: {response_text[:1000]}"
                                )
                                raise MarketIntegrationError(
                                    market="scraper_api",
                                    operation="parse_response",
                                    reason="Failed to parse JSON response",
                                    details={"response_text": response_text[:500]},
                                )

                        elif response.status == 404:
                            logger.warning(
                                f"404 Not Found error for {url} (attempt {attempt + 1}/{retries})"
                            )
                            # For structured endpoints, especially Google Shopping, a 404 often means no results
                            if "google_shopping" in url:
                                logger.info(
                                    "Google Shopping returned 404, treating as empty results"
                                )
                                # Return empty results rather than raising an exception for Google Shopping
                                return {
                                    "products": [],
                                    "status": "empty_results",
                                    "message": "No products found",
                                }

                            # For other endpoints, try again or eventually raise an error
                            if attempt < retries - 1:
                                wait_time = (
                                    2**attempt
                                )  # Exponential backoff: 1, 2, 4, 8 seconds...
                                logger.info(
                                    f"Waiting {wait_time} seconds before retry for 404 error"
                                )
                                await asyncio.sleep(wait_time)
                                continue

                            # After all retries, fail with a specific 404 error
                            raise ProductNotFoundError(
                                market=market_type,
                                product_id=params.get("query", "unknown"),
                            )

                        elif response.status == 429:
                            logger.warning(
                                f"Rate limit exceeded (attempt {attempt + 1}/{retries})"
                            )
                            logger.warning(
                                f"Response headers: {dict(response.headers)}"
                            )
                            if attempt < retries - 1:
                                wait_time = int(response.headers.get("Retry-After", 60))
                                logger.info(f"Waiting {wait_time} seconds before retry")
                                await asyncio.sleep(wait_time)
                                continue
                            raise MarketRateLimitError(
                                market="scraper_api",
                                limit=60,
                                reset_time=response.headers.get("Retry-After", "60s"),
                            )

                        elif response.status == 401:
                            logger.error("Unauthorized - Invalid API key")
                            logger.error(f"API Key used: {self._get_api_key()[:5]}...")
                            raise MarketIntegrationError(
                                market="scraper_api",
                                operation="authentication",
                                reason="Invalid API key",
                                details={"status": 401},
                            )

                        elif response.status == 500:
                            logger.error(
                                f"Server error (status 500) on attempt {attempt + 1}/{retries}"
                            )
                            if attempt < retries - 1:
                                wait_time = (
                                    2**attempt
                                )  # Exponential backoff: 1, 2, 4 seconds...
                                logger.info(
                                    f"Waiting {wait_time} seconds before retry for 500 error"
                                )
                                await asyncio.sleep(wait_time)
                                continue

                            raise MarketIntegrationError(
                                market="scraper_api",
                                operation="server_error",
                                reason=f"Server error (status 500): {response_text[:200]}",
                                details={"status": 500},
                            )

                        else:
                            logger.error(
                                f"Unexpected response status: {response.status}"
                            )
                            logger.error(f"Response text: {response_text[:500]}")

                            if attempt < retries - 1:
                                wait_time = (
                                    2**attempt
                                )  # Exponential backoff: 1, 2, 4 seconds...
                                logger.info(
                                    f"Waiting {wait_time} seconds before retry for status {response.status}"
                                )
                                await asyncio.sleep(wait_time)
                                continue

                            raise MarketIntegrationError(
                                market="scraper_api",
                                operation="api_error",
                                reason=f"Unexpected response status: {response.status}",
                                details={
                                    "status": response.status,
                                    "response": response_text[:500],
                                },
                            )

                except asyncio.TimeoutError:
                    logger.warning(
                        f"Request timed out (attempt {attempt + 1}/{retries})"
                    )
                    # Return empty results instead of retrying
                    return {
                        "shopping_results": [],
                        "status": "timeout",
                        "message": "Request timed out",
                    }

                except Exception as e:
                    logger.error(f"Error making request: {str(e)}")
                    # Return empty results instead of retrying
                    return {
                        "shopping_results": [],
                        "status": "error",
                        "message": f"Request failed: {str(e)}",
                    }

    def _record_request_completion(self, market_type="default"):
        """Record the completion of a request for rate limiting purposes.

        Args:
            market_type: The market type to record the request for
        """
        current_time = time.time()
        self._last_request_time = current_time

        # Add current time to request times
        self._request_times.append(current_time)

        # Also add to market-specific request times
        if market_type.lower() in self._market_request_times:
            self._market_request_times[market_type.lower()].append(current_time)

        # Clean up old request times (older than 10 seconds)
        cutoff_time = current_time - 10
        self._request_times = [t for t in self._request_times if t >= cutoff_time]

        # Clean up market-specific request times
        for market in self._market_request_times:
            self._market_request_times[market] = [
                t for t in self._market_request_times[market] if t >= cutoff_time
            ]

    async def _apply_rate_limiting(self, market_type="default"):
        """Apply rate limiting to avoid exceeding API limits.

        Args:
            market_type: The market type to apply rate limiting for
        """
        async with self._rate_limit_lock:
            current_time = time.time()

            # Clean up old request times (older than 10 seconds)
            cutoff_time = current_time - 10
            self._request_times = [t for t in self._request_times if t >= cutoff_time]

            # Also clean up market-specific request times
            for market in self._market_request_times:
                self._market_request_times[market] = [
                    t for t in self._market_request_times[market] if t >= cutoff_time
                ]

            # Check overall rate limits first
            # Use a rolling window of the last 1 second
            requests_last_second = len(
                [t for t in self._request_times if t >= current_time - 1]
            )

            if requests_last_second >= self.requests_per_second:
                # Calculate wait time to stay within rate limits
                # Wait until we're below the rate limit
                wait_time = 1.0 / self.requests_per_second
                logger.debug(
                    f"Global rate limiting: waiting {wait_time:.2f} seconds before next request"
                )
                await asyncio.sleep(wait_time)

            # Now check market-specific rate limits
            # Some markets like Google Shopping need more aggressive rate limiting
            market_type = market_type.lower()
            if market_type in self._market_request_times:
                market_requests = self._market_request_times[market_type]
                requests_last_second = len(
                    [t for t in market_requests if t >= current_time - 1]
                )

                # Specific limits for different markets
                market_limits = {
                    MarketType.GOOGLE_SHOPPING.value.lower(): 3,  # Limit Google Shopping to 3 req/sec
                    MarketType.AMAZON.value.lower(): 5,  # Limit Amazon to 5 req/sec
                    MarketType.WALMART.value.lower(): 4,  # Limit Walmart to 4 req/sec
                    MarketType.EBAY.value.lower(): 4,  # Limit eBay to 4 req/sec
                    "default": self.requests_per_second,  # Default to global limit
                }

                market_limit = market_limits.get(market_type, market_limits["default"])

                if requests_last_second >= market_limit:
                    wait_time = 1.0 / market_limit
                    logger.debug(
                        f"Market-specific rate limiting for {market_type}: waiting {wait_time:.2f} seconds"
                    )
                    await asyncio.sleep(wait_time)

            # Simple rate limiting - wait a bit between requests regardless
            # This helps prevent bursts that might trigger rate limits
            time_since_last_request = current_time - self._last_request_time
            if time_since_last_request < 0.1:  # Minimum 100ms between requests
                await asyncio.sleep(0.1 - time_since_last_request)

    async def _track_credit_usage(self, request_type: str = "ecommerce"):
        """Track API credit usage."""
        # Initialize Redis client if needed
        if self.redis_client is None:
            await self._init_redis_client()

        if not self.redis_client:
            logger.warning("Redis client not available, skipping credit tracking")
            return

        try:
            credits = 5 if request_type == "ecommerce" else 1
            date_key = datetime.utcnow().strftime("%Y-%m")
            key = f"scraper_api:credits:{date_key}"

            # Use direct Redis client methods instead of pipeline
            try:
                await self.redis_client.incrby(key, credits)
                await self.redis_client.expire(key, 60 * 60 * 24 * 35)  # 35 days
            except Exception as e:
                logger.warning(f"Redis credit tracking operation failed: {str(e)}")
        except Exception as e:
            logger.warning(
                f"Redis credit tracking error (ignoring and continuing): {str(e)}"
            )
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
                date_key = datetime.utcnow().strftime("%Y-%m")

            credits = await self.redis_client.get(f"scraper_api:credits:{date_key}")
            return int(credits) if credits is not None else None
        except Exception as e:
            logger.warning(f"Redis credit usage retrieval error: {str(e)}")
            return None

    async def search_amazon(
        self,
        query: str,
        page: int = 1,
        cache_ttl: int = 1800,  # 30 minutes
        limit: int = 15,  # Explicitly limit to 15 products
    ) -> List[Dict[str, Any]]:
        """Search Amazon for products matching the query."""
        logger.debug(f"Searching Amazon for query: '{query}', page: {page}")

        # Use the structured data endpoint
        target_url = "https://api.scraperapi.com/structured/amazon/search"

        params = {
            "query": query,
            "country": "us",
            "limit": str(limit),  # Add explicit limit parameter
        }

        if page > 1:
            params["page"] = str(page)

        start_time = time.time()
        success = False
        error_msg = None

        try:
            response = await self._make_request(
                target_url=target_url, params=params, cache_ttl=cache_ttl
            )

            logger.debug(f"Raw Amazon search result type: {type(response)}")
            logger.debug(f"Raw Amazon search result preview: {str(response)[:1000]}...")

            # Handle different response structures
            products = []
            if isinstance(response, dict):
                # Log all available top-level keys for debugging
                logger.debug(f"Available top-level keys: {list(response.keys())}")

                # Check for results in different possible locations
                if "results" in response:
                    products = response["results"]
                    logger.debug("Found products in 'results' key")
                elif "products" in response:
                    products = response["products"]
                    logger.debug("Found products in 'products' key")
                elif "search_results" in response:
                    products = response["search_results"]
                    logger.debug("Found products in 'search_results' key")
                elif "data" in response and isinstance(response["data"], list):
                    products = response["data"]
                    logger.debug("Found products in 'data' key")
                elif "items" in response:
                    products = response["items"]
                    logger.debug("Found products in 'items' key")
                else:
                    # No recognizable product list structure found
                    logger.warning(
                        f"No recognizable product list found in response. Keys: {list(response.keys())}"
                    )
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
                        logger.warning(
                            f"Invalid product data at index {idx}: {product}"
                        )
                        continue

                    # Extract product ID (ASIN)
                    product_id = None
                    for id_field in ["asin", "id", "product_id", "productId"]:
                        if id_field in product:
                            product_id = str(product[id_field])
                            break

                    if not product_id:
                        logger.warning(f"Product at index {idx} missing ID field")
                        continue

                    # Extract title
                    title = None
                    for title_field in ["title", "name", "product_name", "productName"]:
                        if title_field in product and product[title_field]:
                            title = str(product[title_field]).strip()
                            break

                    if not title:
                        logger.warning(f"Product {product_id} missing title field")
                        continue

                    # Extract and normalize price
                    price = None
                    try:
                        # Try multiple price fields in order of preference
                        for price_field in [
                            "price",
                            "current_price",
                            "sale_price",
                            "offer_price",
                            "min_price",
                        ]:
                            if (
                                price_field in product
                                and product[price_field] is not None
                            ):
                                try:
                                    price_str = str(product[price_field])
                                    # Handle non-numeric price strings more gracefully
                                    if price_str.lower() in [
                                        "unavailable",
                                        "n/a",
                                        "sold out",
                                        "",
                                        "null",
                                        "none",
                                    ]:
                                        continue

                                    # Remove currency symbols, commas, and whitespace
                                    price_str = re.sub(
                                        r"[^\d\.\-]",
                                        "",
                                        price_str.replace(",", "").strip(),
                                    )

                                    # Handle price ranges (take the lower price)
                                    if " - " in price_str:
                                        price_str = price_str.split(" - ")[0]

                                    # Skip empty or invalid strings
                                    if (
                                        not price_str
                                        or price_str.isspace()
                                        or "." == price_str
                                    ):
                                        continue

                                    price = float(price_str)

                                    # Validate price is reasonable
                                    if (
                                        price <= 0 or price > 1000000
                                    ):  # 1 million max price
                                        logger.debug(
                                            f"Extracted price ${price} is outside reasonable range for product {product_id}"
                                        )
                                        price = None
                                        continue

                                    break  # Exit loop once valid price is found
                                except (ValueError, TypeError) as e:
                                    logger.debug(
                                        f"Failed to parse price '{product[price_field]}' for product {product_id}: {e}"
                                    )
                                    continue

                        if price is None:
                            # Only log at a higher level for specific markets where price is critical
                            critical_markets = [
                                "amazon",
                                "walmart",
                                "bestbuy",
                                "target",
                            ]
                            market_str = (
                                product.get("source", "").lower()
                                if "source" in product
                                else ""
                            )
                            if any(market in market_str for market in critical_markets):
                                logger.warning(
                                    f"Could not extract valid price for product {product_id}"
                                )
                            else:
                                logger.debug(
                                    f"Could not extract valid price for product {product_id}"
                                )
                            continue
                    except Exception as e:
                        logger.warning(
                            f"Error extracting price for product {product_id}: {str(e)}"
                        )
                        continue

                    # Extract original price / list price
                    original_price = None
                    try:
                        for orig_price_field in [
                            "original_price",
                            "list_price",
                            "was_price",
                            "regular_price",
                            "msrp",
                            "strike_price",
                        ]:
                            if (
                                orig_price_field in product
                                and product[orig_price_field]
                            ):
                                try:
                                    orig_price_str = str(product[orig_price_field])
                                    # Remove currency symbols and commas
                                    orig_price_str = (
                                        orig_price_str.replace("$", "")
                                        .replace(",", "")
                                        .strip()
                                    )
                                    # Handle ranges (take the higher price)
                                    if " - " in orig_price_str:
                                        orig_price_str = orig_price_str.split(" - ")[1]
                                    original_price = float(orig_price_str)

                                    # Ensure original price is higher than current price
                                    if original_price <= price:
                                        logger.debug(
                                            f"Original price {original_price} is not higher than current price {price}, ignoring"
                                        )
                                        original_price = None
                                    break
                                except (ValueError, TypeError) as e:
                                    logger.debug(
                                        f"Failed to parse original price '{product[orig_price_field]}' for product {product_id}: {e}"
                                    )
                                    continue
                    except Exception as e:
                        # Non-critical error, just log and continue without original price
                        logger.debug(
                            f"Error extracting original price for product {product_id}: {str(e)}"
                        )
                        original_price = None

                    # Extract image URL
                    image_url = None
                    try:
                        for img_field in [
                            "image",
                            "main_image",
                            "productImage",
                            "image_url",
                            "thumbnail",
                        ]:
                            if img_field in product and product[img_field]:
                                image_url = str(product[img_field])
                                break
                    except Exception as e:
                        # Non-critical error, just log and continue without image URL
                        logger.debug(
                            f"Error extracting image URL for product {product_id}: {str(e)}"
                        )
                        image_url = None

                    # Extract description
                    description = None
                    try:
                        for desc_field in [
                            "description",
                            "product_description",
                            "about",
                            "about_product",
                            "overview",
                            "details",
                            "summary",
                        ]:
                            if desc_field in product and product[desc_field]:
                                # Check if it's a string or a list
                                if (
                                    isinstance(product[desc_field], str)
                                    and len(product[desc_field].strip()) > 0
                                ):
                                    description = product[desc_field].strip()
                                    break
                                elif (
                                    isinstance(product[desc_field], list)
                                    and len(product[desc_field]) > 0
                                ):
                                    # Join list items into a string
                                    description = " ".join(
                                        [
                                            str(item)
                                            for item in product[desc_field]
                                            if item
                                        ]
                                    )
                                    break

                        # Fallback to a generic description based on the product title if still no description
                        if not description or len(description.strip()) == 0:
                            description = f"This is a {title} available on Amazon."
                    except Exception as e:
                        # Non-critical error, just log and create a generic description
                        logger.debug(
                            f"Error extracting description for product {product_id}: {str(e)}"
                        )
                        description = f"This is a {title} available on Amazon."

                    # Add debug log to check the final description
                    logger.info(
                        f"Final description for product {product_id}: {description[:100]}..."
                    )

                    # Create normalized product
                    normalized_product = {
                        "id": product_id,
                        "asin": product_id,
                        "title": title,
                        "name": title,
                        "description": description,
                        "price": price,
                        "price_string": f"${price:.2f}",
                        "original_price": original_price,
                        "currency": "USD",
                        "url": f"https://www.amazon.com/dp/{product_id}",
                        "market_type": "amazon",
                        "image_url": image_url or "",
                        "metadata": {
                            "source": "amazon",
                            "timestamp": datetime.utcnow().isoformat(),
                            "raw_fields": list(product.keys()),
                        },
                    }

                    normalized_products.append(normalized_product)

                except Exception as e:
                    error_count += 1
                    logger.error(f"Error processing product at index {idx}: {str(e)}")
                    # Continue with next product instead of failing the entire operation
                    continue

            logger.info(
                f"Successfully normalized {len(normalized_products)} out of {len(products)} products"
            )

            # Record market metrics for AMAZON
            await self._record_market_metrics(
                market_type=MarketType.AMAZON,
                success=True,
                response_time=time.time() - start_time,
                error=error_msg,
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
                error=error_msg,
            )

            # Re-raise the exception
            raise

    async def get_amazon_product(
        self, product_id: str, cache_ttl: int = 1800  # 30 minutes
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
                params={"asin": product_id, "country": "us"},
                cache_ttl=cache_ttl,
            )

            if not result:
                raise ProductNotFoundError(market="amazon", product_id=product_id)

            # Extract description from various potential fields
            description = None
            for field in [
                "description",
                "product_description",
                "about",
                "about_product",
                "overview",
            ]:
                if field in result and result[field]:
                    desc_content = result[field]
                    if isinstance(desc_content, str) and len(desc_content.strip()) > 0:
                        description = desc_content
                        logger.debug(f"Found description in field: {field}")
                        break
                    elif isinstance(desc_content, list) and desc_content:
                        description = " ".join(
                            [str(item) for item in desc_content if item]
                        )
                        logger.debug(f"Found description list in field: {field}")
                        break

            # Check product information if no description found
            if (
                not description
                and "product_information" in result
                and result["product_information"]
            ):
                for key, value in result["product_information"].items():
                    if "description" in key.lower() and value:
                        description = value if isinstance(value, str) else str(value)
                        logger.debug(f"Found description in product_information: {key}")
                        break

            # Check for features if no description found
            if not description and "features" in result and result["features"]:
                features = result.get("features", [])
                if features and isinstance(features, list):
                    description = " ".join(
                        [str(feature) for feature in features if feature]
                    )
                    logger.debug("Created description from features")

            # Create generic description as last resort
            if not description or len(description.strip()) == 0:
                title = result.get("name", "Product")
                description = f"This is a {title} available on Amazon. No detailed description is available."
                logger.debug("Created generic description")

            # Normalize the response
            normalized_product = {
                "id": product_id,
                "asin": product_id,
                "name": result.get("name"),
                "title": result.get("name"),
                "description": description,  # Include the extracted description
                "price": float(result.get("price", {}).get("current_price", 0.0)),
                "price_string": result.get("price", {}).get(
                    "current_price_string", "$0.00"
                ),
                "currency": result.get("price", {}).get("currency", "USD"),
                "url": f"https://www.amazon.com/dp/{product_id}",
                "market_type": "amazon",
                "rating": float(result.get("rating", {}).get("rating", 0.0)),
                "review_count": int(result.get("rating", {}).get("count", 0)),
                "image_url": result.get("main_image", ""),
                "availability": result.get("stock_status", {}).get("in_stock", False),
                "product_information": result.get("product_information", {}),
                "metadata": {
                    "source": "amazon",
                    "timestamp": datetime.utcnow().isoformat(),
                    "raw_fields": list(result.keys()),
                },
            }

            # Mark as successful if we reach this point
            success = True

            # Record market metrics for AMAZON
            await self._record_market_metrics(
                market_type=MarketType.AMAZON,
                success=success,
                response_time=time.time() - start_time,
                error=error_msg,
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
                error=error_msg,
            )

            # Re-raise the exception
            raise MarketIntegrationError(
                market="amazon",
                operation="get_product",
                reason=f"Product fetch failed: {error_msg}",
            )

    async def search_walmart_products(
        self,
        query: str,
        page: int = 1,
        cache_ttl: int = 1800,  # 30 minutes
        limit: int = 15,  # Explicitly limit to 15 products
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

            logger.debug(
                f"Searching Walmart for query: '{query}', page: {page}, limit: {limit}"
            )
            logger.debug(f"Using target URL: {target_url}")

            result = await self._make_request(
                target_url,
                params={
                    "autoparse": "true",
                    "render_js": "true",
                    "country_code": "us",
                    "keep_headers": "true",
                    "session_number": "1",  # Helps with consistency
                },
                cache_ttl=cache_ttl,
            )

            logger.debug(f"Raw Walmart search result type: {type(result)}")
            logger.debug(f"Raw Walmart search result preview: {str(result)[:1000]}...")

            # Handle different response structures
            products = []
            if isinstance(result, dict):
                # Check for results in different possible locations
                if "items" in result:
                    products = result["items"]
                    logger.debug("Found products in 'items' key")
                elif "products" in result:
                    products = result["products"]
                    logger.debug("Found products in 'products' key")
                elif "results" in result:
                    products = result["results"]
                    logger.debug("Found products in 'results' key")
                elif "data" in result:
                    if isinstance(result["data"], list):
                        products = result["data"]
                        logger.debug("Found products in 'data' key (list)")
                    elif (
                        isinstance(result["data"], dict) and "search" in result["data"]
                    ):
                        products = result["data"]["search"].get("items", [])
                        logger.debug("Found products in 'data.search.items' key")
                    elif isinstance(result["data"], dict) and "items" in result["data"]:
                        products = result["data"]["items"]
                        logger.debug("Found products in 'data.items' key")
                else:
                    logger.warning(
                        f"No recognized product array found in response. Available keys: {list(result.keys())}"
                    )
                    logger.debug("Full response structure:")
                    for key, value in result.items():
                        if isinstance(value, (list, dict)):
                            logger.debug(
                                f"{key}: {type(value)} with {len(value)} items"
                            )
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
                    details={"response_preview": str(result)[:500]},
                )

            logger.debug(f"Found {len(products)} products before validation")

            # Validate and normalize product data
            normalized_products = []
            for idx, product in enumerate(products):
                try:
                    if not isinstance(product, dict):
                        logger.warning(
                            f"Invalid product data at index {idx}: {product}"
                        )
                        continue

                    # Log available fields for debugging
                    logger.debug(
                        f"Product {idx} available fields: {list(product.keys())}"
                    )

                    # Extract product ID
                    product_id = None
                    for id_field in [
                        "id",
                        "productId",
                        "itemId",
                        "product_id",
                        "item_id",
                        "sku",
                    ]:
                        if id_field in product:
                            product_id = str(product[id_field])
                            break

                    if not product_id:
                        logger.warning(f"Product at index {idx} missing ID field")
                        continue

                    # Extract title
                    title = None
                    for title_field in [
                        "title",
                        "name",
                        "productName",
                        "product_name",
                        "displayName",
                    ]:
                        if title_field in product and product[title_field]:
                            title = str(product[title_field]).strip()
                            break

                    if not title:
                        logger.warning(f"Product {product_id} missing title field")
                        continue

                    # Extract and normalize price
                    price = None
                    price_info = product.get(
                        "priceInfo", product
                    )  # Some responses nest price in priceInfo
                    for price_field in [
                        "price",
                        "currentPrice",
                        "salePrice",
                        "listPrice",
                        "displayPrice",
                    ]:
                        price_value = price_info.get(price_field)
                        if price_value:
                            try:
                                if isinstance(price_value, dict):
                                    price_str = str(
                                        price_value.get(
                                            "price", price_value.get("amount", "")
                                        )
                                    )
                                else:
                                    price_str = str(price_value)
                                # Remove currency symbols and commas
                                price_str = (
                                    price_str.replace("$", "").replace(",", "").strip()
                                )
                                # Handle ranges (take the lower price)
                                if " - " in price_str:
                                    price_str = price_str.split(" - ")[0]
                                price = float(price_str)
                                break
                            except (ValueError, TypeError) as e:
                                logger.debug(
                                    f"Failed to parse price '{price_value}' for product {product_id}: {e}"
                                )
                                continue

                    if price is None:
                        logger.warning(
                            f"Could not extract valid price for product {product_id}"
                        )
                        continue

                    # Extract image URL
                    image_url = None
                    for img_field in [
                        "image",
                        "imageUrl",
                        "thumbnailUrl",
                        "productImage",
                        "image_url",
                        "thumbnail",
                    ]:
                        if img_field in product:
                            image_url = str(product[img_field])
                            if not image_url.startswith("http"):
                                image_url = f"https:{image_url}"
                            break

                    # Extract description - check multiple possible field names
                    description = None
                    for desc_field in [
                        "description",
                        "product_description",
                        "about",
                        "about_product",
                        "overview",
                        "details",
                        "summary",
                    ]:
                        if desc_field in product and product[desc_field]:
                            # Check if it's a string or a list
                            if (
                                isinstance(product[desc_field], str)
                                and len(product[desc_field].strip()) > 0
                            ):
                                description = product[desc_field].strip()
                                logger.debug(
                                    f"Found description in field '{desc_field}': {description[:100]}..."
                                )
                                break
                            elif (
                                isinstance(product[desc_field], list)
                                and len(product[desc_field]) > 0
                            ):
                                # Join list items into a string
                                description = " ".join(
                                    [str(item) for item in product[desc_field] if item]
                                )
                                logger.debug(
                                    f"Found description in list field '{desc_field}': {description[:100]}..."
                                )
                                break

                    # If no description found in primary fields, check for it in other structures
                    if not description:
                        # Check in product_information if it exists
                        if "product_information" in product and isinstance(
                            product["product_information"], dict
                        ):
                            for key, value in product["product_information"].items():
                                if "description" in key.lower() and value:
                                    description = str(value)
                                    logger.debug(
                                        f"Found description in product_information.{key}: {description[:100]}..."
                                    )
                                    break

                        # Check in the features as a fallback
                        if (
                            not description
                            and "features" in product
                            and isinstance(product["features"], list)
                            and product["features"]
                        ):
                            description = "Features: " + " ".join(
                                str(f) for f in product["features"]
                            )
                            logger.debug(
                                f"Using features as description fallback: {description[:100]}..."
                            )

                    # Fallback to a generic description based on the product title if still no description
                    if not description:
                        description = f"Product details for {title}. Check the seller's website for more information."
                        logger.debug(
                            f"Using generic description fallback for product {product_id}"
                        )

                    # Now create the normalized product with the description included
                    normalized_product = {
                        "id": product_id,
                        "title": title,
                        "name": title,
                        "description": description,  # Include the description here
                        "price": price,
                        "price_string": f"${price:.2f}",
                        "currency": "USD",
                        "url": f"https://www.walmart.com/ip/{product_id}",
                        "market_type": "walmart",
                        "rating": (
                            float(product.get("average_rating", 0.0))
                            if product.get("average_rating") is not None
                            else 0.0
                        ),
                        "review_count": (
                            int(product.get("review_count", 0))
                            if product.get("review_count") is not None
                            else 0
                        ),
                        "image_url": image_url or "",
                        "availability": bool(
                            product.get(
                                "available",
                                product.get("availabilityStatus", "Available")
                                == "Available",
                            )
                        ),
                        "metadata": {
                            "source": "walmart",
                            "timestamp": datetime.utcnow().isoformat(),
                            "raw_fields": list(product.keys()),
                        },
                    }
                    normalized_products.append(normalized_product)

                except Exception as e:
                    logger.error(f"Error processing product at index {idx}: {str(e)}")
                    logger.error(f"Product data: {product}")
                    continue

            logger.info(
                f"Successfully normalized {len(normalized_products)} out of {len(products)} products"
            )

            # Record market metrics for WALMART
            await self._record_market_metrics(
                market_type=MarketType.WALMART,
                success=True,
                response_time=time.time() - start_time,
                error=error_msg,
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
                error=error_msg,
            )

            # Re-raise the exception
            raise MarketIntegrationError(
                market="walmart",
                operation="search_products",
                reason=f"Search failed: {error_msg}",
            )

    async def get_walmart_product(self, product_id: str) -> Dict[str, Any]:
        """Get Walmart product details."""
        try:
            response = await self._make_request(
                target_url="https://api.scraperapi.com/structured/walmart/product",
                params={"product_id": product_id, "country": "us"},
            )

            if not response:
                raise ProductNotFoundError(market="walmart", product_id=product_id)

            return self._normalize_walmart_product(response)

        except Exception as e:
            logger.error(f"Walmart product fetch failed: {str(e)}")
            raise MarketIntegrationError(
                market="walmart", operation="get_product", reason=str(e)
            )

    def _normalize_walmart_product(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Walmart product data."""
        if not isinstance(product, dict):
            raise MarketIntegrationError(
                market="walmart",
                operation="normalize_product",
                reason="Invalid product data type",
            )

        # Extract product ID
        product_id = None
        for id_field in ["id", "productId", "itemId", "product_id", "item_id", "sku"]:
            if id_field in product:
                product_id = str(product[id_field])
                break

        if not product_id:
            raise MarketIntegrationError(
                market="walmart",
                operation="normalize_product",
                reason="Missing product ID",
            )

        # Extract title
        title = None
        for title_field in [
            "title",
            "name",
            "productName",
            "product_name",
            "displayName",
        ]:
            if title_field in product and product[title_field]:
                title = str(product[title_field]).strip()
                break

        if not title:
            raise MarketIntegrationError(
                market="walmart",
                operation="normalize_product",
                reason="Missing product title",
            )

        # Extract and normalize price
        price = None
        price_info = product.get("priceInfo", product)
        for price_field in [
            "price",
            "currentPrice",
            "salePrice",
            "listPrice",
            "displayPrice",
        ]:
            price_value = price_info.get(price_field)
            if price_value:
                try:
                    if isinstance(price_value, dict):
                        price_str = str(
                            price_value.get("price", price_value.get("amount", ""))
                        )
                    else:
                        price_str = str(price_value)
                    price_str = price_str.replace("$", "").replace(",", "").strip()
                    if " - " in price_str:
                        price_str = price_str.split(" - ")[0]
                    price = float(price_str)
                    break
                except (ValueError, TypeError):
                    continue

        if price is None:
            raise MarketIntegrationError(
                market="walmart",
                operation="normalize_product",
                reason="Could not extract valid price",
            )

        # Extract image URL
        image_url = None
        for img_field in [
            "image",
            "imageUrl",
            "thumbnailUrl",
            "productImage",
            "image_url",
            "thumbnail",
        ]:
            if img_field in product:
                image_url = str(product[img_field])
                if not image_url.startswith("http"):
                    image_url = f"https:{image_url}"
                break

        # Extract description - check multiple possible field names
        description = None
        for desc_field in [
            "description",
            "product_description",
            "about",
            "about_product",
            "overview",
            "details",
            "summary",
        ]:
            if desc_field in product and product[desc_field]:
                # Check if it's a string or a list
                if (
                    isinstance(product[desc_field], str)
                    and len(product[desc_field].strip()) > 0
                ):
                    description = product[desc_field].strip()
                    logger.debug(
                        f"Found description in field '{desc_field}': {description[:100]}..."
                    )
                    break
                elif (
                    isinstance(product[desc_field], list)
                    and len(product[desc_field]) > 0
                ):
                    # Join list items into a string
                    description = " ".join(
                        [str(item) for item in product[desc_field] if item]
                    )
                    logger.debug(
                        f"Found description in list field '{desc_field}': {description[:100]}..."
                    )
                    break

        # If no description found in primary fields, check for it in other structures
        if not description:
            # Check in product_information if it exists
            if "product_information" in product and isinstance(
                product["product_information"], dict
            ):
                for key, value in product["product_information"].items():
                    if "description" in key.lower() and value:
                        description = str(value)
                        logger.debug(
                            f"Found description in product_information.{key}: {description[:100]}..."
                        )
                        break

            # Check in the features as a fallback
            if (
                not description
                and "features" in product
                and isinstance(product["features"], list)
                and product["features"]
            ):
                description = "Features: " + " ".join(
                    str(f) for f in product["features"]
                )
                logger.debug(
                    f"Using features as description fallback: {description[:100]}..."
                )

        # Fallback to a generic description based on the product title if still no description
        if not description:
            description = f"Product details for {title}. Check the seller's website for more information."
            logger.debug(f"Using generic description fallback for product {product_id}")

        # Now create the normalized product with the description included
        normalized_product = {
            "id": product_id,
            "title": title,
            "name": title,
            "description": description,  # Include the description here
            "price": price,
            "price_string": f"${price:.2f}",
            "currency": "USD",
            "url": f"https://www.walmart.com/ip/{product_id}",
            "market_type": "walmart",
            "rating": (
                float(product.get("average_rating", 0.0))
                if product.get("average_rating") is not None
                else 0.0
            ),
            "review_count": (
                int(product.get("review_count", 0))
                if product.get("review_count") is not None
                else 0
            ),
            "image_url": image_url or "",
            "availability": bool(
                product.get(
                    "available",
                    product.get("availabilityStatus", "Available") == "Available",
                )
            ),
            "metadata": {
                "source": "walmart",
                "timestamp": datetime.utcnow().isoformat(),
                "raw_fields": list(product.keys()),
            },
        }

        return normalized_product

    async def _init_redis_client(self):
        """Initialize the Redis client if it's not provided."""
        if self.redis_client is not None:
            return

        # Add rate limiting to prevent excessive Redis initialization attempts
        if (
            hasattr(self, "_last_redis_init_attempt")
            and time.time() - self._last_redis_init_attempt < 30
        ):
            # Only attempt redis initialization every 30 seconds to prevent log spam
            return

        self._last_redis_init_attempt = time.time()

        try:
            # Use the Redis service instead of creating a new client
            redis_service = await get_redis_service()

            # Check if redis_service is not None before using it
            if redis_service is None:
                logger.debug("Redis service is None, continuing without Redis")
                self.redis_client = None
                return

            # Check if the _client attribute exists and is not None
            if not hasattr(redis_service, "_client") or redis_service._client is None:
                logger.debug("Redis service client is None, continuing without Redis")
                self.redis_client = None
                return

            # Test connection with a simple ping with timeout
            try:
                # Set a longer timeout for ping to avoid blocking (2 seconds instead of 1)
                ping_task = asyncio.create_task(redis_service.ping())
                done, pending = await asyncio.wait([ping_task], timeout=2.0)

                if pending:
                    # Ping timed out
                    for task in pending:
                        task.cancel()
                    logger.debug(
                        "Redis ping test failed: timeout after 2 seconds, continuing without Redis"
                    )
                    self.redis_client = None
                    return

                # Check if ping was successful
                if ping_task in done and ping_task.result():
                    self.redis_client = redis_service
                    # Only log successful initialization once every few minutes
                    if (
                        not hasattr(self, "_last_redis_success_log")
                        or time.time() - self._last_redis_success_log > 300
                    ):
                        logger.info(
                            "Redis client initialized successfully for ScraperAPIService"
                        )
                        self._last_redis_success_log = time.time()
                else:
                    logger.debug(
                        "Redis ping test failed: ping returned false, continuing without Redis"
                    )
                    self.redis_client = None
            except asyncio.TimeoutError:
                logger.debug(
                    "Redis ping test failed: TimeoutError, continuing without Redis"
                )
                self.redis_client = None
            except ConnectionRefusedError:
                logger.debug(
                    "Redis ping test failed: ConnectionRefusedError, continuing without Redis"
                )
                self.redis_client = None
            except Exception as ping_error:
                logger.debug(
                    f"Redis ping test failed: {str(ping_error)}, continuing without Redis"
                )
                self.redis_client = None

        except Exception as e:
            logger.debug(
                f"Failed to initialize Redis client: {str(e)}, continuing without Redis"
            )
            self.redis_client = None

    async def _record_market_metrics(
        self,
        market_type: MarketType,
        success: bool,
        response_time: Optional[float] = None,
        error: Optional[str] = None,
    ) -> None:
        """Record marketplace metrics for monitoring and optimization.

        Args:
            market_type: The market type enum value
            success: Whether the operation was successful
            response_time: Optional response time in seconds
            error: Optional error message if operation failed
        """
        try:
            # Check if we have a database session
            if self.db is None:
                logger.debug(
                    "Cannot record market metrics: no database session provided"
                )
                return

            # Check if we have a metrics service or need to initialize it
            if self.metrics_service is None:
                try:
                    # Initialize metrics service
                    from core.services.market_metrics import MarketMetricsService

                    self.metrics_service = MarketMetricsService(self.db)
                    logger.debug(
                        f"Initialized market metrics service for {market_type.value}"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to initialize market metrics service: {str(e)}"
                    )
                    return

            # Record the metrics
            result = await self.metrics_service.record_market_request(
                market_type=market_type,
                success=success,
                response_time=response_time,
            )

            if result:
                logger.debug(
                    f"Successfully recorded market metrics for {market_type.value}"
                )
            else:
                logger.warning(
                    f"Failed to record market metrics for {market_type.value}"
                )

        except Exception as e:
            # Don't let metrics recording failures disrupt the main flow
            logger.warning(
                f"Error recording market metrics for {market_type.value}: {str(e)}"
            )
            # Continue execution - metrics recording should never block main functionality

    async def search_google_shopping(
        self,
        search_query: str,
        page: int = 1,
        cache_ttl: int = 3600,
        results_limit: int = 5,
        limit: Optional[int] = None,
    ) -> Optional[List[Dict[str, Any]]]:
        """Search Google Shopping for products matching the query.

        Args:
            search_query: The search query
            page: The page number (default: 1)
            cache_ttl: Time to live for cached results in seconds (default: 1 hour)
            results_limit: Maximum number of results to return (default: 5)
            limit: Alternative name for results_limit for backwards compatibility

        Returns:
            List of normalized product dictionaries or None if search failed
        """
        # Handle empty search query
        if not search_query or not search_query.strip():
            logger.error("Empty search query provided for Google Shopping search")
            return None

        # Use limit parameter if provided (for backward compatibility)
        if limit is not None:
            results_limit = limit

        logger.info(f"Searching Google Shopping for: {search_query}")

        # Check if results are cached
        redis_service = await get_redis_service()
        redis_client = redis_service._client if redis_service else None

        if redis_client:
            try:
                cache_key = f"google_shopping:{search_query.lower()}:page{page}"
                cached_data = await redis_service.get(cache_key)
                if cached_data:
                    logger.info(
                        f"Using cached Google Shopping results for query: {search_query}"
                    )
                    products = json.loads(cached_data)
                    return products[:results_limit] if results_limit else products
            except Exception as e:
                logger.warning(f"Error retrieving cached results: {str(e)}")

        # Set up parameters for the API request
        target_url = "https://api.scraperapi.com/structured/google/shopping"
        params = {
            "api_key": self._get_api_key(),
            "query": search_query,
            "country_code": "us",
            "tld": "com",
        }

        start_time = time.time()
        timeout = 60  # Use a 60-second timeout for Google Shopping

        try:
            logger.debug(f"Making request to: {target_url}")
            logger.debug(f"With params: {params}")

            # Make a single request with no retries
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get(
                        target_url, params=params, timeout=timeout
                    ) as response:
                        response_time = time.time() - start_time
                        logger.debug(
                            f"Response received in {response_time:.2f} seconds with status: {response.status}"
                        )

                        if response.status == 200:
                            data = await response.json()

                            # Extract shopping results
                            if "shopping_results" in data:
                                products = data.get("shopping_results", [])

                                # Normalize the products
                                normalized_products = (
                                    await self._normalize_google_shopping_products(
                                        products, search_query
                                    )
                                )

                                # Limit results if needed
                                if (
                                    results_limit
                                    and normalized_products
                                    and len(normalized_products) > results_limit
                                ):
                                    normalized_products = normalized_products[
                                        :results_limit
                                    ]

                                # Cache the results if we have a Redis client
                                if redis_client and normalized_products:
                                    try:
                                        await redis_service.set(
                                            cache_key,
                                            json.dumps(normalized_products),
                                            ex=cache_ttl,
                                        )
                                        logger.debug(
                                            f"Cached Google Shopping results for query: {search_query}"
                                        )
                                    except Exception as cache_error:
                                        logger.warning(
                                            f"Error caching results: {str(cache_error)}"
                                        )

                                # Track the market metrics
                                await self._record_market_metrics(
                                    market_type=MarketType.GOOGLE_SHOPPING,
                                    success=True,
                                    response_time=response_time,
                                    error=None,
                                )

                                return normalized_products
                            else:
                                logger.warning(
                                    f"Unexpected response structure: {list(data.keys())}"
                                )

                                # Record market metrics with failure
                                await self._record_market_metrics(
                                    market_type=MarketType.GOOGLE_SHOPPING,
                                    success=False,
                                    response_time=response_time,
                                    error="No shopping_results in response",
                                )

                                return []
                        else:
                            error_text = await response.text()
                            error_msg = f"Error response ({response.status}): {error_text[:200]}"
                            logger.error(error_msg)

                            # Record market metrics with failure
                            await self._record_market_metrics(
                                market_type=MarketType.GOOGLE_SHOPPING,
                                success=False,
                                response_time=response_time,
                                error=error_msg,
                            )

                            return []

                except asyncio.TimeoutError:
                    logger.error(f"Request timed out after {timeout} seconds")

                    # Record market metrics with failure
                    await self._record_market_metrics(
                        market_type=MarketType.GOOGLE_SHOPPING,
                        success=False,
                        response_time=time.time() - start_time,
                        error="Request timed out",
                    )

                    return []

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error searching Google Shopping: {error_msg}")

            # Record market metrics with failure
            await self._record_market_metrics(
                market_type=MarketType.GOOGLE_SHOPPING,
                success=False,
                response_time=time.time() - start_time,
                error=error_msg,
            )

            return []

    async def _normalize_google_shopping_products(
        self, products: List[Dict[str, Any]], query: str
    ) -> List[Dict[str, Any]]:
        """Normalize Google Shopping product data into standard format.

        Args:
            products: List of raw products from Google Shopping API
            query: Original search query

        Returns:
            List of normalized product dictionaries
        """
        if not products:
            return []

        normalized_products = []
        from core.models.enums import MarketCategory

        for i, product in enumerate(products):
            try:
                # Extract common fields with better error handling
                product_id = None

                # Ensure we have a valid product ID
                if "product_id" in product and product["product_id"]:
                    product_id = str(product["product_id"])
                elif "id" in product and product["id"]:
                    product_id = str(product["id"])

                # If still no valid ID, generate a UUID
                if not product_id or product_id == "null" or product_id == "undefined":
                    logger.warning(
                        f"Invalid product ID for item {i}, generating new UUID"
                    )
                    product_id = str(uuid.uuid4())

                # Extract product title/name
                title = None
                if "title" in product and product["title"]:
                    title = str(product["title"]).strip()
                elif "name" in product and product["name"]:
                    title = str(product["name"]).strip()

                if not title or title == "null" or title == "undefined":
                    logger.warning(
                        f"Missing or invalid title for product {product_id}, skipping"
                    )
                    continue

                # Extract and normalize price
                price = None
                price_str = product.get("price", "")

                # If price is not available, try alternative fields
                if not price_str:
                    for price_field in [
                        "current_price",
                        "sale_price",
                        "discounted_price",
                        "offered_price",
                    ]:
                        if price_field in product and product[price_field]:
                            price_str = product[price_field]
                            logger.debug(
                                f"Using alternative price field: {price_field}"
                            )
                            break

                try:
                    if isinstance(price_str, (int, float)):
                        price = float(price_str)
                    elif isinstance(price_str, dict) and "value" in price_str:
                        # Handle nested price objects like {'value': 19.99, 'currency': 'USD'}
                        price_value = price_str.get("value")
                        if isinstance(price_value, (int, float)):
                            price = float(price_value)
                        elif isinstance(price_value, str) and price_value:
                            # Try to parse string value
                            clean_price = (
                                price_value.replace("$", "")
                                .replace("£", "")
                                .replace("€", "")
                                .replace(",", "")
                                .strip()
                            )
                            import re

                            digits = re.findall(r"[\d.]+", clean_price)
                            if digits:
                                price = float(digits[0])
                    elif isinstance(price_str, str) and price_str:
                        # Remove currency symbols, commas, and other non-numeric characters
                        clean_price = (
                            price_str.replace("$", "")
                            .replace("£", "")
                            .replace("€", "")
                            .replace(",", "")
                            .strip()
                        )

                        # Handle price ranges (take the lower price)
                        if " - " in clean_price:
                            clean_price = clean_price.split(" - ")[0].strip()
                        elif " to " in clean_price.lower():
                            clean_price = clean_price.lower().split(" to ")[0].strip()

                        # Try to extract digits and decimal point
                        import re

                        digits = re.findall(r"[\d.]+", clean_price)
                        if digits:
                            price = float(digits[0])
                except (ValueError, TypeError) as e:
                    logger.warning(
                        f"Failed to parse price '{price_str}' for product {product_id}: {e}"
                    )

                # Try to fallback to integer price fields if string parsing failed
                if price is None:
                    for alt_price_field in [
                        "price_cents",
                        "price_amount",
                        "cents",
                        "amount",
                    ]:
                        if alt_price_field in product and isinstance(
                            product[alt_price_field], (int, float)
                        ):
                            cents_value = float(product[alt_price_field])
                            # If it's in cents (value over 100), convert to dollars
                            if cents_value > 100:
                                price = cents_value / 100
                            else:
                                price = cents_value
                            logger.info(
                                f"Using alternative price field {alt_price_field}: {price}"
                            )
                            break

                # Last resort fallbacks for specific API responses
                if (
                    price is None
                    and "pricing" in product
                    and isinstance(product["pricing"], dict)
                ):
                    pricing_obj = product["pricing"]
                    for price_key in [
                        "current_price",
                        "sale_price",
                        "regular_price",
                        "price",
                    ]:
                        if (
                            price_key in pricing_obj
                            and pricing_obj[price_key] is not None
                        ):
                            try:
                                if isinstance(pricing_obj[price_key], (int, float)):
                                    price = float(pricing_obj[price_key])
                                elif (
                                    isinstance(pricing_obj[price_key], str)
                                    and pricing_obj[price_key].strip()
                                ):
                                    clean_price = (
                                        pricing_obj[price_key]
                                        .replace("$", "")
                                        .replace("£", "")
                                        .replace("€", "")
                                        .replace(",", "")
                                        .strip()
                                    )
                                    import re

                                    digits = re.findall(r"[\d.]+", clean_price)
                                    if digits:
                                        price = float(digits[0])
                                        logger.info(
                                            f"Using nested pricing.{price_key}: {price}"
                                        )
                                        break
                            except (ValueError, TypeError):
                                pass

                # Skip products without valid price
                if price is None:
                    logger.warning(
                        f"Could not extract valid price for product {product_id}, skipping"
                    )
                    continue

                # Extract original price if available
                original_price = None
                original_price_str = None

                # Try different field names for original price
                for orig_price_field in [
                    "original_price",
                    "was_price",
                    "previous_price",
                    "list_price",
                    "msrp",
                    "regular_price",
                ]:
                    if orig_price_field in product and product[orig_price_field]:
                        original_price_str = product[orig_price_field]
                        break

                try:
                    if isinstance(original_price_str, (int, float)):
                        original_price = float(original_price_str)
                    elif (
                        isinstance(original_price_str, dict)
                        and "value" in original_price_str
                    ):
                        # Handle nested price objects like {'value': 29.99, 'currency': 'USD'}
                        price_value = original_price_str.get("value")
                        if isinstance(price_value, (int, float)):
                            original_price = float(price_value)
                    elif isinstance(original_price_str, str) and original_price_str:
                        # Clean up the price string
                        clean_price = (
                            original_price_str.replace("$", "")
                            .replace("£", "")
                            .replace("€", "")
                            .replace(",", "")
                            .strip()
                        )

                        # Handle price ranges (take the higher price)
                        if " - " in clean_price:
                            clean_price = clean_price.split(" - ")[1].strip()
                        elif " to " in clean_price.lower():
                            clean_price = clean_price.lower().split(" to ")[1].strip()

                        # Try to extract digits and decimal point
                        import re

                        digits = re.findall(r"[\d.]+", clean_price)
                        if digits:
                            original_price = float(digits[0])

                            # Ensure original price is higher than current price
                            if original_price and original_price <= price:
                                logger.debug(
                                    f"Original price {original_price} not higher than current price {price}, ignoring"
                                )
                                original_price = None
                except (ValueError, TypeError) as e:
                    logger.debug(f"Error extracting original price: {e}")
                    original_price = None

                # Extract description
                description = ""
                for desc_field in [
                    "description",
                    "snippet",
                    "summary",
                    "details",
                    "overview",
                ]:
                    if desc_field in product and product[desc_field]:
                        description = str(product[desc_field]).strip()
                        break

                # If no description, create a generic one
                if not description:
                    description = f"{title} available on Google Shopping."

                # Extract URL
                url = ""
                for url_field in ["link", "url", "product_link"]:
                    if url_field in product and product[url_field]:
                        url = str(product[url_field])
                        break

                # Extract image URL
                image_url = ""
                for img_field in ["thumbnail", "image", "image_url", "main_image"]:
                    if img_field in product and product[img_field]:
                        image_url = str(product[img_field])
                        break

                # Map category to standard categories
                raw_category = product.get("category", "").lower()
                category = MarketCategory.OTHER.value

                # Simple mapping logic for category
                category_mappings = {
                    "electronics": MarketCategory.ELECTRONICS.value,
                    "fashion": MarketCategory.FASHION.value,
                    "clothing": MarketCategory.FASHION.value,
                    "apparel": MarketCategory.FASHION.value,
                    "home": MarketCategory.HOME.value,
                    "kitchen": MarketCategory.HOME.value,
                    "furniture": MarketCategory.HOME.value,
                    "toys": MarketCategory.TOYS.value,
                    "books": MarketCategory.BOOKS.value,
                    "sports": MarketCategory.SPORTS.value,
                    "automotive": MarketCategory.AUTOMOTIVE.value,
                    "health": MarketCategory.HEALTH.value,
                    "beauty": MarketCategory.BEAUTY.value,
                    "grocery": MarketCategory.GROCERY.value,
                    "food": MarketCategory.GROCERY.value,
                }

                # Check raw category first
                for key, value in category_mappings.items():
                    if key in raw_category:
                        category = value
                        break

                # If no category found, try to infer from title
                if category == MarketCategory.OTHER.value:
                    title_lower = title.lower()
                    for key, value in category_mappings.items():
                        if key in title_lower:
                            category = value
                            break

                # Extract merchant info
                merchant = None
                if "merchant" in product:
                    if (
                        isinstance(product["merchant"], dict)
                        and "name" in product["merchant"]
                    ):
                        merchant = product["merchant"]["name"]
                    elif isinstance(product["merchant"], str):
                        merchant = product["merchant"]

                if not merchant:
                    merchant = product.get("source", product.get("seller", "Unknown"))

                # Extract ratings
                rating = 0.0
                rating_value = product.get("rating", 0)
                if isinstance(rating_value, dict) and "value" in rating_value:
                    rating = float(rating_value["value"])
                elif isinstance(rating_value, (int, float, str)):
                    try:
                        rating = float(rating_value)
                    except (ValueError, TypeError):
                        rating = 0.0

                # Extract review count
                review_count = 0
                reviews = product.get("reviews", product.get("review_count", 0))
                if isinstance(reviews, dict) and "count" in reviews:
                    review_count = int(reviews["count"])
                elif isinstance(reviews, (int, str)):
                    try:
                        review_count = int(reviews)
                    except (ValueError, TypeError):
                        review_count = 0

                # Create normalized product object
                normalized_product = {
                    "id": product_id,
                    "title": title,
                    "price": price,
                    "original_price": original_price,
                    "currency": "USD",
                    "url": url,
                    "image_url": image_url,
                    "description": description,
                    "source": "google_shopping",
                    "market_type": "google_shopping",
                    "market_name": "Google Shopping",  # Ensure market_name is properly set
                    "merchant": merchant,
                    "rating": rating,
                    "review_count": review_count,
                    "shipping": product.get("shipping", "Unknown"),
                    "is_available": True,  # Assume available if in search results
                    "category": category,
                    "metadata": {
                        "source": "google_shopping",
                        "query": query,
                        "timestamp": datetime.utcnow().isoformat(),
                        "raw_fields": list(product.keys()),
                        "raw_category": raw_category,
                    },
                }

                # Add to results
                normalized_products.append(normalized_product)

            except Exception as e:
                logger.error(f"Error normalizing Google Shopping product {i}: {str(e)}")
                continue

        logger.info(
            f"Successfully normalized {len(normalized_products)} Google Shopping products"
        )
        return normalized_products

    async def get_google_shopping_product(
        self, product_id: str, cache_ttl: int = 3600  # 1 hour
    ) -> Dict[str, Any]:
        """Get Google Shopping product details.

        Args:
            product_id: The Google Shopping product ID
            cache_ttl: Cache time-to-live in seconds

        Returns:
            Standardized product dictionary
        """
        logger.debug(f"Getting Google Shopping product details for: {product_id}")

        # Start timing
        start_time = time.time()
        success = False
        error_msg = None

        try:
            # Construct the target URL for Google Shopping product
            target_url = f"https://www.google.com/shopping/product/{product_id}"

            # Make request through ScraperAPI
            result = await self._make_request(
                target_url=target_url,
                params={
                    "autoparse": "true",
                    "render_js": "true",
                    "country_code": "us",
                    "keep_headers": "true",
                },
                cache_ttl=cache_ttl,
            )

            if not result:
                raise ProductNotFoundError(
                    market="google_shopping", product_id=product_id
                )

            logger.debug(f"Raw Google Shopping product result type: {type(result)}")

            # Extract product details from the response
            product = {}

            if isinstance(result, dict):
                # Extract product details from the response
                product = result.get("product", result)
            else:
                raise ProductNotFoundError(
                    market="google_shopping", product_id=product_id
                )

            # Extract product description
            description = ""
            for field in [
                "description",
                "product_description",
                "about",
                "overview",
                "details",
            ]:
                if field in product and product[field]:
                    description = product[field]
                    break

            # Extract price
            price = 0.0
            price_str = product.get("price", "")

            if isinstance(price_str, str):
                # Remove currency symbols, commas, etc.
                price_str = price_str.replace("$", "").replace(",", "").replace(" ", "")
                try:
                    price = float(price_str)
                except ValueError:
                    # Try to extract only digits and decimal point
                    import re

                    digits = re.findall(r"[\d.]+", price_str)
                    if digits:
                        price = float(digits[0])
            elif isinstance(price_str, (int, float)):
                price = float(price_str)

            # Create normalized product object
            normalized_product = {
                "id": product_id,
                "title": product.get("title", "Unknown Product"),
                "description": description,
                "price": price,
                "currency": "USD",  # Default to USD
                "url": product.get("link", target_url),
                "image_url": product.get("main_image", product.get("image", "")),
                "source": "google_shopping",
                "market_type": "google_shopping",
                "merchant": product.get("merchant", {}).get(
                    "name", product.get("source", "Unknown")
                ),
                "rating": float(product.get("rating", {}).get("value", 0)),
                "review_count": int(product.get("rating", {}).get("count", 0)),
                "availability": product.get("availability", "Unknown"),
                "features": product.get("features", []),
                "is_available": "out of stock"
                not in product.get("availability", "").lower(),
                "metadata": {
                    "source": "google_shopping",
                    "timestamp": datetime.utcnow().isoformat(),
                    "raw_fields": list(product.keys()),
                },
            }

            # Extract and add specifications
            if "specifications" in product and isinstance(
                product["specifications"], dict
            ):
                normalized_product["specifications"] = product["specifications"]
            elif "specs" in product and isinstance(product["specs"], dict):
                normalized_product["specifications"] = product["specs"]

            # Mark as successful
            success = True

            # Record market metrics
            await self._record_market_metrics(
                market_type=MarketType.GOOGLE_SHOPPING,
                success=success,
                response_time=time.time() - start_time,
                error=error_msg,
            )

            return normalized_product

        except ProductNotFoundError:
            # Record market metrics with error
            await self._record_market_metrics(
                market_type=MarketType.GOOGLE_SHOPPING,
                success=False,
                response_time=time.time() - start_time,
                error="Product not found",
            )
            raise

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error getting Google Shopping product: {error_msg}")

            # Record market metrics with error
            await self._record_market_metrics(
                market_type=MarketType.GOOGLE_SHOPPING,
                success=False,
                response_time=time.time() - start_time,
                error=error_msg,
            )

            # Raise a standardized exception
            raise MarketIntegrationError(
                market="google_shopping",
                operation="get_product_details",
                reason=error_msg,
            )


async def get_scraper_api() -> ScraperAPIService:
    """Get or create a ScraperAPIService instance.

    This is a singleton factory function that ensures we reuse the same
    ScraperAPIService instance across the application.

    Returns:
        ScraperAPIService: An instance of the ScraperAPI service
    """
    from core.config import settings
    from core.database import get_async_db_session

    db = await get_async_db_session()
    return ScraperAPIService(api_key=settings.SCRAPER_API_KEY, db=db)
