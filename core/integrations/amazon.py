from typing import Dict, Any, List, Optional
import aiohttp
import asyncio
from datetime import datetime
from amazon_paapi import AmazonApi
from amazon_paapi.tools import get_asin

from core.integrations.base import BaseMarketIntegration, IntegrationError
from core.models.market import MarketType
from core.exceptions import ValidationError
from core.utils.redis import get_redis_client

class AmazonIntegration(BaseMarketIntegration):
    REQUIRED_CREDENTIALS = ["access_key", "secret_key", "partner_tag", "country"]
    CACHE_TTL = 3600  # 1 hour

    def _validate_credentials(self) -> None:
        missing_fields = [field for field in self.REQUIRED_CREDENTIALS 
                         if field not in self.credentials]
        if missing_fields:
            raise ValidationError(
                f"Missing required Amazon API credentials: {', '.join(missing_fields)}"
            )

    def _initialize_client(self) -> None:
        try:
            self.client = AmazonApi(
                self.credentials["access_key"],
                self.credentials["secret_key"],
                self.credentials["partner_tag"],
                self.credentials["country"]
            )
        except Exception as e:
            self._handle_error(e, "initializing Amazon client")

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
            cache_key = f"amazon:search:{query}:{category}:{min_price}:{max_price}:{limit}"
            redis_client = await get_redis_client()
            cached_result = await redis_client.get(cache_key)
            if cached_result:
                return cached_result

            # Use category as search index if provided, otherwise search all
            search_index = category.upper() if category else "All"
            
            products = await asyncio.to_thread(
                self.client.search_items,
                keywords=query,
                search_index=search_index,
                item_count=limit
            )

            formatted_products = []
            for item in products.items:
                product = self._format_amazon_product(item)
                
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
            self._handle_error(e, "searching Amazon products")

    async def get_product_details(self, product_id: str) -> Dict[str, Any]:
        try:
            # Try to get from cache first
            cache_key = f"amazon:product:{product_id}"
            redis_client = await get_redis_client()
            cached_result = await redis_client.get(cache_key)
            if cached_result:
                return cached_result

            product = await asyncio.to_thread(
                self.client.get_items,
                [product_id]
            )

            if not product.items:
                raise IntegrationError(f"Product {product_id} not found")

            formatted_product = self._format_amazon_product(product.items[0])
            
            # Cache the result
            await redis_client.set(cache_key, formatted_product, ex=self.CACHE_TTL)
            
            return formatted_product

        except Exception as e:
            self._handle_error(e, "getting Amazon product details")

    async def get_product_price_history(self, product_id: str) -> List[Dict[str, Any]]:
        # Note: Amazon PAAPI doesn't provide price history
        # This would require a third-party service or our own price tracking
        raise NotImplementedError("Price history not available for Amazon products")

    async def check_product_availability(self, product_id: str) -> bool:
        try:
            product = await self.get_product_details(product_id)
            return product.get("availability", False)
        except Exception as e:
            self._handle_error(e, "checking Amazon product availability")

    def _format_amazon_product(self, item: Any) -> Dict[str, Any]:
        """Format Amazon PAAPI product data into standardized format"""
        try:
            return self.format_product_response({
                "id": item.asin,
                "title": item.item_info.title.display_value,
                "description": getattr(item.item_info.features, "display_values", [None])[0],
                "price": float(item.offers.listings[0].price.amount) if item.offers.listings else None,
                "currency": item.offers.listings[0].price.currency if item.offers.listings else "USD",
                "url": item.detail_page_url,
                "image_url": item.images.primary.large.url if item.images else None,
                "brand": item.item_info.by_line_info.brand.display_value if hasattr(item.item_info, "by_line_info") else None,
                "category": item.item_info.classifications.binding.display_value if hasattr(item.item_info, "classifications") else None,
                "availability": bool(item.offers.listings[0].availability.message == "In Stock") if item.offers.listings else False,
                "rating": float(item.item_info.customer_reviews.star_rating) if hasattr(item.item_info, "customer_reviews") else None,
                "review_count": int(item.item_info.customer_reviews.count) if hasattr(item.item_info, "customer_reviews") else 0,
                "marketplace": "amazon",
                "seller": item.offers.listings[0].merchant_info.name if item.offers.listings else None,
                "metadata": {
                    "prime": item.offers.listings[0].program_eligibility.prime if item.offers.listings else False,
                    "fulfilled_by_amazon": item.offers.listings[0].program_eligibility.prime if item.offers.listings else False,
                }
            })
        except Exception as e:
            self._handle_error(e, "formatting Amazon product data") 
