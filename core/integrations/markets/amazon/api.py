"""Enhanced Amazon market integration."""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import asyncio
import hmac
import hashlib
import base64
import json
from urllib.parse import quote

from core.integrations.markets.base.market_base import MarketBase, MarketCredentials
from core.exceptions import MarketIntegrationError
from core.utils.logger import get_logger
from core.config import settings

logger = get_logger(__name__)

class AmazonCredentials(MarketCredentials):
    """Amazon API credentials."""
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        partner_tag: str,
        region: str = 'US'
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.partner_tag = partner_tag
        self.region = region
        self.access_token = None
        self.refresh_token = None

class AmazonIntegration(MarketBase):
    """Enhanced Amazon market integration with real-time capabilities."""
    
    BASE_URL = "https://webservices.amazon.com"
    REALTIME_URL = "wss://realtime.webservices.amazon.com"
    
    def __init__(
        self,
        credentials: AmazonCredentials,
        **kwargs
    ):
        super().__init__(credentials, **kwargs)
        self.partner_tag = credentials.partner_tag
        self.region = credentials.region
        self.websocket = None
        self.subscriptions = {}
        
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get Amazon authentication headers."""
        timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # Create signature
        string_to_sign = f"GET\n{self.BASE_URL}\n/\n"
        signature = base64.b64encode(
            hmac.new(
                self.credentials.api_secret.encode('utf-8'),
                string_to_sign.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode('utf-8')
        
        return {
            'X-Amz-Date': timestamp,
            'Authorization': f"AWS3-HTTPS AWSAccessKeyId={self.credentials.api_key}, Signature={signature}",
            'X-Amz-Security-Token': self.credentials.access_token
        }
        
    async def search_products(
        self,
        query: str,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        limit: int = 10
    ) -> Dict[str, Any]:
        """Search for products on Amazon."""
        try:
            params = {
                'Operation': 'SearchItems',
                'Keywords': query,
                'PartnerTag': self.partner_tag,
                'PartnerType': 'Associates',
                'Marketplace': f'www.amazon.{self.region.lower()}',
                'ItemCount': limit
            }
            
            if category:
                params['SearchIndex'] = category
                
            if min_price:
                params['MinPrice'] = str(int(min_price * 100))
                
            if max_price:
                params['MaxPrice'] = str(int(max_price * 100))
                
            response = await self._make_request(
                'GET',
                f"{self.BASE_URL}/paapi5/searchitems",
                params=params
            )
            
            # Process and validate results
            items = []
            for item in response.get('Items', []):
                if await self.validate_product(item):
                    items.append(self._process_product(item))
                    
            return {
                'items': items,
                'total_results': response.get('TotalResultCount', 0),
                'search_url': self._generate_search_url(query)
            }
            
        except Exception as e:
            logger.error(f"Amazon search error: {str(e)}")
            raise MarketIntegrationError(f"Amazon search failed: {str(e)}")
            
    async def get_product_details(
        self,
        product_id: str
    ) -> Dict[str, Any]:
        """Get detailed product information from Amazon."""
        try:
            params = {
                'Operation': 'GetItems',
                'ItemIds': [product_id],
                'PartnerTag': self.partner_tag,
                'PartnerType': 'Associates',
                'Resources': [
                    'ItemInfo.Title',
                    'Offers.Listings.Price',
                    'Offers.Listings.Availability',
                    'Images.Primary.Large',
                    'ItemInfo.Features',
                    'ItemInfo.ProductInfo'
                ]
            }
            
            response = await self._make_request(
                'GET',
                f"{self.BASE_URL}/paapi5/getitems",
                params=params
            )
            
            if not response.get('Items'):
                raise MarketIntegrationError(f"Product {product_id} not found")
                
            item = response['Items'][0]
            return self._process_product(item, include_details=True)
            
        except Exception as e:
            logger.error(f"Amazon product details error: {str(e)}")
            raise MarketIntegrationError(
                f"Failed to get Amazon product details: {str(e)}"
            )
            
    async def track_price(
        self,
        product_id: str
    ) -> Dict[str, Any]:
        """Track product price in real-time."""
        try:
            # Get current price
            details = await self.get_product_details(product_id)
            current_price = details['price']
            
            # Setup real-time tracking
            await self.subscribe_to_changes(
                product_id,
                self._handle_price_change
            )
            
            return {
                'product_id': product_id,
                'current_price': current_price,
                'tracking_started': datetime.utcnow().isoformat(),
                'status': 'tracking'
            }
            
        except Exception as e:
            logger.error(f"Amazon price tracking error: {str(e)}")
            raise MarketIntegrationError(
                f"Failed to setup price tracking: {str(e)}"
            )
            
    async def get_price_history(
        self,
        product_id: str,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get price history for a product."""
        try:
            params = {
                'Operation': 'GetPriceHistory',
                'ItemId': product_id,
                'PartnerTag': self.partner_tag,
                'StartDate': (
                    datetime.utcnow() - timedelta(days=days)
                ).strftime('%Y-%m-%d')
            }
            
            response = await self._make_request(
                'GET',
                f"{self.BASE_URL}/paapi5/getpricehistory",
                params=params
            )
            
            history = []
            for price_point in response.get('PriceHistory', []):
                history.append({
                    'price': float(price_point['Price']['Amount']),
                    'currency': price_point['Price']['Currency'],
                    'timestamp': price_point['Timestamp'],
                    'condition': price_point.get('Condition', 'New')
                })
                
            return history
            
        except Exception as e:
            logger.error(f"Amazon price history error: {str(e)}")
            raise MarketIntegrationError(
                f"Failed to get price history: {str(e)}"
            )
            
    async def subscribe_to_changes(
        self,
        product_id: str,
        callback: callable
    ):
        """Subscribe to real-time product changes."""
        try:
            if not self.websocket:
                await self._connect_websocket()
                
            # Register subscription
            self.subscriptions[product_id] = callback
            
            # Send subscription message
            subscription_message = {
                'action': 'subscribe',
                'productId': product_id
            }
            await self.websocket.send_json(subscription_message)
            
        except Exception as e:
            logger.error(f"Amazon subscription error: {str(e)}")
            raise MarketIntegrationError(
                f"Failed to subscribe to changes: {str(e)}"
            )
            
    async def unsubscribe_from_changes(
        self,
        product_id: str
    ):
        """Unsubscribe from real-time product changes."""
        try:
            if product_id in self.subscriptions:
                # Send unsubscribe message
                unsubscribe_message = {
                    'action': 'unsubscribe',
                    'productId': product_id
                }
                await self.websocket.send_json(unsubscribe_message)
                
                # Remove subscription
                del self.subscriptions[product_id]
                
        except Exception as e:
            logger.error(f"Amazon unsubscribe error: {str(e)}")
            raise MarketIntegrationError(
                f"Failed to unsubscribe from changes: {str(e)}"
            )
            
    async def _connect_websocket(self):
        """Establish WebSocket connection for real-time updates."""
        try:
            if self.websocket:
                return
                
            self.websocket = await self.session.ws_connect(
                self.REALTIME_URL,
                headers=self._get_auth_headers()
            )
            
            # Start background task to handle messages
            asyncio.create_task(self._handle_websocket_messages())
            
        except Exception as e:
            logger.error(f"WebSocket connection error: {str(e)}")
            raise MarketIntegrationError(
                f"Failed to establish WebSocket connection: {str(e)}"
            )
            
    async def _handle_websocket_messages(self):
        """Handle incoming WebSocket messages."""
        try:
            async for message in self.websocket:
                if message.type == 'text':
                    data = json.loads(message.data)
                    product_id = data.get('productId')
                    
                    if product_id in self.subscriptions:
                        callback = self.subscriptions[product_id]
                        await callback(data)
                        
        except Exception as e:
            logger.error(f"WebSocket message handling error: {str(e)}")
            # Try to reconnect
            await self._connect_websocket()
            
    async def _handle_price_change(self, data: Dict[str, Any]):
        """Handle price change notifications."""
        try:
            product_id = data['productId']
            new_price = data['price']
            
            logger.info(
                f"Price change detected for {product_id}: {new_price}"
            )
            
            # Implement your price change handling logic here
            # For example, notify subscribers, update database, etc.
            
        except Exception as e:
            logger.error(f"Price change handling error: {str(e)}")
            
    def _process_product(
        self,
        item: Dict[str, Any],
        include_details: bool = False
    ) -> Dict[str, Any]:
        """Process Amazon product data."""
        try:
            processed = {
                'id': item['ASIN'],
                'title': item['ItemInfo']['Title']['DisplayValue'],
                'price': float(
                    item['Offers']['Listings'][0]['Price']['Amount']
                ),
                'currency': item['Offers']['Listings'][0]['Price']['Currency'],
                'url': item['DetailPageURL'],
                'image_url': item['Images']['Primary']['Large']['URL'],
                'source': 'amazon',
                'timestamp': datetime.utcnow().isoformat()
            }
            
            if include_details:
                processed.update({
                    'features': item['ItemInfo'].get('Features', {}).get(
                        'DisplayValues',
                        []
                    ),
                    'availability': item['Offers']['Listings'][0]['Availability']['Message'],
                    'rating': item.get('CustomerReviews', {}).get('Rating', 0),
                    'review_count': item.get('CustomerReviews', {}).get('Count', 0),
                    'seller': item['Offers']['Listings'][0]['MerchantInfo']['Name']
                })
                
            return processed
            
        except Exception as e:
            logger.error(f"Product processing error: {str(e)}")
            raise MarketIntegrationError(f"Failed to process product: {str(e)}")
            
    def _generate_search_url(self, query: str) -> str:
        """Generate Amazon search URL."""
        encoded_query = quote(query)
        return f"https://www.amazon.{self.region.lower()}/s?k={encoded_query}&tag={self.partner_tag}" 