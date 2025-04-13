"""Walmart-specific Oxylabs scraping service."""

import logging
from typing import Any, Dict, List, Optional, Union
import asyncio
import re

from core.integrations.oxylabs.market_base import OxylabsMarketBaseService, OxylabsResult
from core.integrations.oxylabs.utils import extract_price, detect_currency

logger = logging.getLogger(__name__)


class WalmartOxylabsService(OxylabsMarketBaseService):
    """Service for scraping Walmart using Oxylabs."""

    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        """Initialize Walmart Oxylabs service.
        
        Args:
            username: Oxylabs username
            password: Oxylabs password
        """
        super().__init__(username, password)
        # Set Walmart-specific source configurations
        self.search_source = "walmart_search"  # Primary search source
        self.product_source = "universal"  # For product details, universal works best
        self.fallback_source = "universal"  # Fallback to universal if needed
        self.market_name = "Walmart"

    async def search_products(
        self, 
        query: str,
        limit: int = 10,
        region: Optional[str] = "United States",
        sort_by: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        parse: bool = True,
        cache_ttl: Optional[int] = None,
        extract_details: bool = False,
        batch_size: int = 10,
        **kwargs
    ) -> OxylabsResult:
        """Search for products on Walmart.
        
        Args:
            query: Search query
            limit: Maximum number of results
            region: Region or country (default: "United States")
            sort_by: Sorting option (price_asc, price_desc, best_selling, relevance)
            min_price: Minimum price filter
            max_price: Maximum price filter
            parse: Whether to parse the results automatically
            cache_ttl: Cache time-to-live in seconds (None for no caching)
            extract_details: If True, attempt to extract additional details for each product
            batch_size: Number of products to process in a single batch (for optimization)
            **kwargs: Additional parameters for the request
            
        Returns:
            OxylabsResult object with search results
        """
        # Construct the URL
        url = f"https://www.walmart.com/search?q={query}"
        
        # Build parameters with base implementation
        params = self._prepare_search_params(
            query=query,
            limit=limit,
            parse=parse,
            region=region,
            sort_by=None,  # We'll handle sort_by specially for Walmart
            min_price=min_price,
            max_price=max_price,
            **kwargs
        )
        
        # Override with Walmart-specific parameters
        params["url"] = url
        
        # Map sort options to Walmart's expected values if provided
        if sort_by is not None:
            # Map our sort options to Walmart's expected values
            sort_mapping = {
                "price_asc": "price_low",
                "price_desc": "price_high",
                "best_selling": "best_seller",
                "relevance": "best_match"
            }
            
            # Use mapped value if available, otherwise use provided value
            mapped_sort = sort_mapping.get(sort_by, sort_by)
            params["sort_by"] = mapped_sort
            logger.info(f"Walmart search - Mapped sort_by from {sort_by} to {mapped_sort}")
        
        # Add localization parameters if provided
        for param in ["domain", "fulfillment_speed", "fulfillment_type", "delivery_zip", "store_id"]:
            if param in kwargs:
                params[param] = kwargs.pop(param)
                logger.info(f"Walmart search - Using {param}: {params[param]}")
        
        # Log the final parameters for better debugging
        logger.info(f"Walmart search - URL: {url}")
        logger.debug(f"Walmart search parameters: {params}")
        
        # Execute with standardized fallback handling
        search_result = await self._execute_with_fallback(params, cache_ttl, "search")
        
        # No need for additional processing if we don't have data or don't need details
        if not search_result.success or not extract_details:
            return search_result
        
        # If extract_details is True, we'll enrich the search results
        # with additional product data when available
        try:
            # Extract product IDs from search results
            product_ids = self._extract_product_ids_from_search(search_result.results)
            
            # Limit the number of product IDs to process
            product_ids = product_ids[:limit]
            
            # If no product IDs found, return the original results
            if not product_ids:
                return search_result
                
            # Process product IDs in batches for better performance
            all_product_details = {}
            
            for i in range(0, len(product_ids), batch_size):
                batch_ids = product_ids[i:i+batch_size]
                
                # Process each batch concurrently
                batch_tasks = [
                    self.get_product_details(
                        product_id, 
                        region=region, 
                        parse=True,
                        cache_ttl=cache_ttl
                    ) for product_id in batch_ids
                ]
                
                # Wait for all batch requests to complete
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                # Process results from the batch
                for product_id, result in zip(batch_ids, batch_results):
                    if isinstance(result, Exception):
                        logger.warning(f"Error fetching details for Walmart product {product_id}: {result}")
                        continue
                        
                    if result and result.success and result.results:
                        # Extract and store the detailed product data
                        all_product_details[product_id] = self.extract_product_data(result.results[0] if result.results else {})
            
            # Enhance the original search results with the detailed data
            enhanced_results = []
            
            for product in search_result.results:
                product_id = product.get("item_id") or product.get("id")
                if product_id and product_id in all_product_details:
                    # Merge the detailed data with the search result
                    detailed_data = all_product_details[product_id]
                    for key, value in detailed_data.items():
                        if key not in product or not product[key]:
                            product[key] = value
                enhanced_results.append(product)
            
            # Update the results with enhanced data
            search_result.results = enhanced_results
            
            return search_result
            
        except Exception as e:
            logger.error(f"Error processing Walmart search results for detailed information: {e}")
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
        """Get details of a specific product on Walmart.
        
        Args:
            product_id: Walmart product ID
            region: Region or country (default: "United States")
            parse: Whether to parse the results automatically
            cache_ttl: Cache time-to-live in seconds (None for no caching)
            **kwargs: Additional parameters for the request
            
        Returns:
            OxylabsResult object with product details
        """
        # Construct the product URL
        url = f"https://www.walmart.com/ip/{product_id}"
        
        # Build parameters with base implementation
        params = self._prepare_product_params(
            product_id=product_id,
            parse=parse,
            region=region,
            **kwargs
        )
        
        # Override with Walmart-specific parameters
        params["url"] = url
        params["render"] = "html"
        
        # Add localization parameters if provided
        for param in ["domain", "delivery_zip", "store_id"]:
            if param in kwargs:
                params[param] = kwargs.pop(param)
                logger.info(f"Walmart product details - Using {param}: {params[param]}")
        
        # Log the final parameters for better debugging
        logger.info(f"Walmart product details - URL: {url}")
        logger.debug(f"Walmart product details parameters: {params}")
        
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
            
            if not currency:
                # Default to USD for Walmart
                currency = "USD"
                
            # Create standardized product data structure
            product_data = {
                "title": title,
                "price": price_value,
                "currency": currency,
                "rating": raw_data.get("rating", None),
                "reviews_count": raw_data.get("reviews_count", None),
                "availability": raw_data.get("availability", None),
                "image_url": raw_data.get("image_url", None),
                "features": raw_data.get("features", []),
                "description": raw_data.get("description", ""),
                "seller": raw_data.get("seller", None),
                "item_id": raw_data.get("item_id", None),
            }
            
            # Original price for discounted items - check multiple possible field names
            for orig_price_field in ['price_strikethrough', 'was_price', 'list_price', 'original_price', 'msrp', 'regular_price']:
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
            logger.error(f"Error extracting Walmart product data: {e}")
            return {} 