"""Walmart-specific Oxylabs scraping service."""

import logging
from typing import Any, Dict, List, Optional, Union
import asyncio
import re
import json

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
        self.search_source = "universal"  # Primary search source - Changed from walmart_search to universal
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
        
        # Log the result structure
        logger.info(f"Got search result with success={search_result.success}")
        if hasattr(search_result, 'source'):
            logger.info(f"Search result source: {search_result.source}")
        
        # Log the raw search result structure
        try:
            import json
            # Log the raw response structure to debug price extraction issues
            if search_result.success and search_result.results:
                logger.info("==== RAW WALMART RESPONSE STRUCTURE ====")
                if isinstance(search_result.results, list) and len(search_result.results) > 0:
                    # Log structure of first item
                    sample = search_result.results[0]
                    logger.info(f"Sample product structure: {json.dumps(sample, default=str)}")
                    
                    # Log price fields specifically if they exist
                    if isinstance(sample, dict):
                        logger.info(f"PRICE FIELDS - Direct price: {sample.get('price')}")
                        if 'price' in sample and isinstance(sample['price'], dict):
                            logger.info(f"PRICE FIELDS - Nested price object: {json.dumps(sample['price'], default=str)}")
                        if 'general' in sample and isinstance(sample['general'], dict) and 'price' in sample['general']:
                            logger.info(f"PRICE FIELDS - General.price: {sample['general'].get('price')}")
                elif isinstance(search_result.results, dict):
                    # Log keys of dictionary
                    logger.info(f"Response is dict with keys: {list(search_result.results.keys())}")
                    
                    # If content is present, log a sample from there
                    if 'content' in search_result.results and isinstance(search_result.results['content'], dict):
                        content = search_result.results['content']
                        logger.info(f"Content keys: {list(content.keys())}")
                        
                        if 'results' in content and isinstance(content['results'], list) and len(content['results']) > 0:
                            sample = content['results'][0]
                            logger.info(f"Sample product from content.results: {json.dumps(sample, default=str)}")
                            
                            # Log price fields specifically if they exist
                            if isinstance(sample, dict):
                                logger.info(f"PRICE FIELDS - Content sample price: {sample.get('price')}")
                                if 'price' in sample and isinstance(sample['price'], dict):
                                    logger.info(f"PRICE FIELDS - Content sample nested price: {json.dumps(sample['price'], default=str)}")
                                if 'general' in sample and isinstance(sample['general'], dict) and 'price' in sample['general']:
                                    logger.info(f"PRICE FIELDS - Content sample general.price: {sample['general'].get('price')}")
        except Exception as e:
            logger.error(f"Error logging raw search result structure: {e}")
        
        if isinstance(search_result.results, dict):
            logger.info(f"Search result keys: {list(search_result.results.keys())}")
        
        if search_result.success:
            if isinstance(search_result.results, dict):
                logger.info(f"Search result keys: {list(search_result.results.keys())}")
                # Try to log the first level of nesting for content
                if "content" in search_result.results:
                    content = search_result.results["content"]
                    if isinstance(content, dict):
                        logger.info(f"Content keys: {list(content.keys())}")
                    
                    # Try to log the second level (results field in content)
                    if isinstance(content, dict) and "results" in content:
                        results_obj = content["results"]
                        if isinstance(results_obj, list):
                            logger.info(f"Found {len(results_obj)} results in content.results list")
                        elif isinstance(results_obj, dict):
                            logger.info(f"Results is a dict with keys: {list(results_obj.keys())}")
                
            # Also check directly for array structure
            elif isinstance(search_result.results, list):
                logger.info(f"Search result is a direct list with {len(search_result.results)} items")
        
        # Special handling for universal scraper format
        if search_result.success and hasattr(search_result, 'source') and search_result.source == "universal":
            logger.info("Using universal scraper format for Walmart search results")
            
            # For universal format, the results might be structured differently
            if isinstance(search_result.results, dict) and "content" in search_result.results:
                content = search_result.results["content"]
                if "results" in content and isinstance(content["results"], list):
                    logger.info(f"Found {len(content['results'])} products in universal format")
                    search_result.results = content["results"]
                    
                    # Log a sample product if available
                    if content["results"] and len(content["results"]) > 0:
                        try:
                            sample = content["results"][0]
                            logger.info(f"Sample product keys: {list(sample.keys())}")
                            if "general" in sample:
                                logger.info(f"Sample product general keys: {list(sample['general'].keys())}")
                            if "price" in sample:
                                logger.info(f"Sample product price: {sample['price']}")
                        except Exception as e:
                            logger.error(f"Error logging sample product: {e}")
        
        # If we have a list of products, pre-process them for post-filtering compatibility
        if search_result.success and isinstance(search_result.results, list) and search_result.results:
            # Apply pre-processing to make products compatible with post-scraping filter
            original_count = len(search_result.results)
            search_result.results = self._preprocess_products_for_post_filter(search_result.results)
            logger.info(f"Pre-processed {original_count} products for post-filter compatibility")
            
            # Log a sample processed product for verification
            if search_result.results and len(search_result.results) > 0:
                try:
                    sample = search_result.results[0]
                    logger.info(f"Sample processed product keys: {list(sample.keys())}")
                    logger.info(f"Sample processed product price: {sample.get('price')}")
                    logger.info(f"Sample processed product title: {sample.get('title', '')[:50]}...")
                except Exception as e:
                    logger.error(f"Error logging sample processed product: {e}")
        
        # Fallback handling for universal source detection when 'source' attribute is missing
        elif search_result.success and isinstance(search_result.results, dict) and "content" in search_result.results:
            # This is likely from universal scraper based on structure
            logger.info("Detected probable universal scraper format based on structure")
            content = search_result.results["content"]
            if "results" in content and isinstance(content["results"], list):
                logger.info(f"Found {len(content['results'])} products in universal format structure")
                search_result.results = content["results"]
                
                # Log a sample product if available
                if content["results"] and len(content["results"]) > 0:
                    try:
                        sample = content["results"][0]
                        logger.info(f"Sample product keys: {list(sample.keys())}")
                        if "general" in sample:
                            logger.info(f"Sample product general keys: {list(sample['general'].keys())}")
                        if "price" in sample:
                            logger.info(f"Sample product price: {sample['price']}")
                    except Exception as e:
                        logger.error(f"Error logging sample product: {e}")
                
        # Additional handling for other structures:
        # Sometimes results are wrapped in specific objects
        elif search_result.success and isinstance(search_result.results, dict):
            # Look for products in common fields
            processed = False
            
            for field_name in ["items", "products", "search_results", "list"]:
                if field_name in search_result.results and isinstance(search_result.results[field_name], list):
                    logger.info(f"Found {len(search_result.results[field_name])} products in field '{field_name}'")
                    search_result.results = search_result.results[field_name]
                    processed = True
                    break
            
            # Special handling for complex nested structures
            if not processed and "content" in search_result.results:
                content = search_result.results["content"]
                
                # Check if content is a product list directly
                if isinstance(content, list):
                    logger.info(f"Content is a direct list with {len(content)} items")
                    search_result.results = content
                elif isinstance(content, dict):
                    # Try common product list fields
                    for field_name in ["items", "products", "search_results", "list"]:
                        if field_name in content and isinstance(content[field_name], list):
                            logger.info(f"Found {len(content[field_name])} products in content.{field_name}")
                            search_result.results = content[field_name]
                            processed = True
                            break
        
        # If results is a list but not of dicts, try to convert
        if search_result.success and isinstance(search_result.results, list):
            # Check if all items are dicts (valid products)
            are_all_dicts = all(isinstance(item, dict) for item in search_result.results)
            
            if not are_all_dicts:
                logger.warning("Results list contains non-dict items, filtering...")
                # Filter to keep only dict items
                search_result.results = [item for item in search_result.results if isinstance(item, dict)]
                logger.info(f"After filtering, {len(search_result.results)} valid products remain")
        
        # Check for empty results
        if search_result.success and (not search_result.results or len(search_result.results) == 0):
            logger.warning("Search returned success but empty results, checking for fallback formats")
            
            # Log the original structure
            try:
                import json
                logger.info(f"ORIGINAL SEARCH RESULT STRUCTURE: {json.dumps(search_result.results)}")
            except Exception as e:
                logger.error(f"Failed to serialize original results: {e}")
        
        # No need for additional processing if we don't have data or don't need details
        if not search_result.success or not extract_details:
            # Last chance to preprocess results before returning
            if search_result.success and isinstance(search_result.results, list) and search_result.results:
                logger.info("Final preprocessing of results before returning (non-detailed flow)")
                search_result.results = self._preprocess_products_for_post_filter(search_result.results)
            
            return search_result
        
        # If extract_details is True, we'll enrich the search results
        # with additional product data when available
        try:
            # Extract product IDs from search results
            product_ids = self._extract_product_ids_from_search(search_result.results)
            
            # Log the extracted IDs
            logger.info(f"Extracted {len(product_ids)} product IDs from search results")
            
            # Limit the number of product IDs to process
            product_ids = product_ids[:limit]
            
            # If no product IDs found, return the original results
            if not product_ids:
                logger.warning("No product IDs extracted, returning original results")
                return search_result
                
            # Process product IDs in batches for better performance
            all_product_details = {}
            
            for i in range(0, len(product_ids), batch_size):
                batch_ids = product_ids[i:i+batch_size]
                logger.info(f"Processing batch of {len(batch_ids)} product IDs")
                
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
                        product_data = self.extract_product_data(result.results[0] if isinstance(result.results, list) else result.results)
                        if product_data:
                            all_product_details[product_id] = product_data
                            logger.debug(f"Added detailed data for product {product_id}")
                        else:
                            logger.warning(f"Failed to extract product data for {product_id}")
            
            # Enhance the original search results with the detailed data
            enhanced_results = []
            logger.info(f"Enhancing {len(search_result.results)} search results with {len(all_product_details)} detailed products")
            
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
            logger.info(f"Final results contain {len(enhanced_results)} products")
            
            # Final preprocessing before returning
            if search_result.success and isinstance(search_result.results, list) and search_result.results:
                logger.info("Final preprocessing of enhanced results before returning")
                search_result.results = self._preprocess_products_for_post_filter(search_result.results)
            
            return search_result
            
        except Exception as e:
            logger.error(f"Error processing Walmart search results for detailed information: {e}", exc_info=True)
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

    def _preprocess_products_for_post_filter(self, products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Pre-process products to make them compatible with the post-scraping filter.
        
        This transforms the universal scraper product format into a structure that can be
        correctly processed by the post-scraping filter, particularly for price extraction.
        
        Args:
            products: List of product dictionaries from universal scraper
            
        Returns:
            List of transformed product dictionaries
        """
        if not products:
            return []
            
        processed_products = []
        logger.info(f"Pre-processing {len(products)} products for post-filter compatibility")
        
        for product in products:
            # Create a new product dictionary to avoid modifying the original
            processed_product = {}
            
            # Copy base product attributes
            for key, value in product.items():
                processed_product[key] = value
                
            # HANDLE PRICE - Extract from nested structure
            if "price" in product and isinstance(product["price"], dict):
                # If the price field is a dictionary, extract its components
                price_obj = product["price"]
                
                # Extract direct price value
                if "price" in price_obj:
                    # Set price as a direct attribute (what post_filter expects)
                    if isinstance(price_obj["price"], (int, float)):
                        processed_product["price"] = float(price_obj["price"])
                        logger.debug(f"Extracted direct numeric price: {processed_product['price']}")
                    elif isinstance(price_obj["price"], str):
                        try:
                            clean_price = re.sub(r'[^\d.]', '', price_obj["price"])
                            if clean_price:
                                processed_product["price"] = float(clean_price)
                                logger.debug(f"Extracted price from string: {processed_product['price']}")
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Failed to convert price string: {e}")
                
                # Extract currency if available
                if "currency" in price_obj:
                    processed_product["currency"] = price_obj["currency"]
                    
                # Handle price_strikethrough as original_price
                if "price_strikethrough" in price_obj:
                    strikethrough = price_obj["price_strikethrough"]
                    if isinstance(strikethrough, (int, float)):
                        processed_product["original_price"] = float(strikethrough)
                        logger.info(f"Preprocessing: Added original_price={float(strikethrough)} from price_strikethrough")
                    elif isinstance(strikethrough, str):
                        try:
                            clean_price = re.sub(r'[^\d.]', '', strikethrough)
                            if clean_price:
                                processed_product["original_price"] = float(clean_price)
                                logger.info(f"Preprocessing: Added original_price={float(clean_price)} from price_strikethrough string")
                        except (ValueError, TypeError):
                            pass
            
            # HANDLE GENERAL INFORMATION
            if "general" in product and isinstance(product["general"], dict):
                general = product["general"]
                
                # Extract the product ID if not already present
                if "product_id" in general and not processed_product.get("item_id"):
                    processed_product["item_id"] = general["product_id"]
                    
                # Extract title if not already present
                if "title" in general and not processed_product.get("title"):
                    processed_product["title"] = general["title"]
                    
                # Extract URL if not already present
                if "url" in general and not processed_product.get("url"):
                    url = general["url"]
                    if not url.startswith("http"):
                        url = f"https://www.walmart.com{url}"
                    processed_product["url"] = url
                    
                # Extract image if not already present
                if "image" in general and not processed_product.get("image_url"):
                    processed_product["image_url"] = general["image"]
            
            # HANDLE RATING
            if "rating" in product and isinstance(product["rating"], dict):
                rating_obj = product["rating"]
                
                # Extract rating value
                if "rating" in rating_obj:
                    processed_product["rating"] = rating_obj["rating"]
                    
                # Extract review count
                if "count" in rating_obj:
                    processed_product["reviews_count"] = rating_obj["count"]
            
            # HANDLE SELLER
            if "seller" in product and isinstance(product["seller"], dict):
                seller_obj = product["seller"]
                
                # Extract seller name
                if "name" in seller_obj:
                    processed_product["seller"] = seller_obj["name"]
                
                # Extract seller ID if available
                if "id" in seller_obj:
                    processed_product["seller_id"] = seller_obj["id"]
            
            # HANDLE SPONSORED/BADGE STATUS
            # Check for sponsored flag in general data
            if "general" in product and isinstance(product["general"], dict):
                general = product["general"]
                
                # Extract sponsored status
                if "sponsored" in general:
                    processed_product["sponsored"] = general["sponsored"]
                    
                # Extract badge if available (e.g., "Rollback", "Clearance", etc.)
                if "badge" in general:
                    processed_product["badge"] = general["badge"]
            
            # Ensure sponsored flag exists with default value if not present
            if "sponsored" not in processed_product:
                processed_product["sponsored"] = False
            
            # Guarantee that the item has a minimal price if none was extracted
            if "price" not in processed_product or processed_product["price"] is None:
                # Use 0.01 as a fallback price to avoid filtering out products
                processed_product["price"] = 0.01
                logger.debug(f"No price found, using fallback price: {processed_product['price']}")
            
            # Add the processed product to the list
            processed_products.append(processed_product)
            
        logger.info(f"Pre-processed {len(processed_products)} products for post-filter compatibility")
        return processed_products

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
            logger.warning("Empty raw data provided for Walmart product extraction")
            return {}
            
        # Extract data from parsed results
        try:
            # Log the raw data structure for debugging
            try:
                logger.debug(f"Extracting product data for Walmart product with keys: {list(raw_data.keys())}")
                # Add detailed logging of the raw data structure
                if "price" in raw_data:
                    logger.info(f"Raw price data: {raw_data.get('price')}")
                if "general" in raw_data and isinstance(raw_data["general"], dict):
                    if "price" in raw_data["general"]:
                        logger.info(f"Raw general.price data: {raw_data['general'].get('price')}")
            except Exception:
                logger.warning("Could not log raw_data keys due to an error")
            
            # Check if this is from universal scraper format (universal source)
            universal_format = False
            general_data = {}  # Initialize before conditional use
            
            if "general" in raw_data and isinstance(raw_data["general"], dict):
                universal_format = True
                logger.info("Detected universal scraper format for Walmart product")
                # Use safe copy to avoid reference issues
                try:
                    general_data = raw_data["general"].copy()
                    logger.debug(f"Universal scraper 'general' data keys: {list(general_data.keys())}")
                except Exception as e:
                    logger.error(f"Failed to create safe copy of general_data: {str(e)}")
                    general_data = {}  # Ensure it's at least an empty dict
            
            # Extract title - look in multiple places
            title = None
            if universal_format and "title" in general_data:
                title = general_data["title"]
            else:
                title = raw_data.get("title", "")
            
            # Extract product ID
            product_id = None
            if universal_format and "product_id" in general_data:
                product_id = general_data["product_id"]
            elif "id" in raw_data:
                product_id = raw_data["id"]
            elif "item_id" in raw_data:
                product_id = raw_data["item_id"]
            
            # Price handling with fallbacks
            price_value = 0.0
            currency = "USD"  # Default for Walmart
            original_price = None  # Initialize here to avoid reference in locals()
            
            # PRICE EXTRACTION LOGIC
            # 1. First try universal format price object
            if "price" in raw_data and isinstance(raw_data["price"], dict):
                price_dict = {}
                try:
                    price_dict = raw_data["price"].copy()  # Use safe copy
                    logger.debug(f"Found price dictionary with keys: {list(price_dict.keys())}")
                    
                    # Universal format standard - price field inside price dict
                    if "price" in price_dict and price_dict["price"] is not None:
                        try:
                            extracted_price = price_dict["price"]
                            logger.info(f"Direct price field found: {extracted_price} (type: {type(extracted_price).__name__})")
                            
                            # Handle different price formats
                            if isinstance(extracted_price, (int, float)):
                                price_value = float(extracted_price)
                                logger.info(f"Using numeric price: {price_value}")
                            elif isinstance(extracted_price, str):
                                # Clean the price string and convert
                                clean_price = re.sub(r'[^\d.]', '', extracted_price)
                                if clean_price:
                                    price_value = float(clean_price)
                                    logger.info(f"Converted string price '{extracted_price}' to: {price_value}")
                            
                            logger.debug(f"Extracted price value: {price_value}")
                            
                            # Get currency if available
                            if "currency" in price_dict:
                                currency = price_dict["currency"]
                                logger.info(f"Found currency: {currency}")
                            
                            # Check for original/strikethrough price
                            if "price_strikethrough" in price_dict and price_dict["price_strikethrough"] is not None:
                                try:
                                    strikethrough = price_dict["price_strikethrough"]
                                    logger.info(f"Found strikethrough price: {strikethrough}")
                                    if isinstance(strikethrough, (int, float)):
                                        original_price = float(strikethrough)
                                    elif isinstance(strikethrough, str):
                                        clean_price = re.sub(r'[^\d.]', '', strikethrough)
                                        if clean_price:
                                            original_price = float(clean_price)
                                except (ValueError, TypeError) as e:
                                    logger.warning(f"Error converting strikethrough price: {e}")
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Error converting price from price dict: {e}")
                except Exception as e:
                    logger.warning(f"Error processing price dictionary: {e}")
            
            # 2. If price is still 0, try nested price fields in price object
            if price_value == 0.0 and "price" in raw_data and isinstance(raw_data["price"], dict):
                try:
                    price_obj = raw_data["price"]
                    # Try different price field names
                    for field in ["current_price", "current", "value", "amount"]:
                        if field in price_obj and price_obj[field] is not None:
                            try:
                                logger.info(f"Checking alternative price field '{field}': {price_obj[field]}")
                                if isinstance(price_obj[field], (int, float)):
                                    price_value = float(price_obj[field])
                                    logger.info(f"Extracted price from price.{field}: {price_value}")
                                    break
                                elif isinstance(price_obj[field], str):
                                    clean_price = re.sub(r'[^\d.]', '', price_obj[field])
                                    if clean_price:
                                        price_value = float(clean_price)
                                        logger.info(f"Extracted price from price.{field} string: {price_value}")
                                        break
                            except (ValueError, TypeError) as e:
                                logger.warning(f"Error converting nested price '{price_obj[field]}': {e}")
                except Exception as e:
                    logger.warning(f"Error processing nested price fields: {e}")
            
            # 3. If still not found, try top-level fields
            if price_value == 0.0:
                for field in ['current_price', 'price_amount', 'sale_price', 'final_price', 'price']:
                    if field in raw_data and raw_data[field] is not None:
                        try:
                            logger.info(f"Checking top-level price field '{field}': {raw_data[field]}")
                            if isinstance(raw_data[field], (int, float)):
                                price_value = float(raw_data[field])
                                logger.info(f"Extracted price from {field}: {price_value}")
                                break
                            elif isinstance(raw_data[field], str):
                                clean_price = re.sub(r'[^\d.]', '', raw_data[field])
                                if clean_price:
                                    price_value = float(clean_price)
                                    logger.info(f"Extracted price from {field} string: {price_value}")
                                    break
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Error converting top-level price '{raw_data[field]}': {e}")
                            continue
            
            # Create standardized product data structure with guaranteed price
            product_data = {
                "title": title or "Unknown Product",
                "price": price_value or 0.01,  # Always set a price value, default to 0.01
                "currency": currency,
                "item_id": product_id or raw_data.get("item_id", None) or "unknown",
            }
            
            # Add URL
            url = None
            if universal_format and "url" in general_data:
                url = general_data["url"]
            else:
                url = raw_data.get("url")
                
            if url and isinstance(url, str):
                # Make sure URL is absolute
                if not url.startswith("http"):
                    url = f"https://www.walmart.com{url}"
                product_data["url"] = url
            
            # Only include non-empty values for optional fields
            optional_fields = {
                "rating": self._safe_value(raw_data.get("rating")),
                "reviews_count": self._safe_value(raw_data.get("reviews_count")),
                "availability": raw_data.get("availability"),
                "image_url": raw_data.get("image_url"),
                "features": self._safe_list_copy(raw_data.get("features", [])),
                "description": raw_data.get("description"),
                "seller": raw_data.get("seller"),
            }
            
            # Add optional fields if they have values
            for key, value in optional_fields.items():
                if value not in (None, "", [], {}):  # Skip empty values
                    product_data[key] = value
            
            # For seller in universal format
            if universal_format and "seller" in raw_data and isinstance(raw_data["seller"], dict):
                seller = raw_data["seller"]
                if "name" in seller:
                    product_data["seller"] = seller["name"]
                if "id" in seller:
                    product_data["seller_id"] = seller["id"]
            
            # Handle sponsored flag and badge
            if universal_format and "general" in raw_data:
                general = raw_data["general"]
                if "sponsored" in general:
                    product_data["sponsored"] = general["sponsored"]
                if "badge" in general:
                    product_data["badge"] = general["badge"]
            
            # Ensure sponsored flag exists with default value if not present
            if "sponsored" not in product_data:
                product_data["sponsored"] = False
            
            # If we have an original price, add it
            if original_price is not None:
                product_data["original_price"] = original_price
                logger.info(f"Added original_price: {original_price} for product: {title[:30]}...")
            
            # Ensure we have item_id (repeat this for safety)
            if not product_data["item_id"] or product_data["item_id"] == "unknown":
                if "id" in raw_data:
                    product_data["item_id"] = raw_data["id"]
            
            # Image URL fallback
            if "image_url" not in product_data or not product_data["image_url"]:
                if universal_format and "image" in general_data:
                    product_data["image_url"] = general_data["image"]
                else:
                    for img_field in ["image", "images", "thumbnail", "primary_image"]:
                        if img_field in raw_data and raw_data[img_field]:
                            # Handle both string and list formats for images
                            if isinstance(raw_data[img_field], str):
                                product_data["image_url"] = raw_data[img_field]
                                break
                            elif isinstance(raw_data[img_field], list) and raw_data[img_field]:
                                # Take first image if it's a list
                                if isinstance(raw_data[img_field][0], str):
                                    product_data["image_url"] = raw_data[img_field][0]
                                elif isinstance(raw_data[img_field][0], dict) and "url" in raw_data[img_field][0]:
                                    product_data["image_url"] = raw_data[img_field][0]["url"]
                                break

            # Universal format may have specifications in its own field
            if universal_format and "specifications" in raw_data and isinstance(raw_data["specifications"], list):
                product_data["specifications"] = self._safe_list_copy(raw_data["specifications"])

            # Log final product data for debugging
            try:
                logger.info(f"Final Walmart product data: price={product_data['price']}, currency={product_data['currency']}, title={product_data.get('title', '')[:30]}...")
                
                # Add a SAMPLE log of the complete structure for debugging (limit to first product)
                if product_id and (product_id.endswith('1') or product_id.endswith('0')):
                    logger.info(f"SAMPLE PRODUCT DATA: {json.dumps(product_data)}")
            except Exception:
                logger.debug("Created final Walmart product data (could not log details)")
            
            return product_data
            
        except Exception as e:
            logger.error(f"Error extracting Walmart product data: {e}", exc_info=True)
            # Return minimal data to avoid breaking client code
            return {
                "title": raw_data.get("title", "Unknown Product"),
                "price": 0.01,  # Minimal price 
                "currency": "USD",
                "item_id": raw_data.get("id") or raw_data.get("item_id", "unknown")
            }
            
    def _safe_value(self, value):
        """Create a safe copy of a value to prevent recursion issues.
        
        Args:
            value: The value to create a safe copy of
            
        Returns:
            A safe copy of the value that can be serialized to JSON
        """
        # Stack-based approach to avoid recursion issues
        if value is None:
            return None
            
        # Handle primitive types directly for efficiency
        if isinstance(value, (str, int, float, bool)):
            return value
            
        # For complex types, use simple representation
        try:
            if isinstance(value, dict):
                # For dictionaries, only include simple key-value pairs to avoid recursion
                return {k: self._safe_primitive(v) for k, v in value.items() 
                        if not k.startswith('_') and not callable(v)}
                        
            elif isinstance(value, (list, tuple)):
                # For lists, only include simple values to avoid recursion
                return [self._safe_primitive(item) for item in value]
                
            else:
                # For other types, just use string representation
                return str(value)
                
        except Exception as e:
            logger.warning(f"Error in _safe_value: {e}")
            return str(value) if value is not None else None
            
    def _safe_primitive(self, value):
        """Convert a value to a primitive type that can be serialized to JSON.
        
        Args:
            value: The value to convert
            
        Returns:
            A primitive version of the value
        """
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        elif isinstance(value, dict):
            # Only include a few key-value pairs to avoid deep nesting
            simple_dict = {}
            for k, v in list(value.items())[:5]:  # Limit to 5 keys
                if isinstance(v, (str, int, float, bool, type(None))):
                    simple_dict[k] = v
            return simple_dict
        elif isinstance(value, (list, tuple)):
            # Only include primitive values from the list
            simple_list = []
            for item in list(value)[:5]:  # Limit to 5 items
                if isinstance(item, (str, int, float, bool, type(None))):
                    simple_list.append(item)
                else:
                    simple_list.append(str(item))
            return simple_list
        else:
            # Convert everything else to string
            return str(value)
            
    def _safe_list_copy(self, lst):
        """Create a safe copy of a list that can be serialized to JSON.
        
        Args:
            lst: The list to copy
            
        Returns:
            A safe copy of the list
        """
        if not isinstance(lst, (list, tuple)):
            return []
        
        # Use the same primitive handling approach for consistency
        try:
            return [self._safe_primitive(item) for item in lst[:10]]  # Limit to 10 items for safety
        except Exception as e:
            logger.warning(f"Error in _safe_list_copy: {e}")
            return [] 