"""Enhanced Walmart market integration."""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import asyncio
import hmac
import hashlib
import base64
import json
from urllib.parse import quote
import aiohttp
from dataclasses import dataclass
from redis.asyncio import Redis

from core.integrations.base import MarketBase, MarketCredentials
from core.exceptions import (
    MarketIntegrationError,
    ProductNotFoundError,
    RateLimitError
)
from core.utils.logger import get_logger
from core.utils.metrics import MetricsCollector
from core.utils.redis import get_redis_client

logger = get_logger(__name__)

@dataclass
class WalmartCredentials(MarketCredentials):
    """Walmart API credentials."""
    client_id: str
    client_secret: str
    region: str = 'US'

class WalmartIntegration(MarketBase):
    """Enhanced Walmart market integration."""
    
    def __init__(
        self,
        credentials: WalmartCredentials,
        redis_client: Optional[Redis] = None,
        session: Optional[aiohttp.ClientSession] = None,
        websocket_enabled: bool = True
    ):
        super().__init__(credentials, session)
        self.region = credentials.region
        self.redis_client = redis_client
        self.websocket_enabled = websocket_enabled
        self._ws_connections: Dict[str, aiohttp.ClientWebSocketResponse] = {}
        self._ws_callbacks: Dict[str, List[callable]] = {}
        self._base_url = "https://api.walmart.com/v3"
        
    async def _get_redis(self) -> Redis:
        """Get Redis client instance."""
        if not self.redis_client:
            self.redis_client = await get_redis_client()
        return self.redis_client

    async def search_products(
        self,
        query: str,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        sort_by: Optional[str] = None,
        limit: int = 25
    ) -> List[Dict[str, Any]]:
        """Search for products on Walmart."""
        try:
            # Generate search URL
            url = f"{self._base_url}/items/search"
            
            # Prepare parameters
            params = {
                'query': query,
                'limit': limit
            }
            
            if category:
                params['category'] = category
                
            if min_price:
                params['min_price'] = min_price
                
            if max_price:
                params['max_price'] = max_price
                
            if sort_by:
                params['sort'] = sort_by
                
            # Get authentication headers
            headers = await self._get_auth_headers('GET', url)
            
            # Make request
            response = await self._make_request(
                'GET',
                url,
                headers=headers,
                params=params
            )
            
            # Process results
            items = response.get('items', [])
            processed_items = []
            
            for item in items[:limit]:
                processed_item = await self._process_product(item)
                if processed_item:
                    processed_items.append(processed_item)
                    
            return processed_items
            
        except Exception as e:
            logger.error(f"Error searching Walmart products: {str(e)}")
            raise MarketIntegrationError(f"Walmart search failed: {str(e)}")
            
    async def get_product_details(
        self,
        product_id: str
    ) -> Dict[str, Any]:
        """Get detailed product information."""
        try:
            # Check cache first
            cached_data = await self._get_redis().get(
                f"walmart:product:{product_id}"
            )
            if cached_data:
                return cached_data
                
            # Generate URL
            url = f"{self._base_url}/items/{product_id}"
            
            # Get authentication headers
            headers = await self._get_auth_headers('GET', url)
            
            # Make request
            response = await self._make_request(
                'GET',
                url,
                headers=headers
            )
            
            # Process product data
            if not response:
                raise ProductNotFoundError(f"Product {product_id} not found")
                
            product_data = await self._process_product(response)
            
            # Cache result
            await self._get_redis().set(
                f"walmart:product:{product_id}",
                product_data,
                ex=3600  # 1 hour
            )
            
            return product_data
            
        except Exception as e:
            logger.error(f"Error getting Walmart product details: {str(e)}")
            raise MarketIntegrationError(
                f"Failed to get product details: {str(e)}"
            )
            
    async def track_price(
        self,
        product_id: str,
        check_interval: int = 300
    ) -> Dict[str, Any]:
        """Start tracking product price."""
        try:
            # Get initial product data
            product_data = await self.get_product_details(product_id)
            
            # Store tracking configuration
            tracking_config = {
                'product_id': product_id,
                'initial_price': product_data['price'],
                'check_interval': check_interval,
                'last_check': datetime.utcnow().isoformat(),
                'status': 'active'
            }
            
            # Store in Redis
            await self._get_redis().set(
                f"walmart:price_track:{product_id}",
                tracking_config,
                ex=86400  # 24 hours
            )
            
            # Start WebSocket connection if enabled
            if self.websocket_enabled:
                await self.subscribe_to_changes(
                    product_id,
                    self._handle_price_update
                )
                
            return tracking_config
            
        except Exception as e:
            logger.error(f"Error starting price tracking: {str(e)}")
            raise MarketIntegrationError(
                f"Failed to start price tracking: {str(e)}"
            )
            
    async def get_price_history(
        self,
        product_id: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get product price history."""
        try:
            # Get from Redis
            history = await self._get_redis().lrange(
                f"walmart:price_history:{product_id}",
                0,
                -1
            )
            
            if not history:
                return []
                
            # Filter by date
            cutoff = datetime.utcnow() - timedelta(days=days)
            
            filtered_history = [
                point for point in history
                if datetime.fromisoformat(point['timestamp']) >= cutoff
            ]
            
            return sorted(
                filtered_history,
                key=lambda x: x['timestamp']
            )
            
        except Exception as e:
            logger.error(f"Error getting price history: {str(e)}")
            raise MarketIntegrationError(
                f"Failed to get price history: {str(e)}"
            )
            
    async def subscribe_to_changes(
        self,
        product_id: str,
        callback: callable
    ):
        """Subscribe to product changes via WebSocket."""
        try:
            if not self.websocket_enabled:
                logger.warning("WebSocket functionality is disabled")
                return
                
            if product_id not in self._ws_connections:
                # Create new WebSocket connection
                ws = await self._create_ws_connection(product_id)
                self._ws_connections[product_id] = ws
                self._ws_callbacks[product_id] = []
                
                # Start listening task
                asyncio.create_task(
                    self._listen_for_updates(product_id, ws)
                )
                
            # Add callback
            self._ws_callbacks[product_id].append(callback)
            
        except Exception as e:
            logger.error(f"Error subscribing to changes: {str(e)}")
            raise MarketIntegrationError(
                f"Failed to subscribe to changes: {str(e)}"
            )
            
    async def unsubscribe_from_changes(
        self,
        product_id: str
    ):
        """Unsubscribe from product changes."""
        try:
            if product_id in self._ws_connections:
                ws = self._ws_connections.pop(product_id)
                await ws.close()
                
            self._ws_callbacks.pop(product_id, None)
            
        except Exception as e:
            logger.error(f"Error unsubscribing from changes: {str(e)}")
            
    async def _get_auth_headers(
        self,
        method: str,
        url: str
    ) -> Dict[str, str]:
        """Generate authentication headers for Walmart API."""
        try:
            timestamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
            
            return {
                'WM_SEC.KEY_VERSION': '1',
                'WM_CONSUMER.ID': self.credentials.client_id,
                'WM_CONSUMER.INTIMESTAMP': timestamp,
                'Accept': 'application/json'
            }
            
        except Exception as e:
            logger.error(f"Error generating auth headers: {str(e)}")
            raise MarketIntegrationError(
                f"Failed to generate auth headers: {str(e)}"
            )
            
    async def _process_product(
        self,
        raw_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Process raw product data into standardized format."""
        try:
            if not raw_data:
                return None
                
            # Extract basic information
            product_data = {
                'id': raw_data.get('itemId'),
                'title': raw_data.get('name'),
                'price': float(raw_data.get('salePrice', raw_data.get('price', 0))),
                'currency': 'USD',
                'url': raw_data.get('productUrl'),
                'image_url': raw_data.get('largeImage'),
                'in_stock': raw_data.get('stock', 'NOT_AVAILABLE') == 'AVAILABLE',
                'rating': float(raw_data.get('customerRating', 0)),
                'review_count': int(raw_data.get('numReviews', 0)),
                'seller': raw_data.get('sellerInfo', {}).get('sellerName', 'Walmart'),
                'category': raw_data.get('categoryPath'),
                'features': raw_data.get('shortDescription', '').split('\n'),
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Validate required fields
            if not await self._validate_product_data(product_data):
                return None
                
            return product_data
            
        except Exception as e:
            logger.error(f"Error processing product data: {str(e)}")
            return None
            
    async def _create_ws_connection(
        self,
        product_id: str
    ) -> aiohttp.ClientWebSocketResponse:
        """Create WebSocket connection for real-time updates."""
        try:
            ws_url = f"wss://stream.walmart.com/v3/items/{product_id}"
            
            # Get authentication headers
            headers = await self._get_auth_headers('GET', ws_url)
            
            # Create WebSocket connection
            ws = await self._session.ws_connect(
                ws_url,
                headers=headers,
                heartbeat=30
            )
            
            return ws
            
        except Exception as e:
            logger.error(f"Error creating WebSocket connection: {str(e)}")
            raise MarketIntegrationError(
                f"Failed to create WebSocket connection: {str(e)}"
            )
            
    async def _listen_for_updates(
        self,
        product_id: str,
        ws: aiohttp.ClientWebSocketResponse
    ):
        """Listen for WebSocket updates."""
        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        
                        # Process update
                        if data.get('type') == 'price_update':
                            await self._handle_price_update(
                                product_id,
                                data
                            )
                            
                    except json.JSONDecodeError:
                        logger.error("Invalid WebSocket message format")
                        
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(
                        f"WebSocket error: {ws.exception()}"
                    )
                    break
                    
        except Exception as e:
            logger.error(f"Error in WebSocket listener: {str(e)}")
            
        finally:
            # Cleanup
            if not ws.closed:
                await ws.close()
                
    async def _handle_price_update(
        self,
        product_id: str,
        data: Dict[str, Any]
    ):
        """Handle price update from WebSocket."""
        try:
            # Record price change
            price_point = {
                'price': data['new_price'],
                'currency': data.get('currency', 'USD'),
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Store in Redis
            await self._get_redis().rpush(
                f"walmart:price_history:{product_id}",
                price_point
            )
            
            # Notify callbacks
            if product_id in self._ws_callbacks:
                for callback in self._ws_callbacks[product_id]:
                    try:
                        await callback(product_id, price_point)
                    except Exception as cb_error:
                        logger.error(
                            f"Error in price update callback: {str(cb_error)}"
                        )
                        
        except Exception as e:
            logger.error(f"Error handling price update: {str(e)}") 