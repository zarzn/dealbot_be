"""eBay-specific Oxylabs scraping service."""

import logging
from typing import Any, Dict, List, Optional, Union
import asyncio
import re

from core.integrations.oxylabs.market_base import OxylabsMarketBaseService, OxylabsResult
from core.integrations.oxylabs.utils import extract_price, detect_currency

logger = logging.getLogger(__name__)


class EbayOxylabsService(OxylabsMarketBaseService):
    """Service for scraping eBay using Oxylabs."""

    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        """Initialize eBay Oxylabs service.
        
        Args:
            username: Oxylabs username
            password: Oxylabs password
        """
        super().__init__(username, password)
        # Set eBay-specific source configurations
        self.search_source = "ebay_search"
        self.product_source = "ebay_product"
        self.fallback_source = "universal"
        self.market_name = "eBay"

    async def search_products(
        self, 
        query: str,
        limit: int = 10,
        geo_location: Optional[str] = "united_states",
        sort_by: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        parse: bool = True,
        cache_ttl: Optional[int] = None,
        extract_details: bool = False,
        batch_size: int = 10,
        **kwargs
    ) -> OxylabsResult:
        """Search for products on eBay.
        
        Args:
            query: Search query
            limit: Maximum number of results
            geo_location: Location to search from
            sort_by: Sorting option 
            min_price: Minimum price filter
            max_price: Maximum price filter
            parse: Whether to parse the results automatically
            cache_ttl: Cache TTL in seconds
            extract_details: If True, attempt to extract additional details for each product
            batch_size: Number of products to process in a single batch (for optimization)
            **kwargs: Additional parameters for the request
            
        Returns:
            OxylabsResult object with search results
        """
        # Build the search URL
        url = f"https://www.ebay.com/sch/i.html?_nkw={query}"
        
        # Log for debugging
        logger.debug(f"eBay search - Using url: {url}")
        logger.debug(f"eBay search - Using source: {self.search_source}")
        
        # Build parameters with base implementation
        params = self._prepare_search_params(
            query=query,
            limit=limit,
            parse=parse,
            geo_location=geo_location,
            sort_by=sort_by,
            min_price=min_price,
            max_price=max_price,
            **kwargs
        )
        
        # Add eBay-specific parameters
        params["url"] = url
        
        # Add optional pagination parameters
        if "start_page" in kwargs:
            params["start_page"] = kwargs.pop("start_page")
            
        # Calculate pages needed to get the requested number of products
        # Assuming average of 50 products per page on eBay, but ultimately we'll truncate to limit
        estimated_products_per_page = 50
        pages = max(1, (limit + estimated_products_per_page - 1) // estimated_products_per_page)
        params["pages"] = kwargs.pop("pages", pages)
        
        # Log the query but keep params at debug level
        logger.info(f"eBay search - Query: {query}")
        logger.debug(f"eBay search parameters: {params}")
        
        # Execute with standardized fallback handling
        search_result = await self._execute_with_fallback(params, cache_ttl, "search")
        
        # No need for additional processing if we don't have data or don't need details
        if not search_result or not search_result.results or not extract_details:
            # Ensure we don't return more items than the limit
            if search_result and search_result.results and isinstance(search_result.results, dict):
                # Handle pagination to enforce limit
                self._enforce_result_limit(search_result.results, limit)
            return search_result
        
        # If extract_details is True, we'll enrich the search results
        # with additional product data when available
        try:
            # Log start of detailed product data retrieval
            logger.info(f"eBay search - Extracting detailed product information for up to {limit} products")
            
            # Attempt to process the results to add more detailed information
            processed_data = await self._process_search_results(
                search_result.results, 
                geo_location=geo_location, 
                limit=limit,
                batch_size=batch_size,
                cache_ttl=cache_ttl
            )
            
            # Update the result with the enriched data
            if processed_data:
                search_result.results = processed_data
                
            return search_result
            
        except Exception as e:
            logger.error(f"Error processing search results for detailed information: {e}")
            # Fall back to the original search results if enhancement fails
            return search_result

    def _extract_product_ids_from_search(self, results: List[Dict[str, Any]]) -> List[str]:
        """Extract product IDs from search results.
        
        Args:
            results: Search results list
            
        Returns:
            List of product IDs
        """
        product_ids = []
        
        for product in results:
            product_id = product.get("item_id") or product.get("id")
            if product_id:
                product_ids.append(product_id)
                
        return product_ids

    async def get_product_details(
        self, 
        product_id: str,
        region: Optional[str] = "United States",
        parse: bool = True,
        cache_ttl: Optional[int] = None,
        **kwargs
    ) -> OxylabsResult:
        """Get details of a specific product on eBay.
        
        Args:
            product_id: eBay product ID
            region: Region or country (default: "United States")
            parse: Whether to parse the results automatically
            cache_ttl: Cache time-to-live in seconds (None for no caching)
            **kwargs: Additional parameters for the request
            
        Returns:
            OxylabsResult object with product details
        """
        # Construct the product URL
        url = f"https://www.ebay.com/itm/{product_id}"
        
        # Build parameters with base implementation
        params = self._prepare_product_params(
            product_id=product_id,
            parse=parse,
            region=region,
            **kwargs
        )
        
        # Override with eBay-specific parameters
        params["url"] = url
        params["render"] = "html"
        
        # Handle country-specific eBay sites
        if "country" in kwargs:
            country = kwargs.pop("country")
            if country.lower() != "us":
                # Map country code to eBay domain
                country_to_domain = {
                    "uk": "co.uk",
                    "ca": "ca",
                    "au": "com.au",
                    "de": "de",
                    "fr": "fr",
                    "it": "it",
                    "es": "es"
                }
                domain = country_to_domain.get(country.lower(), "com")
                url = f"https://www.ebay.{domain}/itm/{product_id}"
                params["url"] = url
        
        # Log the request parameters
        logger.info(f"eBay product details - URL: {url}")
        logger.debug(f"eBay product details parameters: {params}")
        
        # Execute with standardized fallback handling
        return await self._execute_with_fallback(params, cache_ttl, "product details")

    def extract_product_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract useful product data from Oxylabs response.
        
        Args:
            raw_data: Raw data from Oxylabs response
            
        Returns:
            Dictionary with extracted product information
        """
        if not raw_data:
            return {}
            
        # Extract data from parsed results
        try:
            title = raw_data.get("title", "")
            price_text = raw_data.get("price", "")
            price_value, currency = extract_price(price_text)
            
            # If currency not detected, try to detect from locale or price text
            if not currency:
                currency = detect_currency(price_text)
                if not currency:
                    # Default to USD for eBay US
                    currency = "USD"
                    
            # Create standardized product data structure
            product_data = {
                "title": title,
                "price": price_value,
                "currency": currency,
                "rating": raw_data.get("rating", None),
                "reviews_count": raw_data.get("reviews_count", None),
                "condition": raw_data.get("condition", None),
                "availability": raw_data.get("availability", None),
                "image_url": raw_data.get("image_url", None),
                "seller": raw_data.get("seller", None),
                "shipping": raw_data.get("shipping_price", None),
                "shipping_currency": raw_data.get("shipping_currency", currency),
                "returns": raw_data.get("returns", None),
                "description": raw_data.get("description", ""),
                "item_id": raw_data.get("item_id", None),
                "format": raw_data.get("format", None),  # auction, buy it now, etc.
                "location": raw_data.get("location", None),
            }
            
            # Extract original price for discounted items - check multiple possible field names
            for orig_price_field in ['price_strikethrough', 'was_price', 'list_price', 'original_price', 'msrp', 'strike_price']:
                if orig_price_field in raw_data and raw_data[orig_price_field]:
                    try:
                        if isinstance(raw_data[orig_price_field], (int, float)):
                            product_data["original_price"] = float(raw_data[orig_price_field])
                        elif isinstance(raw_data[orig_price_field], str):
                            # Try to extract numeric price from string
                            cleaned_price = re.sub(r'[^\d.]', '', raw_data[orig_price_field])
                            if cleaned_price:
                                product_data["original_price"] = float(cleaned_price)
                        # Only use original price if it's higher than current price
                        if "original_price" in product_data and "price" in product_data:
                            if product_data["original_price"] <= product_data["price"]:
                                logger.debug(f"Original price {product_data['original_price']} is not higher than current price {product_data['price']}, ignoring")
                                del product_data["original_price"]
                            else:
                                logger.debug(f"Found original price {product_data['original_price']} for item {product_data.get('item_id', 'unknown')}")
                                break
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Failed to parse original price from {orig_price_field}: {raw_data[orig_price_field]}, error: {e}")
                        continue
            
            # Add any additional fields that might be present
            for key, value in raw_data.items():
                if key not in product_data and value is not None:
                    product_data[key] = value
                    
            return product_data
            
        except Exception as e:
            logger.error(f"Error extracting eBay product data: {e}")
            return {} 

    def _enforce_result_limit(self, data: Dict[str, Any], limit: int) -> None:
        """Enforce the result limit on the search data.
        
        Args:
            data: The search result data
            limit: Maximum number of results to keep
        """
        if not data or not isinstance(data, dict):
            return
            
        # Handle different result formats
        if "results" in data and isinstance(data["results"], list):
            data["results"] = data["results"][:limit]
            
        # Direct list of products at the top level
        elif isinstance(data, list):
            data = data[:limit]
            
        # Handle eBay-specific result structure if different
        if "content" in data and "results" in data["content"]:
            results = data["content"]["results"]
            
            # Handle different result structures
            if "organic" in results and isinstance(results["organic"], list):
                results["organic"] = results["organic"][:limit]
                
            if "paid" in results and isinstance(results["paid"], list):
                # Keep a few sponsored results but prioritize organic
                if "organic" in results and isinstance(results["organic"], list):
                    sponsored_limit = max(2, limit // 5)  # Keep about 20% as sponsored
                    results["paid"] = results["paid"][:sponsored_limit]

    async def _process_search_results(
        self,
        data: Dict[str, Any],
        geo_location: str,
        limit: int,
        batch_size: int,
        cache_ttl: Optional[int] = None
    ) -> Dict[str, Any]:
        """Process search results to add more detailed information.
        
        Args:
            data: The search result data
            geo_location: Geo location
            limit: Maximum number of results
            batch_size: Number of products to process in a batch
            cache_ttl: Cache TTL for product detail requests
            
        Returns:
            Processed data with enhanced product information
        """
        if not data or not isinstance(data, dict):
            return data
            
        # First enforce the limit to avoid processing unnecessary items
        self._enforce_result_limit(data, limit)
        
        # Extract product IDs for batch processing
        item_id_list = []
        
        # Handle different result formats
        if "results" in data and isinstance(data["results"], list):
            for product in data["results"]:
                if product.get("item_id") or product.get("id"):
                    # Use either item_id or id field
                    item_id = product.get("item_id") or product.get("id")
                    item_id_list.append(item_id)
        
        # Limit the number of IDs to process
        item_id_list = item_id_list[:limit]
        
        # If no IDs found, return the original data
        if not item_id_list:
            logger.debug("No product IDs found in search results")
            return data
            
        # Log the number of products to be processed
        logger.info(f"eBay search - Processing {len(item_id_list)} products for detailed information")
        
        # Process IDs in batches for better performance
        all_product_details = {}
        
        for i in range(0, len(item_id_list), batch_size):
            batch_ids = item_id_list[i:i+batch_size]
            
            logger.debug(f"eBay search - Processing batch {i//batch_size+1} with {len(batch_ids)} products")
            
            # Process each batch concurrently
            batch_tasks = [
                self.get_product_details(
                    item_id, 
                    geo_location=geo_location, 
                    parse=True,
                    cache_ttl=cache_ttl
                ) for item_id in batch_ids
            ]
            
            # Wait for all batch requests to complete
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Process results from the batch
            for item_id, result in zip(batch_ids, batch_results):
                if isinstance(result, Exception):
                    logger.warning(f"Error fetching details for product {item_id}: {result}")
                    continue
                    
                if result and result.data:
                    # Extract and store the detailed product data
                    all_product_details[item_id] = self.extract_product_data(result.data)
        
        # Log successful detailed product retrievals
        logger.info(f"eBay search - Successfully retrieved detailed information for {len(all_product_details)} out of {len(item_id_list)} products")
        
        # Enhance the original search results with the detailed data
        if "results" in data and isinstance(data["results"], list):
            for product in data["results"]:
                item_id = product.get("item_id") or product.get("id")
                if item_id and item_id in all_product_details:
                    # Merge the detailed data with the search result
                    # Preserve original search result fields and add missing details
                    detailed_data = all_product_details[item_id]
                    for key, value in detailed_data.items():
                        if key not in product or not product[key]:
                            product[key] = value
                    
                    # Make sure original_price is included if available
                    if "original_price" in detailed_data and detailed_data["original_price"]:
                        product["original_price"] = detailed_data["original_price"]
                        
                    # Add discount information if available
                    if "discount_percentage" in detailed_data and detailed_data["discount_percentage"]:
                        product["discount_percentage"] = detailed_data["discount_percentage"]

        logger.info(f"eBay search - Completed enhancing search results with detailed product information")
        return data 