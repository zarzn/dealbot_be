"""Market search service module.

This module provides comprehensive market search functionality for the AI Agentic Deals System,
including product search, details retrieval, availability checking, and price history tracking
across multiple e-commerce platforms.
"""

from typing import List, Dict, Any, Optional, Tuple
import asyncio
from uuid import UUID
from datetime import datetime, timedelta
from dataclasses import dataclass
from functools import partial

from core.models.market import MarketType
from core.repositories.market import MarketRepository
from core.integrations.factory import MarketIntegrationFactory
from core.utils.redis import get_redis_client, set_cache, get_cache, RedisClient
from core.utils.logger import get_logger
from core.utils.metrics import MetricsCollector
from core.exceptions import (
    BaseError,
    ValidationError,
    MarketError,
    IntegrationError,
    NetworkError,
    ServiceError,
    DataQualityError
)
from core.config import settings


logger = get_logger(__name__)

@dataclass
class SearchResult:
    """Data class for search results."""
    products: List[Dict[str, Any]]
    total_found: int
    successful_markets: List[str]
    failed_markets: List[Tuple[str, str]]
    search_time: float
    cache_hit: bool

class MarketSearchService:
    """Service for searching products across multiple markets."""

    def __init__(self, market_repository: MarketRepository):
        self.market_repository = market_repository
        self.redis_client = RedisClient()  # Use singleton RedisClient instance

    async def _check_rate_limit(self, key: str, limit: int) -> bool:
        """Check rate limit using Redis."""
        try:
            current = await self.redis_client.incrby(f"ratelimit:{key}")
            if current == 1:
                await self.redis_client.expire(f"ratelimit:{key}", 60)  # 1 minute window
            return current <= limit
        except Exception as e:
            logger.error(f"Rate limit check failed: {str(e)}")
            return True  # Allow on error

    async def search_products(
        self,
        query: str,
        market_types: Optional[List[MarketType]] = None,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        limit: int = 10,
        use_cache: bool = True,
        cache_ttl: int = 300  # 5 minutes
    ) -> SearchResult:
        """
        Search for products across multiple markets with caching and rate limiting.

        Args:
            query: Search query string
            market_types: Optional list of specific markets to search
            category: Optional category filter
            min_price: Optional minimum price filter
            max_price: Optional maximum price filter
            limit: Maximum number of results per market
            use_cache: Whether to use cached results
            cache_ttl: Cache TTL in seconds

        Returns:
            SearchResult containing products and metadata

        Raises:
            ValidationError: If input validation fails
            MarketError: If market operations fail
            RateLimitError: If rate limits are exceeded
        """
        try:
            start_time = datetime.utcnow()

            # Input validation
            if not query:
                raise ValidationError("Search query is required")
            if min_price is not None and max_price is not None and min_price > max_price:
                raise ValidationError("min_price cannot be greater than max_price")
            if limit < 1:
                raise ValidationError("limit must be positive")

            # Check cache first
            if use_cache:
                cache_key = self._generate_cache_key(
                    query, market_types, category, min_price, max_price, limit
                )
                cached_result = await get_cache(cache_key)
                if cached_result:
                    logger.info(f"Cache hit for query: {query}")
                    MetricsCollector.track_search_cache_hit()
                    return SearchResult(
                        products=cached_result["products"],
                        total_found=cached_result["total_found"],
                        successful_markets=cached_result["successful_markets"],
                        failed_markets=cached_result["failed_markets"],
                        search_time=cached_result["search_time"],
                        cache_hit=True
                    )

            # Get active markets
            active_markets = await self._get_filtered_markets(market_types)

            # Create search tasks for each market
            search_tasks = []
            for market in active_markets:
                # Check rate limits
                if not await self._check_rate_limit(
                    f"market_search:{market.type}",
                    settings.MARKET_RATE_LIMIT_PER_MINUTE
                ):
                    logger.warning(f"Rate limit exceeded for market: {market.type}")
                    continue

                integration = await self._get_market_integration(market)
                if integration:
                    search_tasks.append(
                        self._execute_market_search(
                            integration,
                            query,
                            category,
                            min_price,
                            max_price,
                            limit,
                            market.type
                        )
                    )

            if not search_tasks:
                raise MarketError("No available markets to search")

            # Execute searches in parallel with timeout
            results = await asyncio.gather(*search_tasks, return_exceptions=True)

            # Process results
            all_products = []
            successful_markets = []
            failed_markets = []
            total_found = 0

            for market, result in zip(active_markets, results):
                if isinstance(result, Exception):
                    error_msg = str(result)
                    logger.error(
                        f"Error searching {market.type}: {error_msg}",
                        exc_info=True
                    )
                    failed_markets.append((str(market.type), error_msg))
                    MetricsCollector.track_market_search_error(
                        market_type=str(market.type),
                        error_type=type(result).__name__
                    )
                else:
                    successful_markets.append(str(market.type))
                    products = result.get("products", [])
                    total_found += result.get("total_found", len(products))
                    all_products.extend(products)

            # Sort and process products
            sorted_products = await self._sort_and_process_products(
                all_products,
                limit
            )

            search_time = (datetime.utcnow() - start_time).total_seconds()

            # Create result
            result = SearchResult(
                products=sorted_products,
                total_found=total_found,
                successful_markets=successful_markets,
                failed_markets=failed_markets,
                search_time=search_time,
                cache_hit=False
            )

            # Cache result if successful
            if use_cache and sorted_products:
                await set_cache(
                    cache_key,
                    result.__dict__,
                    expire=cache_ttl
                )

            # Track metrics
            MetricsCollector.track_market_search(
                query=query,
                results_count=len(sorted_products),
                search_time=search_time,
                successful_markets=len(successful_markets),
                failed_markets=len(failed_markets)
            )

            return result

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error in product search: {str(e)}", exc_info=True)
            raise MarketError(f"Failed to search products: {str(e)}")

    async def get_product_details(
        self,
        product_id: str,
        market_type: MarketType,
        use_cache: bool = True,
        cache_ttl: int = 3600  # 1 hour
    ) -> Dict[str, Any]:
        """
        Get detailed information about a specific product with caching.

        Args:
            product_id: Product identifier
            market_type: Market type
            use_cache: Whether to use cached results
            cache_ttl: Cache TTL in seconds

        Returns:
            Product details dictionary

        Raises:
            ValidationError: If input validation fails
            MarketError: If market operations fail
            IntegrationError: If integration fails
        """
        try:
            # Check cache first
            if use_cache:
                cache_key = f"product_details:{market_type}:{product_id}"
                cached_result = await get_cache(cache_key)
                if cached_result:
                    logger.info(f"Cache hit for product details: {product_id}")
                    MetricsCollector.track_product_details_cache_hit()
                    return cached_result

            # Get market integration
            market = await self.market_repository.get_by_type(market_type)
            if not market:
                raise ValidationError(f"Market not found for type: {market_type}")

            integration = await self._get_market_integration(market)

            # Get product details
            start_time = datetime.utcnow()
            try:
                details = await integration.get_product_details(product_id)
                if not details:
                    raise DataQualityError("No product details returned")

                # Cache result
                if use_cache:
                    await set_cache(
                        cache_key,
                        details,
                        expire=cache_ttl
                    )

                # Track metrics
                search_time = (datetime.utcnow() - start_time).total_seconds()
                MetricsCollector.track_product_details(
                    market_type=str(market_type),
                    response_time=search_time
                )

                return details

            except Exception as e:
                logger.error(
                    f"Error getting product details for {product_id}: {str(e)}",
                    exc_info=True
                )
                raise IntegrationError(
                    f"Failed to get product details from {market_type}: {str(e)}"
                )

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error in get_product_details: {str(e)}", exc_info=True)
            raise MarketError(f"Failed to get product details: {str(e)}")

    async def check_product_availability(
        self,
        product_id: str,
        market_type: MarketType,
        use_cache: bool = True,
        cache_ttl: int = 300  # 5 minutes
    ) -> Dict[str, Any]:
        """
        Check if a product is currently available with caching.

        Args:
            product_id: Product identifier
            market_type: Market type
            use_cache: Whether to use cached results
            cache_ttl: Cache TTL in seconds

        Returns:
            Dictionary with availability status and metadata

        Raises:
            ValidationError: If input validation fails
            MarketError: If market operations fail
        """
        try:
            # Check cache first
            if use_cache:
                cache_key = f"product_availability:{market_type}:{product_id}"
                cached_result = await get_cache(cache_key)
                if cached_result:
                    logger.info(f"Cache hit for availability check: {product_id}")
                    return cached_result

            # Get market integration
            market = await self.market_repository.get_by_type(market_type)
            if not market:
                raise ValidationError(f"Market not found for type: {market_type}")

            integration = await self._get_market_integration(market)

            # Check availability
            start_time = datetime.utcnow()
            try:
                result = await integration.check_product_availability(product_id)
                
                availability_data = {
                    "is_available": bool(result),
                    "checked_at": datetime.utcnow().isoformat(),
                    "market_type": str(market_type)
                }

                # Cache result
                if use_cache:
                    await set_cache(
                        cache_key,
                        availability_data,
                        expire=cache_ttl
                    )

                # Track metrics
                check_time = (datetime.utcnow() - start_time).total_seconds()
                MetricsCollector.track_availability_check(
                    market_type=str(market_type),
                    is_available=availability_data["is_available"],
                    response_time=check_time
                )

                return availability_data

            except Exception as e:
                logger.error(
                    f"Error checking availability for {product_id}: {str(e)}",
                    exc_info=True
                )
                raise IntegrationError(
                    f"Failed to check availability from {market_type}: {str(e)}"
                )

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error in check_product_availability: {str(e)}", exc_info=True)
            raise MarketError(f"Failed to check product availability: {str(e)}")

    async def get_product_price_history(
        self,
        product_id: str,
        market_type: MarketType,
        days: int = 30,
        use_cache: bool = True,
        cache_ttl: int = 3600  # 1 hour
    ) -> List[Dict[str, Any]]:
        """
        Get price history for a specific product with caching.

        Args:
            product_id: Product identifier
            market_type: Market type
            days: Number of days of history to retrieve
            use_cache: Whether to use cached results
            cache_ttl: Cache TTL in seconds

        Returns:
            List of price history records

        Raises:
            ValidationError: If input validation fails
            MarketError: If market operations fail
        """
        try:
            if days < 1:
                raise ValidationError("days must be positive")

            # Check cache first
            if use_cache:
                cache_key = f"price_history:{market_type}:{product_id}:{days}"
                cached_result = await get_cache(cache_key)
                if cached_result:
                    logger.info(f"Cache hit for price history: {product_id}")
                    return cached_result

            # Get market integration
            market = await self.market_repository.get_by_type(market_type)
            if not market:
                raise ValidationError(f"Market not found for type: {market_type}")

            integration = await self._get_market_integration(market)

            # Get price history
            start_time = datetime.utcnow()
            try:
                history = await integration.get_product_price_history(
                    product_id,
                    days=days
                )

                # Validate and process history data
                processed_history = await self._process_price_history(history)

                # Cache result
                if use_cache and processed_history:
                    await set_cache(
                        cache_key,
                        processed_history,
                        expire=cache_ttl
                    )

                # Track metrics
                fetch_time = (datetime.utcnow() - start_time).total_seconds()
                MetricsCollector.track_price_history(
                    market_type=str(market_type),
                    history_points=len(processed_history),
                    response_time=fetch_time
                )

                return processed_history

            except NotImplementedError:
                logger.warning(
                    f"Price history not implemented for market: {market_type}"
                )
                return []
            except Exception as e:
                logger.error(
                    f"Error getting price history for {product_id}: {str(e)}",
                    exc_info=True
                )
                raise IntegrationError(
                    f"Failed to get price history from {market_type}: {str(e)}"
                )

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error in get_product_price_history: {str(e)}", exc_info=True)
            raise MarketError(f"Failed to get product price history: {str(e)}")

    async def _get_filtered_markets(
        self,
        market_types: Optional[List[MarketType]] = None
    ) -> List[Any]:
        """Get filtered list of active markets."""
        active_markets = await self.market_repository.get_all_active()
        
        if not active_markets:
            raise MarketError("No active markets available")

        if market_types:
            active_markets = [m for m in active_markets if m.type in market_types]
            if not active_markets:
                raise ValidationError(f"No active markets found for types: {market_types}")

        return active_markets

    async def _get_market_integration(self, market: Any) -> Any:
        """Get market integration with error handling."""
        try:
            return MarketIntegrationFactory.get_integration(
                market.type,
                market.api_credentials
            )
        except Exception as e:
            logger.error(
                f"Error creating integration for market {market.type}: {str(e)}",
                exc_info=True
            )
            raise IntegrationError(
                f"Failed to create integration for {market.type}: {str(e)}"
            )

    async def _execute_market_search(
        self,
        integration: Any,
        query: str,
        category: Optional[str],
        min_price: Optional[float],
        max_price: Optional[float],
        limit: int,
        market_type: MarketType
    ) -> Dict[str, Any]:
        """Execute search on a specific market with error handling."""
        try:
            return await integration.search_products(
                query=query,
                category=category,
                min_price=min_price,
                max_price=max_price,
                limit=limit
            )
        except Exception as e:
            logger.error(
                f"Error searching {market_type}: {str(e)}",
                exc_info=True
            )
            raise IntegrationError(f"Search failed for {market_type}: {str(e)}")

    async def _sort_and_process_products(
        self,
        products: List[Dict[str, Any]],
        limit: int
    ) -> List[Dict[str, Any]]:
        """Sort and process product results."""
        try:
            # Remove duplicates based on product ID
            unique_products = {
                p.get("id"): p for p in products
            }.values()

            # Sort products
            sorted_products = sorted(
                unique_products,
                key=lambda x: (
                    float(x.get("price", float("inf"))),
                    -float(x.get("rating", 0)),
                    -int(x.get("review_count", 0))
                )
            )

            # Process and validate each product
            processed_products = []
            for product in sorted_products[:limit]:
                try:
                    processed = await self._process_product(product)
                    if processed:
                        processed_products.append(processed)
                except Exception as e:
                    logger.warning(f"Error processing product: {str(e)}")
                    continue

            return processed_products

        except Exception as e:
            logger.error(f"Error processing products: {str(e)}", exc_info=True)
            raise DataQualityError(f"Failed to process products: {str(e)}")

    async def _process_product(self, product: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process and validate individual product data."""
        required_fields = ["id", "title", "price", "market_type"]
        if not all(field in product for field in required_fields):
            logger.warning(f"Product missing required fields: {product.get('id', 'unknown')}")
            return None

        try:
            # Ensure numeric fields are properly typed
            product["price"] = float(product["price"])
            if "rating" in product:
                product["rating"] = float(product["rating"])
            if "review_count" in product:
                product["review_count"] = int(product["review_count"])

            # Add processing timestamp
            product["processed_at"] = datetime.utcnow().isoformat()

            return product

        except (ValueError, TypeError) as e:
            logger.warning(f"Error processing product data: {str(e)}")
            return None

    async def _process_price_history(
        self,
        history: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Process and validate price history data."""
        processed_history = []
        for entry in history:
            try:
                if "price" not in entry or "timestamp" not in entry:
                    continue

                processed_entry = {
                    "price": float(entry["price"]),
                    "timestamp": entry["timestamp"],
                    "source": entry.get("source", "unknown")
                }
                processed_history.append(processed_entry)

            except (ValueError, TypeError) as e:
                logger.warning(f"Error processing price history entry: {str(e)}")
                continue

        return sorted(
            processed_history,
            key=lambda x: x["timestamp"]
        )

    def _generate_cache_key(
        self,
        query: str,
        market_types: Optional[List[MarketType]],
        category: Optional[str],
        min_price: Optional[float],
        max_price: Optional[float],
        limit: int
    ) -> str:
        """Generate cache key for search results."""
        key_parts = [
            f"search:{query}",
            f"markets:{','.join(sorted(str(m) for m in market_types))}",
            f"category:{category}",
            f"price:{min_price}-{max_price}",
            f"limit:{limit}"
        ]
        return ":".join(key_parts) 
