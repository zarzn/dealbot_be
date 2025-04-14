"""Standardized base market service for Oxylabs integrations."""

import logging
from typing import Any, Dict, List, Optional, Union

from core.integrations.oxylabs.base import OxylabsBaseService, OxylabsResult
from core.integrations.oxylabs.utils import extract_price, detect_currency

logger = logging.getLogger(__name__)


class OxylabsMarketBaseService(OxylabsBaseService):
    """Standardized base service for all Oxylabs market-specific scraping services.
    
    This class provides a consistent interface for all marketplace implementations
    while allowing for marketplace-specific customizations.
    """

    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        """Initialize standardized market service.
        
        Args:
            username: Oxylabs username
            password: Oxylabs password
        """
        super().__init__(username, password)
        
        # Default source configurations - should be overridden by specific markets
        self.search_source = "universal"       # Primary source for search operations
        self.product_source = "universal"      # Primary source for product detail operations
        self.fallback_source = "universal"     # Fallback source if primary fails
        
        # Market name for consistent logging
        self.market_name = "generic"  # Should be overridden by specific markets
        
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
        **kwargs
    ) -> OxylabsResult:
        """Search for products on a marketplace.
        
        Args:
            query: Search query
            limit: Maximum number of results
            region: Region or country code (e.g., 'us', 'uk')
            sort_by: Sorting option (implementation-specific)
            min_price: Minimum price filter
            max_price: Maximum price filter
            parse: Whether to parse the results automatically
            cache_ttl: Cache time-to-live in seconds (None for no caching)
            **kwargs: Additional marketplace-specific parameters
            
        Returns:
            OxylabsResult object with search results
        """
        # This method should be implemented by specific market services
        raise NotImplementedError("This method must be implemented by a specific market service")
        
    async def get_product_details(
        self, 
        product_id: str,
        region: Optional[str] = None,
        parse: bool = True,
        cache_ttl: Optional[int] = None,
        **kwargs
    ) -> OxylabsResult:
        """Get details of a specific product on a marketplace.
        
        Args:
            product_id: Marketplace product ID
            region: Region or country code (e.g., 'us', 'uk')
            parse: Whether to parse the results automatically
            cache_ttl: Cache time-to-live in seconds (None for no caching)
            **kwargs: Additional marketplace-specific parameters
            
        Returns:
            OxylabsResult object with product details
        """
        # This method should be implemented by specific market services
        raise NotImplementedError("This method must be implemented by a specific market service")
        
    def extract_product_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract useful product data from Oxylabs response.
        
        Args:
            raw_data: Raw data from Oxylabs response
            
        Returns:
            Dictionary with extracted product information
        """
        # This method should be implemented by specific market services
        raise NotImplementedError("This method must be implemented by a specific market service")
        
    def _prepare_search_params(
        self,
        query: str,
        limit: int,
        parse: bool,
        region: Optional[str] = None,
        sort_by: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Prepare standardized search parameters.
        
        This helper method creates a consistent parameter structure for search operations.
        Specific market implementations can override or extend this as needed.
        
        Args:
            query: Search query
            limit: Maximum number of results
            parse: Whether to parse the results
            region: Region or country code
            sort_by: Sorting option
            min_price: Minimum price filter
            max_price: Maximum price filter
            **kwargs: Additional parameters
            
        Returns:
            Dictionary of parameters for the API request
        """
        # Build base parameters
        params = {
            "source": self.search_source,
            "parse": parse,
            "limit": limit,
            "query": query
        }
        
        # Add price filters if provided
        if min_price is not None:
            params.setdefault("context", []).append({
                "key": "min_price", 
                "value": min_price
            })
            
        if max_price is not None:
            params.setdefault("context", []).append({
                "key": "max_price", 
                "value": max_price
            })
            
        # Add sort option if provided
        if sort_by is not None:
            params.setdefault("context", []).append({
                "key": "sort_by", 
                "value": sort_by
            })
            
        # Add region/location if provided
        if region is not None:
            # Default to geo_location - market-specific implementations can override
            params["geo_location"] = region
            
        return params
        
    def _prepare_product_params(
        self,
        product_id: str,
        parse: bool,
        region: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Prepare standardized product detail parameters.
        
        This helper method creates a consistent parameter structure for product detail operations.
        Specific market implementations can override or extend this as needed.
        
        Args:
            product_id: Product identifier
            parse: Whether to parse the results
            region: Region or country code
            **kwargs: Additional parameters
            
        Returns:
            Dictionary of parameters for the API request
        """
        # Build base parameters
        params = {
            "source": self.product_source,
            "parse": parse
        }
        
        # Add region/location if provided
        if region is not None:
            # Default to geo_location - market-specific implementations can override
            params["geo_location"] = region
            
        return params
        
    async def _execute_with_fallback(
        self, 
        params: Dict[str, Any],
        cache_ttl: Optional[int] = None,
        operation_name: str = "operation"
    ) -> OxylabsResult:
        """Execute a request with fallback support.
        
        This helper method provides standardized error handling and fallback logic.
        
        Args:
            params: Request parameters
            cache_ttl: Cache time-to-live
            operation_name: Name of operation for logging
            
        Returns:
            OxylabsResult from the API request
        """
        try:
            # Try with primary source
            current_source = params.get('source')
            logger.debug(f"{self.market_name} {operation_name} - Using source: {current_source}")
            
            result = await self.scrape_url(params, cache_ttl=cache_ttl)
            
            # Add the source to the result object for easier source tracking
            if not hasattr(result, 'source') or result.source is None:
                result.source = current_source
                logger.debug(f"Added source attribute: {current_source} to result")
            
            # Check for success with actual data
            has_data = False
            if result.success and isinstance(result.results, list):
                has_data = len(result.results) > 0
                
            # If failed or no data and we have a fallback, try it
            if (not result.success or not has_data) and self.fallback_source and self.fallback_source != current_source:
                logger.warning(
                    f"{self.market_name} {operation_name} - Primary source failed or returned no data, "
                    f"trying fallback source: {self.fallback_source}"
                )
                
                # Make a copy of params to avoid modifying the original
                fallback_params = params.copy()
                fallback_params["source"] = self.fallback_source
                
                # Try the fallback source
                fallback_result = await self.scrape_url(fallback_params, cache_ttl=cache_ttl)
                
                # Add the fallback source to the result object
                if not hasattr(fallback_result, 'source') or fallback_result.source is None:
                    fallback_result.source = self.fallback_source
                    logger.debug(f"Added fallback source attribute: {self.fallback_source} to result")
                
                # Check if fallback was successful with data
                fallback_has_data = False
                if fallback_result.success and isinstance(fallback_result.results, list):
                    fallback_has_data = len(fallback_result.results) > 0
                
                # Use fallback if it's better than the primary
                if (fallback_result.success and not result.success) or (fallback_has_data and not has_data):
                    logger.info(f"{self.market_name} {operation_name} - Using fallback source results")
                    return fallback_result
                else:
                    logger.info(f"{self.market_name} {operation_name} - Fallback not better than primary, using primary")
                
            # Add warning if no data
            if result.success and not has_data:
                logger.warning(f"{self.market_name} {operation_name} - Successful request but no results found")
                if not result.errors:
                    result.errors = ["Success but no results found"]
                    
            return result
            
        except Exception as e:
            error_msg = f"Error in {self.market_name} {operation_name}: {str(e)}"
            logger.error(error_msg)
            
            # Try fallback on exception if available
            if self.fallback_source and params.get("source") != self.fallback_source:
                try:
                    logger.debug(f"{self.market_name} {operation_name} - Using fallback source after error: {self.fallback_source}")
                    # Make a copy of params to avoid modifying the original
                    fallback_params = params.copy()
                    fallback_params["source"] = self.fallback_source
                    
                    result = await self.scrape_url(fallback_params, cache_ttl=cache_ttl)
                    
                    # Add the fallback source to the result object
                    if not hasattr(result, 'source') or result.source is None:
                        result.source = self.fallback_source
                        logger.debug(f"Added fallback source attribute: {self.fallback_source} to result")
                        
                    return result
                except Exception as fallback_error:
                    logger.error(f"Error in {self.market_name} {operation_name} fallback: {str(fallback_error)}")
            
            # Return error result if all fails
            error_result = OxylabsResult(
                success=False,
                start_url=params.get("url", ""),
                results=[],
                raw_results={},
                status_code=500,
                errors=[error_msg]
            )
            
            # Add source to error result for consistency
            error_result.source = params.get("source", self.fallback_source)
            
            return error_result 