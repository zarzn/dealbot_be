"""Enhanced Amazon market integration."""

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
class AmazonCredentials(MarketCredentials):
    """Amazon API credentials."""
    api_key: str
    api_secret: str
    partner_tag: str
    region: str = 'US'

class AmazonIntegration(MarketBase):
    """Enhanced Amazon market integration."""
    
    def __init__(
        self,
        credentials: AmazonCredentials,
        redis_client: Optional[Redis] = None,
        session: Optional[aiohttp.ClientSession] = None,
        websocket_enabled: bool = True
    ):
        super().__init__(credentials, session)
        self.partner_tag = credentials.partner_tag
        self.region = credentials.region
        self.redis_client = redis_client
        self.websocket_enabled = websocket_enabled
        self._ws_connections: Dict[str, aiohttp.ClientWebSocketResponse] = {}
        self._ws_callbacks: Dict[str, List[callable]] = {}
        self._base_url = f"https://webservices.amazon.{self.region.lower()}"

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
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for products on Amazon."""
        try:
            # Generate search URL
            url = await self._generate_search_url(
                query,
                category,
                min_price,
                max_price,
                sort_by
            )
            
            # Get authentication headers
            headers = await self._get_auth_headers('GET', url)
            
            # Make request
            response = await self._make_request(
                'GET',
                url,
                headers=headers
            )
            
            # Process results
            items = response.get('Items', [])
            processed_items = []
            
            for item in items[:limit]:
                processed_item = await self._process_product(item)
                if processed_item:
                    processed_items.append(processed_item)
                    
            return processed_items
            
        except Exception as e:
            logger.error(f"Error searching Amazon products: {str(e)}")
            raise MarketIntegrationError(f"Amazon search failed: {str(e)}")
            
    async def get_product_details(
        self,
        product_id: str
    ) -> Dict[str, Any]:
        """Get detailed product information."""
        try:
            # Check cache first
            cached_data = await self._get_redis().get(
                f"amazon:product:{product_id}"
            )
            if cached_data:
                return cached_data
                
            # Generate URL
            url = f"{self._base_url}/paapi5/getitems"
            
            # Get authentication headers
            headers = await self._get_auth_headers('GET', url)
            
            # Make request
            response = await self._make_request(
                'GET',
                url,
                headers=headers,
                params={'ItemIds': product_id}
            )
            
            # Process product data
            if not response.get('ItemsResult', {}).get('Items'):
                raise ProductNotFoundError(f"Product {product_id} not found")
                
            product_data = await self._process_product(
                response['ItemsResult']['Items'][0]
            )
            
            # Cache result
            await self._get_redis().set(
                f"amazon:product:{product_id}",
                product_data,
                ex=3600  # 1 hour
            )
            
            return product_data
            
        except Exception as e:
            logger.error(f"Error getting Amazon product details: {str(e)}")
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
                f"amazon:price_track:{product_id}",
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
                f"amazon:price_history:{product_id}",
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
        """Generate authentication headers for Amazon API."""
        try:
            timestamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
            
            # Create signature
            string_to_sign = f"{method}\n{url}\n{timestamp}"
            signature = base64.b64encode(
                hmac.new(
                    self.credentials.api_secret.encode('utf-8'),
                    string_to_sign.encode('utf-8'),
                    hashlib.sha256
                ).digest()
            ).decode('utf-8')
            
            return {
                'X-Amz-Date': timestamp,
                'Authorization': f"AWS4-HMAC-SHA256 Credential={self.credentials.api_key}",
                'X-Amz-Security-Token': signature
            }
            
        except Exception as e:
            logger.error(f"Error generating auth headers: {str(e)}")
            raise MarketIntegrationError(
                f"Failed to generate auth headers: {str(e)}"
            )
            
    async def _generate_search_url(
        self,
        query: str,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        sort_by: Optional[str] = None
    ) -> str:
        """Generate search URL with parameters."""
        try:
            base_url = f"{self._base_url}/paapi5/searchitems"
            
            params = {
                'Keywords': quote(query),
                'PartnerTag': self.partner_tag,
                'PartnerType': 'Associates'
            }
            
            if category:
                params['SearchIndex'] = category
                
            if min_price:
                params['MinPrice'] = str(int(min_price * 100))
                
            if max_price:
                params['MaxPrice'] = str(int(max_price * 100))
                
            if sort_by:
                params['SortBy'] = sort_by
                
            query_string = '&'.join(
                f"{k}={v}" for k, v in params.items()
            )
            
            return f"{base_url}?{query_string}"
            
        except Exception as e:
            logger.error(f"Error generating search URL: {str(e)}")
            raise MarketIntegrationError(
                f"Failed to generate search URL: {str(e)}"
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
                'id': raw_data.get('ASIN'),
                'title': raw_data.get('ItemInfo', {}).get('Title', {}).get('DisplayValue'),
                'price': float(raw_data.get('Offers', {}).get('Listings', [{}])[0].get('Price', {}).get('Amount', 0)),
                'currency': raw_data.get('Offers', {}).get('Listings', [{}])[0].get('Price', {}).get('Currency', 'USD'),
                'url': raw_data.get('DetailPageURL'),
                'image_url': raw_data.get('Images', {}).get('Primary', {}).get('Large', {}).get('URL'),
                'in_stock': raw_data.get('Offers', {}).get('Listings', [{}])[0].get('DeliveryInfo', {}).get('IsAmazonFulfilled', False),
                'rating': raw_data.get('CustomerReviews', {}).get('StarRating', {}).get('Value', 0),
                'review_count': raw_data.get('CustomerReviews', {}).get('Count', 0),
                'seller': raw_data.get('Offers', {}).get('Listings', [{}])[0].get('MerchantInfo', {}).get('Name', 'Amazon'),
                'category': raw_data.get('ItemInfo', {}).get('Classifications', {}).get('ProductGroup', {}).get('DisplayValue'),
                'features': raw_data.get('ItemInfo', {}).get('Features', {}).get('DisplayValues', []),
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
            ws_url = f"wss://realtime.amazon.{self.region.lower()}/products/{product_id}"
            
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
                f"amazon:price_history:{product_id}",
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