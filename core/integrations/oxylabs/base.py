"""Base functionality for Oxylabs web scraping service."""

import json
import logging
import time
import hashlib
import random
import asyncio
from typing import Any, Dict, List, Optional, Union
from datetime import datetime

import aiohttp
from pydantic import BaseModel, SecretStr

from core.config import settings
from core.models.enums import MarketType
try:
    from core.services.redis import get_redis_service, create_null_safe_redis_service
except ImportError:
    logging.getLogger(__name__).warning("Could not import Redis service, caching will be disabled")
    # Mock functions if Redis is not available
    async def get_redis_service():
        return None
    
    def create_null_safe_redis_service():
        return None

logger = logging.getLogger(__name__)


class OxylabsRequestException(Exception):
    """Exception raised when Oxylabs request fails."""
    pass


class OxylabsResult(BaseModel):
    """Structure for storing oxylabs scraping result."""
    success: bool
    start_url: str
    results: Optional[List[Dict[str, Any]]] = []
    raw_results: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = []  # Allow both list and dict types
    errors: Optional[List[Union[Dict[str, Any], str]]] = []  # Allow both dict and string error messages
    status_code: int = 200
    source: Optional[str] = None  # Added source field to track which source was used


class OxylabsBaseService:
    """Base service for Oxylabs scraping.
    
    This class provides common functionality for all Oxylabs scraping services,
    including authentication, request handling, caching, and rate limiting.
    """

    def __init__(self, username: str = None, password: str = None):
        """Initialize Oxylabs base service.
        
        Args:
            username: Oxylabs username
            password: Oxylabs password
        """
        # Get credentials from args or settings
        if username is None or not username:
            username = getattr(settings, 'OXYLABS_USERNAME', None)
            logger.info(f"Oxylabs username configured: {bool(username)}")
            
        if password is None or not password:
            # Handle SecretStr password
            raw_password = getattr(settings, 'OXYLABS_PASSWORD', None)
            if hasattr(raw_password, 'get_secret_value'):
                password = raw_password.get_secret_value()
            else:
                password = raw_password
            logger.info(f"Oxylabs password configured: {bool(password)}")
        
        # Store credentials - convert to strings to handle SecretStr objects
        self.username = str(username) if username else ""
        self.password = str(password) if password else ""
        
        # Check for valid credentials
        if not self.username or not self.password:
            logger.error("Oxylabs credentials not properly configured")
        
        # Base API URL
        self.base_url = getattr(settings, 'OXYLABS_BASE_URL', 'https://realtime.oxylabs.io')
        
        # Set default proxy type
        self.proxy_type = "datacenter"
        
        # Cache settings
        self._redis_client = None
        self._in_memory_cache = {}
        self._redis_service = None
        self._initialized_redis = False
        
        # Initialize Redis tracking variables to fix linter errors
        self._last_redis_init_attempt = 0
        self._last_redis_success_log = 0
        
        # Add recursion detection for caching
        self._cache_operation_in_progress = False
        self._recursion_detected = False
        
        # Default timeout - can be overridden by specific services for slower sources
        self.timeout = aiohttp.ClientTimeout(total=90)  # 90 seconds total timeout
        
        # Initialize and manage aiohttp session
        self._session = None
        self._session_lock = asyncio.Lock()
        
        # Rate limiting
        self._request_times = []
        self._market_failures = {}
        
        # Metrics
        self._metrics_batch = []
        self._metrics_batch_size = 10
        
        # Configure retry settings
        self.max_retries = 3
        self.retry_delay = 2  # seconds

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an HTTP session.
        
        Returns:
            An aiohttp client session
        """
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Close the HTTP session if it exists."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def _init_redis_client(self):
        """Initialize Redis client with error handling and rate limiting for initialization attempts."""
        # Avoid too frequent initialization attempts
        current_time = time.time()
        if current_time - self._last_redis_init_attempt < 60:  # Try at most once per minute
            return self._redis_client
            
        self._last_redis_init_attempt = current_time
        
        try:
            # Use null-safe redis service to prevent issues
            # This helps avoid recursion errors and handle connection problems gracefully
            if self._redis_client is None:  # Only initialize if not already set
                # Import directly only when needed, to avoid circular imports
                from core.services.redis import create_null_safe_redis_service
                
                self._redis_client = create_null_safe_redis_service()
                
                # Log success (but not too frequently)
                if current_time - self._last_redis_success_log > 3600:  # Log at most once per hour
                    logger.info("Successfully initiated null-safe Redis client for Oxylabs caching")
                    self._last_redis_success_log = current_time
                
            return self._redis_client
        except Exception as e:
            logger.warning(f"Failed to initialize Redis client for Oxylabs caching: {e}")
            logger.info("Using in-memory cache as fallback")
            self._redis_client = None
            return None

    async def _get_from_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """Get data from Redis cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached data or None if not found/expired
        """
        try:
            # Try to get data from Redis
            redis = await self._get_redis()
            if not redis:
                logger.debug("Redis client unavailable for cache retrieval")
                return None
                
            cached_data = await redis.get(key)
            
            if cached_data:
                logger.debug(f"Cache hit for key: {key[:20]}...")
                try:
                    # Parse JSON data
                    data = json.loads(cached_data)
                    
                    # Ensure source field is preserved (for market sources)
                    if isinstance(data, dict) and "source" not in data and hasattr(self, "search_source"):
                        # Add source information from the service that's retrieving it
                        data["source"] = getattr(self, "search_source", None)
                        
                    return data
                    
                except json.JSONDecodeError as e:
                    logger.warning(f"Error decoding cached JSON data: {e}")
                    return None
                
            logger.debug(f"Cache miss for key: {key[:20]}...")
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving data from cache: {e}")
            return None

    async def _store_in_cache(self, key: str, data: Union[Dict, OxylabsResult], ttl: int = 3600) -> None:
        """Store data in Redis cache.
        
        Args:
            key: Cache key
            data: Data to store (either a dict or OxylabsResult object)
            ttl: Time-to-live in seconds
        """
        try:
            # Get Redis client
            redis = await self._get_redis()
            if not redis:
                logger.warning("Redis client unavailable for caching")
                return
                
            # Check for circular references or recursion in progress
            if getattr(self, "_cache_operation_in_progress", False):
                logger.warning("Recursion detected in caching operation, skipping")
                return
                
            # Set recursion flag to prevent nested cache operations
            self._cache_operation_in_progress = True
                
            try:
                # Create a safe copy of the data to prevent recursion errors during serialization
                data_dict = None
                
                # If data is an OxylabsResult, convert to a safe dict
                if isinstance(data, OxylabsResult):
                    try:
                        # Use its dict method which is safe
                        result_dict = data.dict()
                        
                        # Specially handle raw_results to prevent recursion
                        if "raw_results" in result_dict:
                            if isinstance(result_dict["raw_results"], dict) and len(result_dict["raw_results"]) > 20:
                                # For large dictionaries, only keep a few key items
                                result_dict["raw_results"] = {
                                    k: v for k, v in list(result_dict["raw_results"].items())[:20]
                                }
                            elif isinstance(result_dict["raw_results"], list) and len(result_dict["raw_results"]) > 20:
                                # For large lists, truncate
                                result_dict["raw_results"] = result_dict["raw_results"][:20]
                        
                        # Then create a safe copy to ensure no nested objects cause issues
                        data_dict = self._create_safe_copy(result_dict)
                    except Exception as e:
                        logger.error(f"Failed to convert OxylabsResult to dict: {e}")
                        # Fallback: manually create dict with essential fields
                        data_dict = {
                            "success": data.success,
                            "start_url": data.start_url,
                            "results": self._create_safe_copy(data.results),
                            # Omit raw_results to avoid recursion issues
                            "errors": self._create_safe_copy(data.errors),
                            "status_code": data.status_code,
                            "source": getattr(data, "source", None)
                        }
                else:
                    # For dict data, create a safe copy
                    data_dict = self._create_safe_copy(data)
                
                # Validate we have data to cache
                if not data_dict:
                    logger.warning("No valid data to cache")
                    return
                    
                # Serialize to JSON
                try:
                    json_data = json.dumps(data_dict)
                except (TypeError, ValueError) as e:
                    logger.error(f"Failed to JSON serialize data for caching: {e}")
                    # Try a more aggressive approach to make it serializable
                    try:
                        # Convert the entire structure to strings
                        simplified_data = json.dumps(str(data_dict))
                        logger.warning("Stored simplified string representation of data in cache")
                        await redis.set(key, simplified_data, ex=ttl)
                        return
                    except Exception:
                        logger.error("Failed to serialize even with simplified approach")
                        return
                
                # Store in Redis with TTL
                await redis.set(key, json_data, ex=ttl)
                logger.debug(f"Stored data in cache with key: {key[:20]}...")
                
            finally:
                # Reset recursion flag when done
                self._cache_operation_in_progress = False
                
        except Exception as e:
            logger.error(f"Error storing data in cache: {e}")
            # Don't raise the exception - caching failures shouldn't break the main flow

    def _clean_in_memory_cache(self):
        """Clean up expired entries from in-memory cache."""
        current_time = time.time()
        keys_to_delete = [
            key for key, entry in self._in_memory_cache.items()
            if entry['expires'] <= current_time
        ]
        
        for key in keys_to_delete:
            del self._in_memory_cache[key]

    def _generate_cache_key(self, params: Dict[str, Any], operation: str = "scrape") -> str:
        """Generate a unique cache key based on request parameters.
        
        Args:
            params: Request parameters
            operation: Operation type (e.g., 'scrape', 'search')
            
        Returns:
            Cache key
        """
        # Create a stable, deterministic cache key based on params
        # Filter out non-deterministic keys like timestamps
        filtered_params = {k: v for k, v in sorted(params.items()) 
                          if k not in ["_timestamp", "timestamp", "cache_key"]}
        
        # Compute cache key prefix
        prefix = f"oxylabs:{self.__class__.__name__}:{operation}"
        
        # Generate param hash for the cache key
        param_str = json.dumps(filtered_params, sort_keys=True)
        param_hash = hashlib.md5(param_str.encode()).hexdigest()
        
        # Combine prefix and hash for final cache key
        cache_key = f"{prefix}:{param_hash}"
        
        return cache_key

    async def scrape_url(self, params: Dict[str, Any], cache_ttl: Optional[int] = None) -> OxylabsResult:
        """Scrape a URL using Oxylabs API.
        
        Args:
            params: Request parameters
            cache_ttl: Cache time-to-live in seconds (None for no caching)
            
        Returns:
            OxylabsResult object
        """
        # Generate a cache key from params
        cache_key = self._generate_cache_key(params)
        
        # Try to get from cache if TTL is provided
        if cache_ttl is not None:
            cached_data = await self._get_from_cache(cache_key)
            if cached_data:
                logger.debug(f"Cache hit for key: {cache_key[:20]}...")
                
                # Create new result with cached data, ensuring proper field types
                result = OxylabsResult(
                    success=cached_data.get("success", True),
                    start_url=cached_data.get("start_url", ""),
                    results=cached_data.get("results", []),
                    raw_results=cached_data.get("raw_results", {}),  # Use raw_results field from cache
                    errors=cached_data.get("errors", []),
                    source=cached_data.get("source")
                )
                return result
        
        # Prepare API endpoint
        url = f"{self.base_url}/v1/queries"
        
        # Record start time for metrics
        start_time = time.time()
        success = False
        status_code = None
        
        try:
            # Get or create an HTTP session
            session = await self._get_session()
            
            # Log the request details (at DEBUG level to reduce noise)
            logger.debug(f"Making request to Oxylabs API: {url}")
            if "source" in params:
                logger.debug(f"Oxylabs API request source: {params['source']}")
            if "domain" in params:
                logger.debug(f"Oxylabs API request domain: {params['domain']}")
            
            # Set authentication
            auth = aiohttp.BasicAuth(self.username, self.password)
            
            # Send the request
            async with session.post(url, json=params, auth=auth, timeout=self.timeout) as response:
                # Calculate response time
                response_time = time.time() - start_time
                
                # Get response data
                status_code = response.status
                try:
                    data = await response.json()
                except Exception:
                    data = await response.text()
                    logger.warning(f"Could not parse response as JSON, using text: {data[:200]}...")
                    # Return error result for non-JSON response
                    return OxylabsResult(
                        success=False,
                        start_url=params.get("url", ""),
                        results=[],
                        raw_results={},
                        errors=[f"Non-JSON response: {data[:200]}..."],
                        status_code=status_code,
                        source=params.get("source")
                    )
                
                # Log response info (DEBUG for success, INFO for errors)
                if status_code == 200:
                    logger.debug(f"Oxylabs API response status: {status_code} in {response_time:.2f}s")
                else:
                    logger.info(f"Oxylabs API response status: {status_code} in {response_time:.2f}s")
                
                # Handle error responses
                if status_code != 200:
                    error_msg = f"Oxylabs API error: {data}"
                    logger.error(error_msg)
                    logger.error(f"Failed request payload: {json.dumps(params)}")
                    return OxylabsResult(
                        success=False,
                        start_url=params.get("url", ""),
                        results=[],
                        raw_results={},
                        errors=[error_msg],
                        status_code=status_code,
                        source=params.get("source")
                    )
                
                # Process successful response
                results = []
                
                # Extract results based on response structure
                try:
                    if isinstance(data, dict):
                        # Handle universal scraper format (most common format)
                        if "results" in data and isinstance(data["results"], list):
                            for result in data["results"]:
                                if "content" in result:
                                    # Universal format often has a nested structure
                                    content = result.get("content", {})
                                    
                                    # Check if content has nested "results" (common in searches)
                                    if isinstance(content, dict) and "results" in content:
                                        if isinstance(content["results"], list):
                                            # For direct list of results
                                            results.extend(content["results"])
                                        elif isinstance(content["results"], dict):
                                            # For search results with categories (paid/organic)
                                            for category, items in content["results"].items():
                                                if isinstance(items, list):
                                                    results.extend(items)
                                    else:
                                        # For product details, the content itself might be the result
                                        if content:  # Only add if not empty
                                            results.append(content)
                        # Simplified format where content is directly in the response
                        elif "content" in data:
                            if isinstance(data["content"], dict):
                                results = [data["content"]]
                            elif isinstance(data["content"], list):
                                results = data["content"]
                        else:
                            # Fallback: treat the entire response as the result
                            results = [data]
                    elif isinstance(data, list):
                        # For list responses, use directly
                        results = data
                    
                    # Ensure we have results
                    if not results:
                        logger.warning("No results extracted from Oxylabs response")
                        if isinstance(data, dict):
                            # Log top-level keys for debugging
                            logger.debug(f"Response data keys: {list(data.keys())}")
                    
                    # Mark success
                    success = True
                    
                    # Create result object
                    result = OxylabsResult(
                        success=True,
                        start_url=params.get("url", ""),
                        results=results,
                        raw_results=data,  # Store the complete original response
                        errors=[],
                        status_code=status_code,
                        source=params.get("source")
                    )
                    
                    # Cache the results if TTL is provided
                    if cache_ttl is not None and cache_ttl > 0:
                        await self._store_in_cache(cache_key, result, cache_ttl)
                    
                    return result
                    
                except Exception as e:
                    # Handle extraction errors
                    error_msg = f"Error processing Oxylabs response: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    return OxylabsResult(
                        success=False,
                        start_url=params.get("url", ""),
                        results=[],
                        raw_results=data,  # Still store the raw data for debugging
                        errors=[error_msg],
                        status_code=status_code,
                        source=params.get("source")
                    )
                
        except asyncio.TimeoutError:
            elapsed = time.time() - start_time
            error_msg = f"Oxylabs API request timed out after {elapsed:.2f}s"
            logger.error(error_msg)
            return OxylabsResult(
                success=False,
                start_url=params.get("url", ""),
                results=[],
                raw_results={},
                errors=[error_msg],
                status_code=status_code,
                source=params.get("source")
            )
            
        except Exception as e:
            elapsed = time.time() - start_time
            error_msg = f"Error making Oxylabs API request: {str(e)}"
            logger.error(error_msg)
            return OxylabsResult(
                success=False,
                start_url=params.get("url", ""),
                results=[],
                raw_results={},
                errors=[error_msg],
                status_code=status_code,
                source=params.get("source")
            )
            
        finally:
            # Record metrics if implemented in subclasses
            try:
                if hasattr(self, '_record_metrics'):
                    await self._record_metrics(
                        market_type=params.get("source", "unknown"),
                        success=success,
                        response_time=time.time() - start_time,
                        error=None if success else "API Error"
                    )
            except Exception as e:
                logger.debug(f"Error recording metrics: {str(e)}")

    async def _make_request_with_retry(
        self, endpoint: str, payload: Dict[str, Any], retries: int = None
    ) -> OxylabsResult:
        """Make a request to Oxylabs API with retry logic.
        
        Args:
            endpoint: API endpoint
            payload: Request payload
            retries: Number of retries (defaults to self.max_retries)
            
        Returns:
            OxylabsResult with the response data
        """
        if retries is None:
            retries = self.max_retries
            
        last_error = None
        status_code = None
        
        for attempt in range(retries + 1):
            try:
                result = await self._make_request(endpoint, payload)
                
                # If successful, return immediately
                if result.success:
                    return result
                    
                # If not successful but not a server error, don't retry
                if result.status_code and result.status_code < 500:
                    return result
                    
                # It's a server error, so we'll retry
                last_error = result.errors[0] if result.errors else "Unknown server error"
                if result.status_code:
                    status_code = result.status_code
                    
            except Exception as e:
                logger.error(f"Exception during Oxylabs API request (attempt {attempt+1}/{retries+1}): {e}")
                last_error = str(e)
            
            # If we're out of retries, break
            if attempt >= retries:
                break
                
            # Exponential backoff for retries
            wait_time = self.retry_delay * (2 ** attempt)
            logger.info(f"Retrying Oxylabs request in {wait_time}s (attempt {attempt+1}/{retries})")
            await asyncio.sleep(wait_time)
            
        # If we get here, all retries failed
        return OxylabsResult(
            success=False,
            start_url=payload.get("url", "") or f"{payload.get('domain', '')}/{payload.get('query', '')}",
            results=[],
            raw_results={},
            errors=[f"All retry attempts failed: {last_error}"],
            status_code=status_code,
            source=payload.get("source")
        )

    async def _make_request(
        self, endpoint: str, payload: Dict[str, Any]
    ) -> OxylabsResult:
        """Make a request to Oxylabs API.
        
        Args:
            endpoint: API endpoint
            payload: Request payload
            
        Returns:
            OxylabsResult with the response data
            
        Raises:
            OxylabsRequestException: If the request fails
        """
        session = await self._get_session()
        url = f"{self.base_url}{endpoint}"
        
        # Use Basic Auth with Oxylabs credentials
        auth = aiohttp.BasicAuth(self.username, self.password)
        
        try:
            logger.info(f"Making request to Oxylabs API: {url}")
            logger.debug(f"Payload: {json.dumps(payload)}")
            
            # Log specific details that are common sources of errors
            if "source" in payload:
                logger.info(f"Oxylabs API request source: {payload['source']}")
            if "domain" in payload:
                logger.info(f"Oxylabs API request domain: {payload['domain']}")
            if "query" in payload:
                logger.info(f"Oxylabs API request query: {payload['query']}")
            
            start_time = time.time()
            
            async with session.post(url, json=payload, auth=auth) as response:
                status_code = response.status
                response_text = await response.text()
                
                # Calculate response time for metrics
                response_time = time.time() - start_time
                
                logger.info(f"Oxylabs API response status: {status_code} in {response_time:.2f}s")
                
                # Handle empty response (204 No Content)
                if status_code == 204:
                    logger.error(f"Oxylabs API error: No content returned")
                    return OxylabsResult(
                        success=False,
                        start_url=payload.get("url", "") or f"{payload.get('domain', '')}/{payload.get('query', '')}",
                        results=[],
                        raw_results={},
                        errors=["No content returned (HTTP 204)"],
                        status_code=status_code,
                        source=payload.get("source")
                    )
                
                # Handle other non-200 responses
                if status_code != 200:
                    logger.error(f"Oxylabs API error: {response_text}")
                    # Log the full payload for debugging purposes on error
                    logger.error(f"Failed request payload: {json.dumps(payload, default=str)}")
                    
                    # Try to parse the error message from JSON if possible
                    error_detail = response_text
                    try:
                        error_json = json.loads(response_text)
                        if "message" in error_json:
                            error_detail = error_json["message"]
                    except json.JSONDecodeError:
                        pass
                        
                    return OxylabsResult(
                        success=False,
                        start_url=payload.get("url", "") or f"{payload.get('domain', '')}/{payload.get('query', '')}",
                        results=[],
                        raw_results={},
                        errors=[f"HTTP error {status_code}: {error_detail}"],
                        status_code=status_code,
                        source=payload.get("source")
                    )
                
                try:
                    # Parse JSON response
                    response_data = json.loads(response_text)
                    results = response_data.get("results", [])
                    
                    if not results:
                        logger.warning("Oxylabs API returned empty results")
                        return OxylabsResult(
                            success=False,
                            start_url=payload.get("url", "") or f"{payload.get('domain', '')}/{payload.get('query', '')}",
                            results=[],
                            raw_results=response_data,
                            errors=["No results found"],
                            status_code=status_code,
                            source=payload.get("source")
                        )
                    
                    # For parsed responses, extract content
                    extracted_results = []
                    for result in results:
                        # Get content from result
                        content = result.get("content", {})
                        
                        # Extract products if available (for search results)
                        if "results" in content:
                            products = []
                            # Get paid and organic results
                            if isinstance(content["results"], dict):
                                paid = content["results"].get("paid", [])
                                organic = content["results"].get("organic", [])
                                products.extend(paid)
                                products.extend(organic)
                            elif isinstance(content["results"], list):
                                products.extend(content["results"])
                            
                            extracted_results.extend(products)
                        else:
                            # For product details, the content itself is the result
                            extracted_results.append(content)
                    
                    # Record metrics for successful request
                    await self._record_metrics(
                        payload.get("source", "unknown"),
                        True, 
                        response_time
                    )
                    
                    return OxylabsResult(
                        success=True,
                        start_url=payload.get("url", "") or f"{payload.get('domain', '')}/{payload.get('query', '')}",
                        results=extracted_results,
                        raw_results=response_data,
                        status_code=status_code,
                        source=payload.get("source")
                    )
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse Oxylabs API response: {e}")
                    await self._record_metrics(
                        payload.get("source", "unknown"), 
                        False, 
                        response_time, 
                        str(e)
                    )
                    
                    return OxylabsResult(
                        success=False,
                        start_url=payload.get("url", "") or f"{payload.get('domain', '')}/{payload.get('query', '')}",
                        results=[],
                        raw_results={"raw_text": response_text},
                        errors=[f"Failed to parse API response: {e}"],
                        status_code=status_code,
                        source=payload.get("source")
                    )
        except Exception as e:
            logger.error(f"Exception during Oxylabs API request: {e}")
            await self._record_metrics(
                payload.get("source", "unknown"), 
                False, 
                None, 
                str(e)
            )
            
            return OxylabsResult(
                success=False,
                start_url=payload.get("url", "") or f"{payload.get('domain', '')}/{payload.get('query', '')}",
                results=[],
                raw_results={},
                errors=[f"Request exception: {str(e)}"],
                status_code=status_code,
                source=payload.get("source")
            )

    async def _record_metrics(
        self,
        market_type: str,
        success: bool = True,
        response_time: Optional[float] = None,
        error: Optional[str] = None
    ) -> None:
        """Record metrics about API requests.
        
        This is a placeholder that should be overridden by compatibility layer
        to use the actual metrics service.
        
        Args:
            market_type: Type of market (amazon, walmart, etc.)
            success: Whether the request was successful
            response_time: Response time in seconds
            error: Error message if any
        """
        # This can be implemented by users of this class if needed 

    def _create_safe_copy(self, obj):
        """Create a safe copy of an object that can be serialized to JSON without recursion errors.
        
        Args:
            obj: The object to copy
            
        Returns:
            A safe copy of the object
        """
        # Use a stack-based approach to avoid recursion depth issues
        if obj is None:
            return None
            
        # Handle primitive types directly to reduce processing
        if isinstance(obj, (str, int, float, bool, type(None))):
            return obj
            
        # Handle dictionary type
        if isinstance(obj, dict):
            # Create a new dict with safe copies of values
            result = {}
            # Skip these keys that could cause circular references or hold non-serializable data
            skip_keys = [
                "_client", "_service", "_session", "client", "service", "session",
                "connection", "connector", "_connector", "app", "_app", "request",
                "__pydantic_self__", "raw_results"  # Add raw_results to skip_keys to avoid recursion
            ]
            
            # Limit dictionary size to prevent deep nesting
            if len(obj) > 50:
                logger.warning(f"Large dictionary with {len(obj)} items found, truncating to 50 items")
                obj_items = list(obj.items())[:50]
            else:
                obj_items = obj.items()
                
            for key, value in obj_items:
                # Skip problematic keys
                if key in skip_keys:
                    continue
                    
                # Skip callable objects
                if callable(value):
                    continue
                
                # Skip extremely large string values
                if isinstance(value, str) and len(value) > 10000:
                    result[key] = f"<Large string: {len(value)} characters>"
                    continue
                
                # Skip deeply nested lists/dicts to prevent recursion
                if isinstance(value, (list, dict)) and id(value) == id(obj):
                    result[key] = "<Self-reference detected>"
                    continue
                    
                # Recursively create safe copies of values
                try:
                    safe_value = self._create_safe_copy(value)
                    if safe_value is not None:  # Skip None values to reduce output size
                        result[key] = safe_value
                except (RecursionError, TypeError, ValueError) as e:
                    # If error occurs, use a string representation instead
                    result[key] = f"<Complex object: {type(value).__name__}>"
                    logger.warning(f"Error creating safe copy of '{key}': {str(e)}")
                    
            return result
            
        # Handle list/tuple types
        elif isinstance(obj, (list, tuple)):
            # Create a new list with safe copies of values
            result = []
            
            # Limit list size to prevent deep nesting
            if len(obj) > 50:
                logger.warning(f"Large list/tuple with {len(obj)} items found, truncating to 50 items")
                obj_items = list(obj)[:50]
            else:
                obj_items = obj
                
            for item in obj_items:
                # Skip self-references
                if item is obj:
                    result.append("<Self-reference detected>")
                    continue
                    
                try:
                    safe_item = self._create_safe_copy(item)
                    if safe_item is not None:  # Skip None values
                        result.append(safe_item)
                except (RecursionError, TypeError, ValueError) as e:
                    # If error occurs, use a string representation instead
                    result.append(f"<Complex object: {type(item).__name__}>")
                    logger.warning(f"Error creating safe copy of list item: {str(e)}")
                    
            return result
            
        # Handle Pydantic models and objects with dict method
        elif hasattr(obj, "dict") and callable(getattr(obj, "dict")):
            try:
                # Convert to dict and create safe copy
                obj_dict = obj.dict()
                # Remove raw_results if present to avoid recursion
                if "raw_results" in obj_dict:
                    obj_dict["raw_results"] = "<Large data structure omitted>"
                return self._create_safe_copy(obj_dict)
            except Exception as e:
                logger.warning(f"Failed to convert object to dict: {e}")
                # Fall back to string representation
                return str(obj)
                
        # Handle objects with __dict__ (but no dict method)
        elif hasattr(obj, "__dict__"):
            try:
                # Filter out special attributes and methods
                attrs = {k: v for k, v in obj.__dict__.items() 
                        if not k.startswith('_') and not callable(v)}
                return self._create_safe_copy(attrs)
            except Exception as e:
                logger.warning(f"Failed to copy object attributes: {e}")
                return str(obj)
                
        # For other types, try to convert to string if possible
        try:
            return str(obj)
        except Exception:
            return f"<Object of type {type(obj).__name__}>"

    async def _get_redis(self):
        """Get a Redis client.
        
        Returns:
            Redis client or None if Redis is not available
        """
        try:
            # Import here to avoid circular imports
            from core.services.redis import get_redis_service
            
            # Get Redis service
            redis_service = await get_redis_service()
            return redis_service.client
            
        except Exception as e:
            logger.error(f"Failed to get Redis client: {e}")
            return None
        