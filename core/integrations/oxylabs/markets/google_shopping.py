"""Google Shopping-specific Oxylabs scraping service."""

import logging
from typing import Any, Dict, List, Optional, Union
import asyncio
import re

from core.integrations.oxylabs.market_base import OxylabsMarketBaseService, OxylabsResult
from core.integrations.oxylabs.utils import extract_price, detect_currency

logger = logging.getLogger(__name__)


class GoogleShoppingOxylabsService(OxylabsMarketBaseService):
    """Service for scraping Google Shopping using Oxylabs."""

    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        """Initialize Google Shopping Oxylabs service.
        
        Args:
            username: Oxylabs username
            password: Oxylabs password
        """
        super().__init__(username, password)
        # Set Google Shopping-specific source configurations
        self.search_source = "google_shopping_search"
        self.product_source = "google_shopping_product"
        self.fallback_source = "universal"
        self.market_name = "Google Shopping"

    async def search_products(
        self, 
        query: str,
        limit: int = 10,
        region: Optional[str] = None,
        sort_by: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        parse: bool = True,
        cache_ttl: Optional[int] = None,
        domain: str = "com",
        start_page: int = 1,
        pages: int = 1,
        extract_details: bool = False,
        batch_size: int = 10,
        **kwargs
    ) -> OxylabsResult:
        """Search for products on Google Shopping.
        
        Args:
            query: Search query
            limit: Maximum number of results
            region: Region or country code for geo-location
            sort_by: Sorting option (r=relevance, rv=reviews, p=price asc, pd=price desc)
            min_price: Minimum price filter
            max_price: Maximum price filter
            parse: Whether to parse the results automatically
            cache_ttl: Cache time-to-live in seconds (None for no caching)
            domain: Domain localization for Google (e.g., 'com', 'co.uk')
            start_page: Starting page number
            pages: Number of pages to retrieve
            extract_details: If True, attempt to extract additional details for each product
            batch_size: Number of products to process in a single batch (for optimization)
            **kwargs: Additional parameters including:
                - locale: Accept-Language header value (interface language)
                - results_language: Results language
                - nfpr: Turn off spelling auto-correction (true/false)
            
        Returns:
            OxylabsResult object with search results
        """
        # Build parameters with base implementation
        params = self._prepare_search_params(
            query=query,
            limit=limit,
            parse=parse,
            region=region,
            sort_by=None,  # We'll handle sort_by specially for Google
            min_price=min_price,
            max_price=max_price,
            **kwargs
        )
        
        # Add Google Shopping-specific parameters
        params["domain"] = domain
        params["start_page"] = start_page
        params["pages"] = pages
        
        # Build context array for additional parameters
        context = params.get("context", [])
        
        # Add sorting parameter if provided with Google's special format
        if sort_by is not None:
            if sort_by in ["r", "rv", "p", "pd"]:
                context.append({"key": "sort_by", "value": sort_by})
                
        # Add results language if provided
        if "results_language" in kwargs:
            results_language = kwargs.pop("results_language")
            context.append({"key": "results_language", "value": results_language})
            
        # Add nfpr (no spell correction) if provided
        if "nfpr" in kwargs:
            nfpr = kwargs.pop("nfpr")
            context.append({"key": "nfpr", "value": nfpr})
        
        # Update context if we have any parameters
        if context:
            params["context"] = context
        
        # Add locale if provided
        if "locale" in kwargs:
            params["locale"] = kwargs.pop("locale")
            
        # Add user_agent_type if provided or default to desktop
        if "user_agent_type" in kwargs:
            params["user_agent_type"] = kwargs.pop("user_agent_type")
        else:
            params["user_agent_type"] = "desktop"
            
        # Log the final parameters for debugging
        logger.info(f"Google Shopping search - Query: {query}, Domain: {domain}")
        logger.debug(f"Google Shopping search parameters: {params}")
        
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
                        domain=domain,
                        parse=True,
                        cache_ttl=cache_ttl
                    ) for product_id in batch_ids
                ]
                
                # Wait for all batch requests to complete
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                # Process results from the batch
                for product_id, result in zip(batch_ids, batch_results):
                    if isinstance(result, Exception):
                        logger.warning(f"Error fetching details for Google Shopping product {product_id}: {result}")
                        continue
                        
                    if result and result.success and result.results:
                        # Extract and store the detailed product data
                        all_product_details[product_id] = self.extract_product_data(result.results[0] if result.results else {})
            
            # Enhance the original search results with the detailed data
            enhanced_results = []
            
            for product in search_result.results:
                product_id = product.get("product_id") or product.get("item_id") or product.get("id")
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
            logger.error(f"Error processing Google Shopping search results for detailed information: {e}")
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
            product_id = product.get("product_id") or product.get("item_id") or product.get("id")
            if product_id:
                product_ids.append(product_id)
                
        return product_ids

    async def get_product_details(
        self, 
        product_id: str,
        region: Optional[str] = None,
        parse: bool = True,
        cache_ttl: Optional[int] = None,
        domain: str = "com",
        **kwargs
    ) -> OxylabsResult:
        """Get details of a specific product on Google Shopping.
        
        Args:
            product_id: Google Shopping product ID
            region: Region or country code for geo-location
            parse: Whether to parse the results automatically
            cache_ttl: Cache time-to-live in seconds (None for no caching)
            domain: Domain localization for Google (e.g., 'com', 'co.uk')
            **kwargs: Additional parameters including:
                - locale: Accept-Language header value (interface language)
            
        Returns:
            OxylabsResult object with product details
        """
        # Build parameters with base implementation
        params = self._prepare_product_params(
            product_id=product_id,
            parse=parse,
            region=region,
            **kwargs
        )
        
        # Add Google Shopping-specific parameters
        params["domain"] = domain
        params["product_id"] = product_id
        
        # Add locale if provided
        if "locale" in kwargs:
            params["locale"] = kwargs.pop("locale")
            
        # Add user_agent_type if provided or default to desktop
        if "user_agent_type" in kwargs:
            params["user_agent_type"] = kwargs.pop("user_agent_type")
        else:
            params["user_agent_type"] = "desktop"
            
        # Log the final parameters for debugging
        logger.info(f"Google Shopping product details - Product ID: {product_id}, Domain: {domain}")
        logger.debug(f"Google Shopping product details parameters: {params}")
        
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
                    # Default to USD if detection fails
                    currency = "USD"
            
            # Handle image data - check multiple possible fields
            image_url = None
            
            # First check direct image_url field
            if "image_url" in raw_data and raw_data["image_url"]:
                image_url = raw_data["image_url"]
            # Then check thumbnail field which is common in Google Shopping
            elif "thumbnail" in raw_data and raw_data["thumbnail"]:
                image_url = raw_data["thumbnail"]
                logger.info(f"Using thumbnail as image_url: {image_url}")
            # Also check other possible image field names
            elif "image" in raw_data and raw_data["image"]:
                image_url = raw_data["image"]
            elif "images" in raw_data and raw_data["images"] and isinstance(raw_data["images"], list) and len(raw_data["images"]) > 0:
                # If images is a list, take the first one
                image_url = raw_data["images"][0]
                
            # Create standardized product data structure
            product_data = {
                "title": title,
                "price": price_value,
                "currency": currency,
                "rating": raw_data.get("rating", None),
                "reviews_count": raw_data.get("reviews_count", None),
                "availability": raw_data.get("availability", None),
                "image_url": image_url,
                "seller": raw_data.get("seller", None),
                "description": raw_data.get("description", ""),
                "item_id": raw_data.get("item_id", None),
                "variants": raw_data.get("variants", []),
                "category": raw_data.get("category", None),
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
            logger.error(f"Error extracting Google Shopping product data: {e}")
            return {} 