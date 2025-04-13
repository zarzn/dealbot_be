"""Amazon-specific Oxylabs scraping service."""

import logging
from typing import Any, Dict, List, Optional, Union
import asyncio
import json
import re
import urllib.parse
import time

from core.integrations.oxylabs.market_base import OxylabsMarketBaseService, OxylabsResult
from core.integrations.oxylabs.utils import extract_price, detect_currency

logger = logging.getLogger(__name__)


class AmazonOxylabsService(OxylabsMarketBaseService):
    """Service for scraping Amazon using Oxylabs."""

    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        """Initialize Amazon Oxylabs service.
        
        Args:
            username: Oxylabs username
            password: Oxylabs password
        """
        super().__init__(username, password)
        # Set Amazon-specific source configurations
        self.search_source = "amazon_search"
        self.product_source = "amazon_product"
        self.fallback_source = "universal"
        self.market_name = "Amazon"
        
        # Cache TTL settings
        self.default_cache_ttl = 3600  # 1 hour default cache
        
        # Amazon-specific domain mapping
        self.domain_mapping = {
            "us": "com",  # US maps to .com domain
            "uk": "co.uk",
            "jp": "co.jp",
            "ca": "ca",
            "au": "com.au",
            "de": "de",
            "fr": "fr",
            "it": "it",
            "es": "es",
            "in": "in",
            "mx": "com.mx",
            "br": "com.br",
            "sg": "com.sg",
            "ae": "ae",
            "sa": "sa",
            "nl": "nl",
            "se": "se",
            "pl": "pl",
            "tr": "com.tr"
        }
        
    def _get_domain(self, region: str) -> str:
        """Get Amazon domain for a given region.
        
        Args:
            region: Region code (us, uk, de, etc.)
            
        Returns:
            Domain suffix for the region
        """
        region = region.lower() if region else "us"
        return self.domain_mapping.get(region, "com")  # Default to .com
        
    def _get_geo_location(self, region: str) -> str:
        """Get geo location string for a given region.
        
        Args:
            region: Region code
            
        Returns:
            Geo location string for Oxylabs
        """
        # Map region codes to geo location strings
        geo_mapping = {
            "us": "united_states",
            "uk": "united_kingdom",
            "ca": "canada",
            "au": "australia",
            "de": "germany",
            "fr": "france",
            "it": "italy",
            "es": "spain",
            "in": "india",
            "jp": "japan",
            "mx": "mexico",
            "br": "brazil"
        }
        
        region = region.lower() if region else "us"
        return geo_mapping.get(region, "united_states")  # Default to US
        
    async def search_products(
        self, 
        query: str, 
        region: str = "us", 
        limit: int = None,
        page: int = 1,
        pages: int = 1,
        parse: bool = True,
        geo_location: Optional[str] = None,
        category: Optional[str] = None,
        **kwargs
    ) -> OxylabsResult:
        """Search for products on Amazon.
        
        Args:
            query: Search query
            region: Amazon region (default: us)
            limit: Maximum number of results to return (optional, legacy parameter)
            page: Page number to fetch (default: 1)
            pages: Number of pages to fetch (default: 1)
            parse: Whether to parse results (default: True)
            geo_location: Geo location for the request (default: None)
            category: Category to filter results (default: None)
            **kwargs: Additional parameters for the search
        
        Returns:
            OxylabsResult object containing search results
        """
        try:
            # Log the search
            logger.info(f"Searching Amazon for '{query}' in region '{region}'")
            
            # Set up parameters
            cache_key = f"amazon:search:{region}:{query}:{page}:{pages}:{category}"
            cache_ttl = kwargs.pop("cache_ttl", self.default_cache_ttl)

            # Check cache for existing results
            cached_result = await self._get_from_cache(cache_key)
            if cached_result:
                logger.info(f"Using cached Amazon search results for '{query}'")
                return cached_result
            
            # Extract optional parameters
            sort_by = kwargs.get("sort_by")
            min_price = kwargs.get("min_price")
            max_price = kwargs.get("max_price")
            
            # Make the request to Oxylabs with proper parameters for amazon_search
            # The amazon_search source doesn't work with url parameter, use query and domain directly
            params = {
                "source": self.search_source,
                "domain": self._get_domain(region),  # e.g., "com" for US
                "query": query,
                "parse": parse,
                "user_agent_type": "desktop",
                "page": page,
                "pages": pages
            }
            
            # Add sorting if specified
            if sort_by:
                params["sort_by"] = sort_by

            # Add price filters if specified
            if min_price is not None:
                params["min_price"] = min_price
            if max_price is not None:
                params["max_price"] = max_price
                
            # Add limit for results if specified (for backwards compatibility)
            if limit:
                params["limit"] = limit
            
            # Add any remaining custom parameters
            params.update({k: v for k, v in kwargs.items() if k not in ["cache_ttl", "geo_location", "category"]})
            
            # Note: category parameter is intentionally not added to params as it's not supported by the Amazon parser API
            # It's kept in the method signature and cache key for post-processing purposes
            
            # Execute the request
            start_time = time.time()
            response = await self.scrape_url(params, cache_ttl=cache_ttl)
            response_time = time.time() - start_time
            
            # Process the raw results to extract products
            raw_results = response.raw_results
            products = []
            
            # Log the raw results structure for debugging
            logger.info(f"Amazon search - Processing raw results structure: {type(raw_results)}")
            
            # Add more detailed debugging to see the actual structure
            if isinstance(raw_results, dict):
                logger.info(f"Amazon search - Raw results keys: {list(raw_results.keys())}")
                
                # Extract from top-level results
                if "results" in raw_results:
                    # Direct debug of the results field structure
                    logger.info(f"Amazon search - Results field type: {type(raw_results['results'])}")
                    
                    if isinstance(raw_results["results"], list) and len(raw_results["results"]) > 0:
                        # Check if this is a list of products or if it contains a single item with content
                        if len(raw_results["results"]) == 1 and isinstance(raw_results["results"][0], dict) and "content" in raw_results["results"][0]:
                            # This is likely the case where results[0] contains content with organic/paid structure
                            content = raw_results["results"][0]["content"]
                            if isinstance(content, dict) and "results" in content:
                                results_obj = content["results"]
                                all_products = []
                                
                                # Check for organic/paid structure
                                if isinstance(results_obj, dict):
                                    if "organic" in results_obj and isinstance(results_obj["organic"], list):
                                        organic_count = len(results_obj["organic"])
                                        logger.info(f"Amazon search - Found {organic_count} organic products in nested content")
                                        all_products.extend(results_obj["organic"])
                                    
                                    if "paid" in results_obj and isinstance(results_obj["paid"], list):
                                        paid_count = len(results_obj["paid"])
                                        logger.info(f"Amazon search - Found {paid_count} paid products in nested content")
                                        all_products.extend(results_obj["paid"])
                                    
                                    if all_products:
                                        products = all_products
                                        logger.info(f"Amazon search - Found {len(products)} total products in nested content structure")
                        else:
                            # Direct list of product items
                            products = raw_results["results"]
                            logger.info(f"Amazon search - Found {len(products)} products in top-level 'results' list")
            
            # Log the total number of products found
            logger.info(f"Total processed Amazon products: {len(products)}")
            
            # Process the results to extract products - very specific structure handling for Amazon
            if products:
                # No longer limiting the number of results - client should decide how many to use
                response.results = products
                logger.info(f"Returning {len(products)} Amazon products")
            else:
                logger.warning("No products extracted from Amazon search results")
            
            return response
        except Exception as e:
            logger.error(f"Error searching Amazon: {str(e)}")
            return OxylabsResult(
                success=False,
                results=[],
                errors=[str(e)],
                start_url=f"amazon_search:domain={self._get_domain(region)},query={query}"
            )

    async def get_product_details(
        self, 
        product_id: str, 
        region: Optional[str] = "us",
        parse: bool = True,
        cache_ttl: Optional[int] = None,
        **kwargs
    ) -> OxylabsResult:
        """Get details of a specific product on Amazon.
        
        Args:
            product_id: Amazon product ID (ASIN)
            region: Country code (e.g., 'us', 'uk')
            parse: Whether to parse the results automatically
            cache_ttl: Cache time-to-live in seconds (None for no caching)
            **kwargs: Additional parameters for the request
            
        Returns:
            OxylabsResult object with product details
        """
        # Map country code to domain (most countries use their code as domain)
        # Always convert to lowercase to ensure consistent handling
        country = region.lower() if region else "us"
        
        # Add debug logging before domain mapping
        logger.info(f"Amazon product details - Original country code: {country}")
        
        # Map country to domain
        domain = self.domain_mapping.get(country, country)
        logger.info(f"Amazon product details - Mapped domain from {country} to {domain}")
            
        # Override with Amazon-specific parameters
        params = {
            "source": self.product_source,
            "domain": domain,
            "asin": product_id,
            "parse": parse
        }
        
        # Explicitly log for debugging
        logger.info(f"Amazon product details - Using source: {self.product_source}")
        logger.info(f"Amazon product details - Using domain: {domain}")
        
        # Handle currency if provided
        if "currency" in kwargs:
            params["currency"] = kwargs.pop("currency")
        
        # Add any remaining custom parameters
        params.update({k: v for k, v in kwargs.items() if k not in ["cache_ttl", "geo_location"]})
        
        # Log the final parameters for debugging
        logger.info(f"Amazon product details - ASIN: {product_id}, Domain: {domain}")
        logger.debug(f"Amazon product details parameters: {params}")
        
        # Execute with standardized fallback handling
        return await self._execute_with_fallback(params, cache_ttl, "product details")

    def _enforce_result_limit(self, data: Dict[str, Any], limit: int) -> None:
        """Enforce the result limit on the search data.
        
        Args:
            data: The search result data
            limit: Maximum number of results to keep
        """
        if not data or not isinstance(data, dict):
            return
            
        # Handle different result formats
        if "content" in data and "results" in data["content"]:
            results = data["content"]["results"]
            
            # Handle different result structures
            if "organic" in results and isinstance(results["organic"], list):
                results["organic"] = results["organic"][:limit]
                
            if "paid" in results and isinstance(results["paid"], list):
                # Keep a few sponsored results but prioritize organic
                if "organic" in results and isinstance(results["organic"], list):
                    organic_count = len(results["organic"])
                    # Keep a balanced mix of organic and paid results within the limit
                    max_paid = max(2, limit - organic_count)
                    results["paid"] = results["paid"][:max_paid]
                else:
                    results["paid"] = results["paid"][:limit]
                    
        # Direct results list format
        elif "results" in data and isinstance(data["results"], list):
            data["results"] = data["results"][:limit]

    async def _process_search_results(
        self,
        data: Union[List[Dict[str, Any]], Dict[str, Any]],
        country: str,
        limit: int,
        batch_size: int,
        cache_ttl: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Process search results to add more detailed information.
        
        Args:
            data: The search result data
            country: Country code
            limit: Maximum number of results
            batch_size: Number of products to process in a batch
            cache_ttl: Cache TTL for product detail requests
            
        Returns:
            Processed data with enhanced product information
        """
        # Convert data to a list if it's not already
        products_list = []
        
        if isinstance(data, list):
            products_list = data
        elif isinstance(data, dict):
            # Handle Amazon's specific nested structure with paid and organic results
            if "paid" in data and isinstance(data["paid"], list):
                products_list.extend(data["paid"])
            
            if "organic" in data and isinstance(data["organic"], list):
                products_list.extend(data["organic"])
                
            # If no products found yet, try different paths for extracting products
            if not products_list:
                if "results" in data:
                    # Handle case where results itself might be an object with paid/organic
                    results = data["results"]
                    if isinstance(results, dict):
                        if "paid" in results and isinstance(results["paid"], list):
                            products_list.extend(results["paid"])
                        
                        if "organic" in results and isinstance(results["organic"], list):
                            products_list.extend(results["organic"])
                    elif isinstance(results, list):
                        products_list = results
                elif "content" in data and isinstance(data["content"], dict):
                    content = data["content"]
                    if "organic" in content and isinstance(content["organic"], list):
                        products_list.extend(content["organic"])
                    elif "results" in content and isinstance(content["results"], list):
                        products_list.extend(content["results"])
                    elif "paid" in content and isinstance(content["paid"], list):
                        products_list.extend(content["paid"])
        
        # Log what we found
        logger.info(f"Amazon search - Found {len(products_list)} products to process")
        
        # If no products found, return empty list
        if not products_list:
            logger.warning("No products found in Amazon search results to process")
            return []
            
        # Limit the number of products to process
        products_list = products_list[:limit]
        
        # Extract product IDs for batch processing
        asin_list = []
        
        for product in products_list:
            asin = product.get("asin") or product.get("product_id") or product.get("id")
            if asin:
                asin_list.append(asin)
                
        # If no ASINs found, return the original product list
        if not asin_list:
            logger.warning("No ASINs found in Amazon search results")
            return products_list
            
        # Log the number of products to be processed
        logger.info(f"Amazon search - Processing {len(asin_list)} products for detailed information")
        
        # Process ASINs in batches for better performance
        all_product_details = {}
        
        for i in range(0, len(asin_list), batch_size):
            batch_asins = asin_list[i:i+batch_size]
            
            logger.debug(f"Amazon search - Processing batch {i//batch_size+1} with {len(batch_asins)} products")
            
            # Process each batch concurrently
            batch_tasks = [
                self.get_product_details(
                    asin, 
                    region=country, 
                    parse=True,
                    cache_ttl=cache_ttl
                ) for asin in batch_asins
            ]
            
            # Wait for all batch requests to complete
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Process results from the batch
            for asin, result in zip(batch_asins, batch_results):
                if isinstance(result, Exception):
                    logger.warning(f"Error fetching details for Amazon product {asin}: {result}")
                    continue
                    
                if result and result.success and result.results:
                    # Extract the product data from the result
                    result_data = result.results
                    # Handle both list and dict result formats
                    if isinstance(result_data, list) and result_data:
                        result_data = result_data[0]
                    # Store the detailed product data
                    all_product_details[asin] = self.extract_product_data(result_data)
        
        # Log successful detailed product retrievals
        logger.info(f"Amazon search - Successfully retrieved detailed information for {len(all_product_details)} out of {len(asin_list)} products")
        
        # Enhance the original search results with the detailed data
        enhanced_products = []
        
        for product in products_list:
            asin = product.get("asin") or product.get("product_id") or product.get("id")
            if asin and asin in all_product_details:
                # Merge the detailed data with the search result
                detailed_data = all_product_details[asin]
                for key, value in detailed_data.items():
                    if key not in product or not product[key]:
                        product[key] = value
                
                # Ensure price is properly set
                if "price" not in product or product["price"] is None:
                    if "price" in detailed_data and detailed_data["price"] is not None:
                        product["price"] = detailed_data["price"]
                
                # Add original price if available
                if "original_price" in detailed_data and detailed_data["original_price"]:
                    product["original_price"] = detailed_data["original_price"]
                    
                # Add discount information if available
                if "discount_percentage" in detailed_data and detailed_data["discount_percentage"]:
                    product["discount_percentage"] = detailed_data["discount_percentage"]
            
            # Make sure price exists and is a number
            if "price" in product and product["price"]:
                if isinstance(product["price"], str):
                    try:
                        # Extract just the numeric part
                        price_str = ''.join(c for c in product["price"] if c.isdigit() or c == '.')
                        product["price"] = float(price_str)
                    except (ValueError, TypeError):
                        # If conversion fails, set a default price to avoid filtering
                        logger.warning(f"Could not convert price string to float: {product['price']}")
                        product["price"] = 0
            
            enhanced_products.append(product)

        logger.info(f"Amazon search - Completed enhancing search results with detailed product information")
        return enhanced_products

    def extract_product_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract product data from response.
        
        Args:
            data: Raw product data from Oxylabs
            
        Returns:
            Dict with extracted product data including original price when available
        """
        if not data:
            return {}
        
        logger.debug(f"Extracting product data from raw data structure: {str(type(data))}")
            
        # Get content if present
        content = None
        if "content" in data:
            content = data["content"]
        else:
            content = data
            
        # Extract product details from the response
        product_data = {}
        
        # Basic product information - support multiple field name variations
        product_data["asin"] = (
            content.get("asin", "") or 
            content.get("product_id", "") or 
            content.get("id", "")
        )
        
        product_data["title"] = (
            content.get("title", "") or 
            content.get("name", "")
        )
        
        # Handle price fields - support multiple variations
        price_value = None
        price_raw = content.get("price")
        
        if price_raw is not None:
            if isinstance(price_raw, (int, float)):
                price_value = float(price_raw)
            elif isinstance(price_raw, str) and price_raw.strip():
                # Try to extract numeric price from string
                try:
                    # Strip currency symbols and commas
                    cleaned_price = re.sub(r'[^\d.]', '', price_raw)
                    if cleaned_price:
                        price_value = float(cleaned_price)
                except (ValueError, TypeError):
                    logger.warning(f"Failed to parse price from string: {price_raw}")
        
        # Fallback to price_upper if main price not found
        if price_value is None and "price_upper" in content:
            try:
                price_value = float(content["price_upper"])
            except (ValueError, TypeError):
                pass
                
        product_data["price"] = price_value
        
        # Handle the currency
        currency = content.get("currency", "USD")
        if isinstance(currency, str) and currency.strip():
            product_data["currency"] = currency
        else:
            product_data["currency"] = "USD"  # Default currency
        
        # Handle ratings with multiple possible structures
        rating_data = content.get("rating", {})
        if rating_data:
            if isinstance(rating_data, dict):
                product_data["rating"] = rating_data.get("rating", None)
                product_data["rating_count"] = rating_data.get("rating_count", None)
            elif isinstance(rating_data, (int, float)):
                product_data["rating"] = rating_data
                # Look for rating count in other locations
                product_data["rating_count"] = content.get("rating_count", None)
        
        # Reviews count can be in multiple locations
        product_data["reviews_count"] = (
            content.get("reviews_count", None) or
            content.get("review_count", None)
        )
        
        # Product URL and image
        product_data["url"] = content.get("url", "")
        
        # Handle various image field names
        image_url = None
        if "url_image" in content and content["url_image"]:
            image_url = content["url_image"]
            logger.debug(f"Using url_image for product: {product_data.get('asin', 'unknown')}: {image_url}")
        elif "image_url" in content and content["image_url"]:
            image_url = content["image_url"]
            logger.debug(f"Using image_url for product: {product_data.get('asin', 'unknown')}: {image_url}")
        elif "images" in content:
            images = content.get("images", [])
            if isinstance(images, list) and images:
                if isinstance(images[0], dict) and "url" in images[0]:
                    image_url = images[0]["url"]
                else:
                    image_url = images[0]
            elif isinstance(images, dict) and "main" in images:
                image_url = images["main"]
            logger.debug(f"Using images data for product: {product_data.get('asin', 'unknown')}: {image_url}")
                
        product_data["image_url"] = image_url
        
        # Original price for discounted items
        if "price_strikethrough" in content and content["price_strikethrough"]:
            try:
                product_data["original_price"] = float(content["price_strikethrough"])
            except (ValueError, TypeError):
                if isinstance(content["price_strikethrough"], str):
                    # Try to extract numeric price from string
                    try:
                        cleaned_price = re.sub(r'[^\d.]', '', content["price_strikethrough"])
                        if cleaned_price:
                            product_data["original_price"] = float(cleaned_price)
                    except (ValueError, TypeError):
                        pass
        
        # Check for sponsorship/advertisement
        product_data["is_sponsored"] = content.get("is_sponsored", False)
        
        # Extract seller information if available
        seller = content.get("seller", "")
        if seller:
            product_data["seller"] = seller
            
        # Extract availability and stock information
        availability_data = content.get("availability", content.get("stock", {}))
        if availability_data:
            if isinstance(availability_data, dict):
                product_data["in_stock"] = availability_data.get("in_stock", None)
                product_data["stock_level"] = availability_data.get("stock_level", None)
                product_data["availability_status"] = availability_data.get("status", None)
            elif isinstance(availability_data, bool):
                product_data["in_stock"] = availability_data
            elif isinstance(availability_data, str):
                product_data["availability_status"] = availability_data
                product_data["in_stock"] = "in stock" in availability_data.lower()
        
        # Extract shipping information
        shipping_data = content.get("shipping", {})
        if shipping_data:
            if isinstance(shipping_data, dict):
                product_data["free_shipping"] = shipping_data.get("free", None)
                product_data["shipping_cost"] = shipping_data.get("cost", None)
                product_data["shipping_information"] = shipping_data.get("information", None)
            elif isinstance(shipping_data, str):
                product_data["shipping_information"] = shipping_data
                product_data["free_shipping"] = "free" in shipping_data.lower()
        
        # Extract additional product details
        product_data["brand"] = content.get("brand", None)
        # Map brand to manufacturer for consistency with expected field names
        product_data["manufacturer"] = content.get("brand", None)
        product_data["description"] = content.get("description", None)
        product_data["features"] = content.get("features", [])
        product_data["categories"] = content.get("categories", [])
        
        # Extract specifications from various possible locations
        specs = content.get("specifications", content.get("specs", content.get("attributes", {})))
        if specs:
            if isinstance(specs, dict):
                product_data["specifications"] = specs
            elif isinstance(specs, list):
                specs_dict = {}
                for spec in specs:
                    if isinstance(spec, dict) and "name" in spec and "value" in spec:
                        specs_dict[spec["name"]] = spec["value"]
                product_data["specifications"] = specs_dict
        
        # Extract variant information
        variants = content.get("variants", [])
        if variants:
            if isinstance(variants, list):
                product_data["has_variants"] = len(variants) > 0
                product_data["variant_count"] = len(variants)
                
                # Extract variant options (e.g., available colors, sizes)
                variant_options = {}
                for variant in variants:
                    if isinstance(variant, dict):
                        for k, v in variant.items():
                            if k not in ["asin", "url", "price"]:
                                if k not in variant_options:
                                    variant_options[k] = set()
                                variant_options[k].add(v)
                
                # Convert sets to lists for JSON serialization
                product_data["variant_options"] = {k: list(v) for k, v in variant_options.items()}
        
        # Extract bestseller information
        if "bestseller" in content:
            # Store original bestseller data
            product_data["bestseller"] = content["bestseller"]
            # Add best_seller (with underscore) for consistency with expected field names
            product_data["best_seller"] = content["bestseller"]
            # Extract bestseller rank if available
            if isinstance(content["bestseller"], dict):
                product_data["bestseller_rank"] = content["bestseller"].get("rank", None)
                product_data["bestseller_category"] = content["bestseller"].get("category", None)
        else:
            # If no bestseller information is available, set best_seller to False by default
            product_data["best_seller"] = False
        
        # Extract Amazon's Choice information
        if "amazons_choice" in content:
            # Store original amazons_choice data
            product_data["amazons_choice"] = content["amazons_choice"]
            # Add is_amazons_choice (with is_ prefix) for consistency with expected field names
            product_data["is_amazons_choice"] = content["amazons_choice"]
            # Extract Amazon's Choice category if available
            if isinstance(content["amazons_choice"], dict):
                product_data["amazons_choice_category"] = content["amazons_choice"].get("category", None)
        else:
            # If no Amazon's Choice information is available, set is_amazons_choice to False by default
            product_data["is_amazons_choice"] = False
        
        # Extract review highlights
        reviews = content.get("reviews", {})
        if reviews:
            if isinstance(reviews, dict):
                product_data["review_count"] = reviews.get("count", None)
                if "highlights" in reviews and isinstance(reviews["highlights"], list):
                    product_data["review_highlights"] = reviews["highlights"]
        
        # Extract seller information
        seller = content.get("seller", {})
        if seller:
            if isinstance(seller, dict):
                product_data["seller_name"] = seller.get("name", None)
                product_data["seller_id"] = seller.get("id", None)
                product_data["seller_rating"] = seller.get("rating", None)
            elif isinstance(seller, str):
                product_data["seller_name"] = seller
        
        # Extract Prime information
        if "prime" in content:
            product_data["prime"] = content["prime"]
            # Add is_prime (with is_ prefix) for consistency with expected field names
            product_data["is_prime"] = content["prime"]
        else:
            # If no prime information is available, set is_prime to False by default
            product_data["is_prime"] = False
        
        # Remove None values for a cleaner response
        return {k: v for k, v in product_data.items() if v is not None} 