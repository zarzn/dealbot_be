"""Market integration factory."""

from typing import List, Dict, Any, Optional, Literal
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.exceptions.market_exceptions import MarketIntegrationError

settings = get_settings()

class MarketIntegrationFactory:
    """Factory for market integrations."""

    def __init__(
        self,
        redis_client=None,
        api_key: Optional[SecretStr] = None,
        db: Optional[AsyncSession] = None,
        scraper_type: Literal["scraper_api", "oxylabs"] = settings.SCRAPER_TYPE
    ):
        """Initialize the factory with optional settings.
        
        Args:
            redis_client: Redis client for caching
            api_key: API key for scraper service (if using ScraperAPI)
            db: Database session for tracking metrics
            scraper_type: Type of scraper to use ("scraper_api" or "oxylabs")
        """
        self.redis_client = redis_client
        self.api_key = api_key
        self.db = db
        self.scraper_type = scraper_type
        self._scraper_api_instance = None
        self._oxylabs_instance = None
        
    async def get_scraper_api_service(self) -> Any:
        """Get a ScraperAPIService instance with lazy import to avoid circular dependencies."""
        if self._scraper_api_instance:
            return self._scraper_api_instance
            
        # Import here to avoid circular dependency
        from core.integrations.scraper_api import ScraperAPIService
        
        self._scraper_api_instance = ScraperAPIService(
            api_key=self.api_key or settings.SCRAPER_API_KEY,
            redis_client=self.redis_client,
            db=self.db
        )
        return self._scraper_api_instance
        
    async def get_oxylabs_service(self) -> Any:
        """Get an OxylabsService instance with lazy import to avoid circular dependencies."""
        if self._oxylabs_instance:
            return self._oxylabs_instance
            
        # Import here to avoid circular dependency
        from core.integrations.oxylabs import get_oxylabs
        
        self._oxylabs_instance = await get_oxylabs(
            db=self.db
        )
        return self._oxylabs_instance
        
    async def get_scraper_service(self):
        """Get the appropriate scraper service based on the configured type."""
        if self.scraper_type == "oxylabs":
            return await self.get_oxylabs_service()
        else:
            return await self.get_scraper_api_service()

    async def search_products(
        self,
        market: str,
        query: str,
        page: int = 1,
        pages: int = 1,
        limit: int = 15,
        geo_location: Optional[str] = None,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for products in the specified market.
        
        Args:
            market: Market identifier (amazon, walmart, google_shopping, ebay)
            query: Search query string
            page: Result page number (default: 1)
            pages: Number of pages to retrieve (default: 1)
            limit: Maximum number of products to return (default: 15)
            geo_location: Geographic location for localized results (optional)
            category: Product category to filter results (optional)
            
        Returns:
            List of product dictionaries or dictionary with 'results' field containing product list
        """
        import logging
        logger = logging.getLogger(__name__)
        
        scraper = await self.get_scraper_service()
        
        if market.lower() == "amazon":
            if self.scraper_type == "oxylabs":
                region = "us"  # Default region
                
                # Extract region from geo_location if provided
                if geo_location:
                    geo_lower = geo_location.lower()
                    if geo_lower in ["us", "uk", "ca", "de", "fr", "it", "es", "jp"]:
                        region = geo_lower
                
                # Additional Amazon-specific parameters - removing 'parse' to avoid duplicate parameter
                kwargs = {
                    "region": region,
                    "limit": limit,
                    "page": page,
                    "pages": pages
                    # Don't set parse here, it's already set in the OxylabsClient.search_amazon method
                }
                
                # Note: For Amazon, category is not directly supported by the Oxylabs API
                # It should be used for post-scraping filtering only, not passed to the API
                # We'll still include it in the method signature but won't pass it to search_amazon
                
                try:
                    # Get the Amazon search results
                    success, products, errors = await scraper.search_amazon(query, **kwargs)
                    
                    if not success:
                        logger.warning(f"Amazon search failed: {errors}")
                        return []
                    
                    # Process the products to ensure they are serializable
                    processed_products = []
                    
                    # Handle potentially complex product structures
                    if isinstance(products, list):
                        for product in products:
                            if isinstance(product, dict):
                                # Only include serializable fields
                                processed_product = {}
                                
                                # Essential fields - include both image_url and url_image 
                                for key in ["asin", "title", "url", "image_url", "url_image", "price", "currency", "price_string",
                                           "sponsored", "manufacturer", "marketplace", 
                                           "product_id", "price_value", "availability", "original_price", "price_strikethrough",
                                           "best_seller", "is_amazons_choice"]:
                                    if key in product:
                                        processed_product[key] = product[key]
                                
                                # Create seller_info if it doesn't exist
                                if "seller_info" not in processed_product:
                                    processed_product["seller_info"] = {}
                                
                                # Move rating and reviews_count into seller_info
                                if "rating" in product:
                                    processed_product["seller_info"]["rating"] = product["rating"]
                                if "reviews_count" in product:
                                    processed_product["seller_info"]["reviews"] = product["reviews_count"]
                                
                                # If we have price_strikethrough but not original_price, use it
                                if "price_strikethrough" in product and product["price_strikethrough"] and not processed_product.get("original_price"):
                                    try:
                                        if isinstance(product["price_strikethrough"], (int, float)):
                                            processed_product["original_price"] = float(product["price_strikethrough"])
                                        elif isinstance(product["price_strikethrough"], str):
                                            # Try to extract numeric price from string
                                            import re
                                            cleaned_price = re.sub(r'[^\d.]', '', product["price_strikethrough"])
                                            if cleaned_price:
                                                processed_product["original_price"] = float(cleaned_price)
                                        logger.debug(f"Mapped price_strikethrough to original_price: {processed_product.get('original_price')}")
                                    except Exception as e:
                                        logger.warning(f"Failed to convert price_strikethrough to original_price: {e}")
                                
                                # Ensure we have an image_url field, prioritizing url_image if available
                                if "url_image" in product and product["url_image"] and not processed_product.get("image_url"):
                                    processed_product["image_url"] = product["url_image"]
                                    logger.debug(f"Mapped url_image to image_url: {product['url_image']}")
                                elif "image" in product and product["image"] and not processed_product.get("image_url"):
                                    processed_product["image_url"] = product["image"]
                                    logger.debug(f"Mapped image to image_url: {product['image']}")
                                elif "images" in product and isinstance(product["images"], list) and product["images"] and not processed_product.get("image_url"):
                                    # Extract first image from images array
                                    if isinstance(product["images"][0], dict) and "url" in product["images"][0]:
                                        processed_product["image_url"] = product["images"][0]["url"]
                                    elif isinstance(product["images"][0], str):
                                        processed_product["image_url"] = product["images"][0]
                                    logger.debug(f"Extracted image_url from images array: {processed_product.get('image_url')}")
                                
                                # Ensure we have an ID field
                                if "asin" in processed_product:
                                    processed_product["id"] = processed_product["asin"]
                                elif "product_id" in processed_product:
                                    processed_product["id"] = processed_product["product_id"]
                                    
                                # Add to processed list
                                processed_products.append(processed_product)
                    
                    logger.info(f"Amazon search returned {len(processed_products)} processed products")
                    
                    # Log image URL status for debugging
                    image_urls_found = sum(1 for p in processed_products if "image_url" in p and p["image_url"])
                    logger.info(f"Found image URLs for {image_urls_found} out of {len(processed_products)} products")
                    
                    # Return the processed products directly
                    return processed_products
                except Exception as e:
                    logger.error(f"Error processing Amazon search results: {str(e)}", exc_info=True)
                    return []
            else:
                return await scraper.search_amazon(query, limit=limit)
        elif market.lower() == "walmart":
            if self.scraper_type == "oxylabs":
                kwargs = {"max_results": limit}
                if geo_location:
                    kwargs["geo_location"] = geo_location
                # Note: Category is not used directly in the scraper API, only for post-processing
                result = await scraper.search_walmart(query, **kwargs)
                
                # Process the results to ensure consistent structure for the frontend
                if isinstance(result, dict) and "results" in result and isinstance(result["results"], list):
                    for product in result["results"]:
                        # Create seller_info object if needed
                        if "seller_info" not in product:
                            product["seller_info"] = {}
                        
                        # Move rating and reviews to seller_info
                        if "rating" in product:
                            product["seller_info"]["rating"] = product["rating"]
                        if "reviews_count" in product:
                            product["seller_info"]["reviews"] = product["reviews_count"]
                
                # Log the structure of the result for debugging
                if isinstance(result, dict):
                    logger.debug(f"Walmart search result keys: {list(result.keys())}")
                
                # Return the raw result to let the caller handle the structure
                return result
            else:
                return await scraper.search_walmart(query, limit=limit)
        elif market.lower() == "google_shopping":
            if self.scraper_type == "oxylabs":
                kwargs = {"max_results": limit}
                if geo_location:
                    kwargs["geo_location"] = geo_location
                # Note: Category is not used directly in the scraper API, only for post-processing
                result = await scraper.search_google_shopping(query, **kwargs)
                
                # Process the results to ensure consistent structure for the frontend
                if isinstance(result, dict) and "results" in result and isinstance(result["results"], list):
                    for product in result["results"]:
                        # Create seller_info object if needed
                        if "seller_info" not in product:
                            product["seller_info"] = {}
                        
                        # Move rating and reviews to seller_info
                        if "rating" in product:
                            product["seller_info"]["rating"] = product["rating"]
                        if "reviews_count" in product:
                            product["seller_info"]["reviews"] = product["reviews_count"]
                
                # Log the structure of the result for debugging
                if isinstance(result, dict):
                    logger.debug(f"Google Shopping search result keys: {list(result.keys())}")
                
                # Return the raw result to let the caller handle the structure
                return result
            else:
                return await scraper.search_google_shopping(query, limit=limit)
        elif market.lower() == "ebay":
            if self.scraper_type == "oxylabs":
                kwargs = {"max_results": limit}
                if geo_location:
                    kwargs["geo_location"] = geo_location
                # Note: Category is not used directly in the scraper API, only for post-processing
                result = await scraper.search_ebay(query, **kwargs)
                
                # Process the results to ensure consistent structure for the frontend
                if isinstance(result, dict) and "results" in result and isinstance(result["results"], list):
                    for product in result["results"]:
                        # Create seller_info object if needed
                        if "seller_info" not in product:
                            product["seller_info"] = {}
                        
                        # Move rating and reviews to seller_info
                        if "rating" in product:
                            product["seller_info"]["rating"] = product["rating"]
                        if "reviews_count" in product:
                            product["seller_info"]["reviews"] = product["reviews_count"]
                
                # Log the structure of the result for debugging
                if isinstance(result, dict):
                    logger.debug(f"Ebay search result keys: {list(result.keys())}")
                
                # Return the raw result to let the caller handle the structure
                return result
            else:
                # Use ScraperAPI as fallback
                scraper_api = await self.get_scraper_api_service()
                return await scraper_api.search_ebay(query, limit=limit)
        else:
            raise MarketIntegrationError(
                market=market,
                operation="search_products",
                reason=f"Unsupported market: {market}"
            )

    async def get_product_details(
        self,
        market: str,
        product_id: str,
        geo_location: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get detailed information for a specific product.
        
        Args:
            market: Market identifier (amazon, walmart, google_shopping, ebay)
            product_id: Product identifier (asin, item_id, etc.)
            geo_location: Geographic location for localized results (optional)
            
        Returns:
            Product details dictionary
        """
        scraper = await self.get_scraper_service()
        
        if market.lower() == "amazon":
            if self.scraper_type == "oxylabs" and geo_location:
                return await scraper.get_amazon_product(product_id, geo_location=geo_location)
            else:
                return await scraper.get_amazon_product(product_id)
        elif market.lower() == "walmart":
            if self.scraper_type == "oxylabs" and geo_location:
                return await scraper.get_walmart_product(product_id, geo_location=geo_location)
            else:
                return await scraper.get_walmart_product(product_id)
        elif market.lower() == "google_shopping":
            if self.scraper_type == "oxylabs" and geo_location:
                return await scraper.get_google_shopping_product(product_id, geo_location=geo_location)
            else:
                return await scraper.get_google_shopping_product(product_id)
        elif market.lower() == "ebay":
            if self.scraper_type == "oxylabs" and geo_location:
                return await scraper.get_ebay_product(product_id, geo_location=geo_location)
            else:
                if self.scraper_type == "oxylabs":
                    return await scraper.get_ebay_product(product_id)
                else:
                    # Use ScraperAPI as fallback
                    scraper_api = await self.get_scraper_api_service()
                    return await scraper_api.get_ebay_product(product_id)
        else:
            raise MarketIntegrationError(
                market=market,
                operation="get_product_details",
                reason=f"Unsupported market: {market}"
            )