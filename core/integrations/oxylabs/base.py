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
    """Model for Oxylabs scraping result."""
    success: bool
    start_url: str
    results: List[Dict[str, Any]]
    raw_results: Dict[str, Any]
    errors: List[str] = []
    status_code: Optional[int] = None


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

    async def _get_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get data from cache (Redis or in-memory fallback).
        
        Args:
            cache_key: Cache key to retrieve
            
        Returns:
            Cached data if found, None otherwise
        """
        # Check for recursion
        if self._cache_operation_in_progress:
            self._recursion_detected = True
            logger.warning("Recursion detected in cache operations, temporarily disabling Redis caching")
            return None

        # Try in-memory cache first for better performance and to avoid Redis issues
        if cache_key in self._in_memory_cache:
            entry = self._in_memory_cache[cache_key]
            # Check if entry is still valid
            if entry['expires'] > time.time():
                return entry['data']
            else:
                # Clean up expired entry
                del self._in_memory_cache[cache_key]
        
        # If recursion was detected previously, skip Redis cache operations
        if self._recursion_detected:
            return None
            
        # Mark cache operation in progress to detect recursion
        self._cache_operation_in_progress = True
        
        try:
            # Try Redis as a fallback if in-memory cache doesn't have the data
            try:
                # Only initialize Redis client if not already done
                if self._redis_client is None:
                    redis_client = await self._init_redis_client()
                else:
                    redis_client = self._redis_client
                
                if redis_client:
                    try:
                        # Use safe_get to prevent recursion issues
                        cached_data = await redis_client.safe_get(f"oxylabs:{cache_key}")
                        if cached_data:
                            try:
                                # Simple type check to avoid recursion issues
                                if isinstance(cached_data, (str, bytes)):
                                    data = json.loads(cached_data)
                                    # Store in memory cache for faster retrieval next time
                                    self._in_memory_cache[cache_key] = {
                                        'data': data,
                                        'expires': time.time() + 3600  # Default 1 hour TTL
                                    }
                                    return data
                            except json.JSONDecodeError:
                                logger.warning(f"Invalid JSON in Redis cache for key: {cache_key}")
                    except Exception as e:
                        # Log error but continue with fallback to avoid breaking the flow
                        logger.warning(f"Error retrieving from Redis cache: {e}")
            except Exception as e:
                logger.warning(f"Unexpected error in _get_from_cache: {e}")
            
            return None
        finally:
            # Reset cache operation flag
            self._cache_operation_in_progress = False

    async def _store_in_cache(self, cache_key: str, value: Dict[str, Any], ttl: int = 3600):
        """Store data in cache (Redis or in-memory fallback).
        
        Args:
            cache_key: Cache key for storing
            value: Data to store
            ttl: Time-to-live in seconds (default: 1 hour)
        """
        if not value:
            return
        
        # Check for recursion
        if self._cache_operation_in_progress:
            self._recursion_detected = True
            logger.warning("Recursion detected in cache operations, temporarily disabling Redis caching")
            return
            
        # Store in in-memory cache first - this is always reliable
        self._in_memory_cache[cache_key] = {
            'data': value,
            'expires': time.time() + ttl
        }
        
        # Clean up expired entries occasionally
        if len(self._in_memory_cache) > 100 and random.random() < 0.1:  # 10% chance when cache is large
            self._clean_in_memory_cache()
            
        # If recursion was detected previously, skip Redis cache operations
        if self._recursion_detected:
            return
            
        # Mark cache operation in progress to detect recursion
        self._cache_operation_in_progress = True
        
        try:
            # Also try to store in Redis if available
            try:
                # Only initialize Redis client if not already done
                if self._redis_client is None:
                    redis_client = await self._init_redis_client()
                else:
                    redis_client = self._redis_client
                
                if redis_client:
                    try:
                        # Convert to JSON string first to avoid complex serialization issues
                        json_data = json.dumps(value, default=str)
                        # Use safe_set to prevent recursion issues
                        await redis_client.safe_set(
                            f"oxylabs:{cache_key}",
                            json_data,
                            ex=ttl
                        )
                    except Exception as e:
                        # Log error but continue since we already have in-memory cache
                        logger.warning(f"Error storing in Redis cache: {e}")
            except Exception as e:
                logger.warning(f"Unexpected error in _store_in_cache: {e}")
        finally:
            # Reset cache operation flag
            self._cache_operation_in_progress = False

    def _clean_in_memory_cache(self):
        """Clean up expired entries from in-memory cache."""
        current_time = time.time()
        keys_to_delete = [
            key for key, entry in self._in_memory_cache.items()
            if entry['expires'] <= current_time
        ]
        
        for key in keys_to_delete:
            del self._in_memory_cache[key]

    def _generate_cache_key(self, params: Dict[str, Any]) -> str:
        """Generate a cache key from request parameters.
        
        Args:
            params: Request parameters
            
        Returns:
            Cache key string
        """
        # Create a simplified params copy to avoid serialization issues
        simplified_params = {}
        for k, v in params.items():
            # Skip complex objects that could cause recursion
            if isinstance(v, (str, int, float, bool)) or v is None:
                simplified_params[k] = v
            elif isinstance(v, list) and all(isinstance(x, (str, int, float, bool)) or x is None for x in v):
                simplified_params[k] = v
            else:
                # For complex objects, just use their type name
                simplified_params[k] = f"<{type(v).__name__}>"
                
        # Create a sorted, stable representation of the params
        param_str = json.dumps(simplified_params, sort_keys=True)
        
        # Create a hash to use as the cache key
        return hashlib.md5(param_str.encode('utf-8')).hexdigest()

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
                return OxylabsResult(
                    success=cached_data.get("success", True),
                    start_url=cached_data.get("start_url", ""),
                    results=cached_data.get("results", []),
                    raw_results=cached_data,
                    errors=cached_data.get("errors", [])
                )
        
        # Prepare API endpoint
        url = f"{self.base_url}/v1/queries"
        
        # Record start time for metrics
        start_time = time.time()
        success = False
        
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
                        status_code=status_code
                    )
                
                # Process successful response
                results = []
                
                # Extract results based on response structure
                if isinstance(data, dict):
                    if "results" in data:
                        for result in data["results"]:
                            if "content" in result:
                                if result["content"]:
                                    results.append(result["content"])
                            elif "result" in result:
                                if result["result"]:
                                    results.append(result["result"])
                    elif "content" in data:
                        results = [data["content"]]
                elif isinstance(data, list):
                    results = data
                
                # Mark success
                success = True
                
                # Cache the results if TTL is provided
                if cache_ttl is not None and cache_ttl > 0:
                    await self._store_in_cache(cache_key, data, cache_ttl)
                
                # Return structured result
                return OxylabsResult(
                    success=True,
                    start_url=params.get("url", ""),
                    results=results,
                    raw_results=data,
                    errors=[],
                    status_code=status_code
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
                errors=[error_msg]
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
                errors=[error_msg]
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
            errors=[f"All retry attempts failed: {last_error}"]
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
                        status_code=status_code
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
                        status_code=status_code
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
                            status_code=status_code
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
                        status_code=status_code
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
                        status_code=status_code
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
                errors=[f"Request exception: {str(e)}"]
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