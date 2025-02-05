from typing import Dict, Any, List, Optional
import aiohttp
import asyncio
from datetime import datetime
import hashlib
import time

from core.integrations.base import BaseMarketIntegration, IntegrationError
from core.models.market import MarketType
from core.exceptions import ValidationError
from core.utils.redis import get_redis_client


class WalmartIntegration(BaseMarketIntegration):
    REQUIRED_CREDENTIALS = ["client_id", "client_secret"]
    CACHE_TTL = 3600  # 1 hour
    BASE_URL = "https://api.walmart.com/v3"
    TOKEN_URL = "https://api.walmart.com/v3/token"

    def _validate_credentials(self) -> None:
        missing_fields = [field for field in self.REQUIRED_CREDENTIALS 
                         if field not in self.credentials]
        if missing_fields:
            raise ValidationError(
                f"Missing required Walmart API credentials: {', '.join(missing_fields)}"
            )

    def _initialize_client(self) -> None:
        self.client_id = self.credentials["client_id"]
        self.client_secret = self.credentials["client_secret"]
        self.session = aiohttp.ClientSession()

    async def _get_access_token(self) -> str:
        """Get or refresh Walmart API access token"""
        try:
            redis_client = await get_redis_client()
            cache_key = f"walmart:token:{self.client_id}"
            
            # Try to get cached token
            cached_token = await redis_client.get(cache_key)
            if cached_token:
                return cached_token

            # Generate new token
            timestamp = str(int(time.time() * 1000))
            signature = hashlib.sha256(
                f"{self.client_id}{timestamp}{self.client_secret}".encode()
            ).hexdigest()

            headers = {
                "WM_SVC.NAME": "Walmart Marketplace",
                "WM_QOS.CORRELATION_ID": timestamp,
                "WM_SEC.TIMESTAMP": timestamp,
                "WM_SEC.AUTH_SIGNATURE": signature,
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            }

            async with self.session.post(
                self.TOKEN_URL,
                headers=headers,
                data={
                    "grant_type": "client_credentials"
                }
            ) as response:
                if response.status != 200:
                    raise IntegrationError(f"Failed to get Walmart access token: {await response.text()}")
                
                data = await response.json()
                token = data["access_token"]
                expires_in = data["expires_in"]

                # Cache token
                await redis_client.set(cache_key, token, ex=expires_in - 60)  # Expire 1 minute before actual expiration
                
                return token

        except Exception as e:
            self._handle_error(e, "getting Walmart access token")

    async def search_products(
        self,
        query: str,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        try:
            # Try to get from cache first
            cache_key = f"walmart:search:{query}:{category}:{min_price}:{max_price}:{limit}"
            redis_client = await get_redis_client()
            cached_result = await redis_client.get(cache_key)
            if cached_result:
                return cached_result

            params = {
                "query": query,
                "limit": limit
            }
            if category:
                params["category"] = category

            token = await self._get_access_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json"
            }

            async with self.session.get(
                f"{self.BASE_URL}/items/search",
                headers=headers,
                params=params
            ) as response:
                if response.status != 200:
                    raise IntegrationError(f"Failed to search Walmart products: {await response.text()}")
                
                data = await response.json()
                items = data.get("items", [])

                formatted_products = []
                for item in items:
                    product = self._format_walmart_product(item)
                    
                    # Apply price filters if specified
                    price = float(product["price"]) if product.get("price") else None
                    if price:
                        if min_price and price < min_price:
                            continue
                        if max_price and price > max_price:
                            continue
                    
                    formatted_products.append(product)

                # Cache the results
                await redis_client.set(cache_key, formatted_products, ex=self.CACHE_TTL)
                
                return formatted_products[:limit]

        except Exception as e:
            self._handle_error(e, "searching Walmart products")

    async def get_product_details(self, product_id: str) -> Dict[str, Any]:
        try:
            # Try to get from cache first
            cache_key = f"walmart:product:{product_id}"
            redis_client = await get_redis_client()
            cached_result = await redis_client.get(cache_key)
            if cached_result:
                return cached_result

            token = await self._get_access_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json"
            }

            async with self.session.get(
                f"{self.BASE_URL}/items/{product_id}",
                headers=headers
            ) as response:
                if response.status != 200:
                    raise IntegrationError(f"Failed to get Walmart product details: {await response.text()}")
                
                item = await response.json()
                formatted_product = self._format_walmart_product(item)

                # Cache the result
                await redis_client.set(cache_key, formatted_product, ex=self.CACHE_TTL)
                
                return formatted_product

        except Exception as e:
            self._handle_error(e, "getting Walmart product details")

    async def get_product_price_history(self, product_id: str) -> List[Dict[str, Any]]:
        # Note: Walmart API doesn't provide price history
        # This would require a third-party service or our own price tracking
        raise NotImplementedError("Price history not available for Walmart products")

    async def check_product_availability(self, product_id: str) -> bool:
        try:
            product = await self.get_product_details(product_id)
            return product.get("availability", False)
        except Exception as e:
            self._handle_error(e, "checking Walmart product availability")

    def _format_walmart_product(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Format Walmart API product data into standardized format"""
        try:
            return self.format_product_response({
                "id": item.get("itemId"),
                "title": item.get("name"),
                "description": item.get("shortDescription"),
                "price": float(item.get("salePrice", item.get("price", {}).get("amount"))),
                "currency": "USD",
                "url": item.get("productUrl"),
                "image_url": item.get("imageUrl") or item.get("images", [{}])[0].get("url"),
                "brand": item.get("brand"),
                "category": item.get("categoryPath"),
                "availability": item.get("availabilityStatus") == "IN_STOCK",
                "rating": float(item.get("customerRating", 0)),
                "review_count": int(item.get("numReviews", 0)),
                "marketplace": "walmart",
                "seller": item.get("sellerName", "Walmart"),
                "metadata": {
                    "free_shipping": item.get("freeShipping", False),
                    "two_day_shipping": item.get("twoDayShipping", False),
                    "pickup_available": item.get("pickupAvailable", False)
                }
            })
        except Exception as e:
            self._handle_error(e, "formatting Walmart product data")

    async def __del__(self):
        if hasattr(self, "session"):
            await self.session.close() 
