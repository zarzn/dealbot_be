from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import HTTPException, status
from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
import json
import hashlib

from ..repositories.market import MarketRepository
from ..models.market import MarketCreate, MarketUpdate, Market, MarketType, MarketStatus
from ..exceptions import (
    NotFoundException,
    ValidationError,
    MarketError,
    MarketNotFoundError,
    MarketValidationError,
    MarketConnectionError,
    MarketRateLimitError,
    MarketConfigurationError,
    MarketOperationError,
    APIError,
    APIAuthenticationError,
    APIServiceUnavailableError,
    DatabaseError,
    CacheOperationError,
    RepositoryError,
    NetworkError,
    DataProcessingError
)
from ..services.base import BaseService


class MarketService(BaseService[Market, MarketCreate, MarketUpdate]):
    """Service for managing markets."""
    
    model = Market

    def __init__(self, db: AsyncSession, redis_service: Optional[Redis] = None):
        """Initialize market service.
        
        Args:
            db: Database session
            redis_service: Optional Redis service for caching
        """
        super().__init__(session=db, redis_service=redis_service)
        self.market_repository = MarketRepository(db)

    async def create_market(self, **kwargs) -> Market:
        """Create a new market.
        
        Args:
            **kwargs: Market data including name, type, api_endpoint, etc.
            
        Returns:
            Market: The created market
            
        Raises:
            ValidationError: If a market with the same type already exists
        """
        try:
            # Check if market with same type already exists
            market_type = kwargs.get('type')
            if market_type:
                existing_market = await self.market_repository.get_by_type(market_type)
                if existing_market:
                    raise ValidationError(f"Market with type {market_type} already exists")

            # Validate API credentials if provided
            api_credentials = kwargs.get('api_credentials')
            if api_credentials and market_type:
                self._validate_api_credentials(market_type, api_credentials)
                
            # Filter out non-model parameters
            valid_model_params = {
                'id', 'name', 'type', 'description', 'api_endpoint', 'api_key', 'status',
                'config', 'rate_limit', 'is_active', 'error_count', 'requests_today',
                'total_requests', 'success_rate', 'avg_response_time', 'last_error',
                'last_error_at', 'last_successful_request', 'last_reset_at', 'created_at',
                'updated_at'
            }
            
            # Add non-model parameters to config if they exist
            config = kwargs.get('config', {}).copy() if kwargs.get('config') else {}
                
            # Store timeout, retry_count, retry_delay in config
            for param in ['timeout', 'retry_count', 'retry_delay']:
                if param in kwargs:
                    config.setdefault('connection', {})
                    config['connection'][param] = kwargs[param]
            
            # Update config in kwargs
            if config:
                kwargs['config'] = config
            
            # Filter kwargs to only include valid model parameters
            filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_model_params}

            # Create the market using filtered kwargs
            return await self.market_repository.create(filtered_kwargs)
        except Exception as e:
            raise ValidationError(f"Failed to create market: {str(e)}")

    async def get_market(self, market_id: UUID) -> Market:
        """Get a market by ID.
        
        Args:
            market_id: The UUID of the market to retrieve
            
        Returns:
            Market: The retrieved market
            
        Raises:
            MarketNotFoundError: If the market is not found
        """
        try:
            # Validate UUID format
            if not isinstance(market_id, UUID):
                try:
                    market_id = UUID(str(market_id))
                except (ValueError, TypeError):
                    raise MarketNotFoundError(f"Invalid market ID format: {market_id}")
            
            market = await self.market_repository.get_by_id(market_id)
            if not market:
                raise MarketNotFoundError(f"Market with id {market_id} not found")
            return market
        except MarketNotFoundError:
            raise
        except Exception as e:
            raise DatabaseError(
                operation="get_market",
                message=f"Failed to get market: {str(e)}"
            )

    async def get_market_by_type(self, market_type: MarketType) -> Market:
        market = await self.market_repository.get_by_type(market_type)
        if not market:
            raise NotFoundException(f"Market of type {market_type} not found")
        return market

    async def get_all_markets(self) -> List[Market]:
        return await self.market_repository.get_all()

    async def list_markets(self, **filters) -> List[Market]:
        """List all markets with optional filters.
        
        Args:
            **filters: Optional filters such as is_active, type, status
            
        Returns:
            List[Market]: List of markets matching the filters
        """
        # Ensure status is in the correct format
        if 'status' in filters and filters['status']:
            # Convert to lowercase for comparison
            filters['status'] = filters['status'].lower()
            
        # Ensure type is in the correct format
        if 'type' in filters and filters['type']:
            # Convert to lowercase for comparison
            filters['type'] = filters['type'].lower()
            
        return await self.market_repository.get_all_filtered(**filters)

    async def get_active_markets(self) -> List[Market]:
        return await self.market_repository.get_all_active()

    async def update_market(self, market_id: UUID, **kwargs) -> Market:
        """Update a market.
        
        Args:
            market_id: The ID of the market to update
            **kwargs: Market data to update including name, api_endpoint, status, etc.
            
        Returns:
            Market: The updated market
            
        Raises:
            MarketNotFoundError: If the market is not found
            ValidationError: If the update data is invalid
        """
        try:
            market = await self.get_market(market_id)

            # Validate API credentials if provided
            api_credentials = kwargs.get('api_credentials')
            if api_credentials and market.type:
                self._validate_api_credentials(market.type, api_credentials)

            # Filter out non-model parameters
            valid_model_params = {
                'id', 'name', 'type', 'description', 'api_endpoint', 'api_key', 'status',
                'config', 'rate_limit', 'is_active', 'error_count', 'requests_today',
                'total_requests', 'success_rate', 'avg_response_time', 'last_error',
                'last_error_at', 'last_successful_request', 'last_reset_at', 'created_at',
                'updated_at'
            }
            
            # Handle config updates - merge with existing config if present
            if 'config' in kwargs:
                config = market.config.copy() if market.config else {}
                if isinstance(kwargs['config'], dict):
                    # Update with new config values
                    config.update(kwargs['config'])
                    kwargs['config'] = config
            else:
                config = market.config.copy() if market.config else {}
                
            # Store timeout, retry_count, retry_delay in config
            connection_updated = False
            for param in ['timeout', 'retry_count', 'retry_delay']:
                if param in kwargs:
                    config.setdefault('connection', {})
                    config['connection'][param] = kwargs[param]
                    connection_updated = True
            
            # Update config in kwargs if connection parameters were updated
            if connection_updated:
                kwargs['config'] = config
            
            # Filter kwargs to only include valid model parameters
            filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_model_params}

            # Update the market
            return await self.market_repository.update(market_id, **filtered_kwargs)
        except MarketNotFoundError:
            raise
        except Exception as e:
            raise ValidationError(f"Failed to update market: {str(e)}")

    async def delete_market(self, market_id: UUID) -> bool:
        market = await self.get_market(market_id)
        return await self.market_repository.delete(market_id)

    def _validate_api_credentials(self, market_type: str, credentials: Dict[str, Any]) -> None:
        """Validate market-specific API credentials"""
        required_fields = {
            MarketType.AMAZON: ["access_key", "secret_key", "partner_tag"],
            MarketType.WALMART: ["client_id", "client_secret"],
            MarketType.EBAY: ["app_id", "cert_id", "dev_id"]
        }

        if market_type not in required_fields:
            raise ValidationError(f"Unsupported market type: {market_type}")

        missing_fields = [field for field in required_fields[market_type] 
                         if field not in credentials]
        
        if missing_fields:
            raise ValidationError(
                f"Missing required API credentials for {market_type}: {', '.join(missing_fields)}"
            )

    async def get_categories(self, market_id: UUID) -> List[dict]:
        """Get categories for a specific market"""
        market = await self.get_market(market_id)
        
        # Default categories for supported markets
        default_categories = {
            MarketType.AMAZON: [
                {"id": "electronics", "name": "Electronics", "parent_id": None},
                {"id": "computers", "name": "Computers", "parent_id": "electronics"},
                {"id": "phones", "name": "Phones & Accessories", "parent_id": "electronics"},
                {"id": "home", "name": "Home & Kitchen", "parent_id": None},
                {"id": "appliances", "name": "Appliances", "parent_id": "home"}
            ],
            MarketType.WALMART: [
                {"id": "electronics", "name": "Electronics", "parent_id": None},
                {"id": "home", "name": "Home", "parent_id": None},
                {"id": "grocery", "name": "Grocery", "parent_id": None}
            ]
        }
        
        try:
            if market.type in default_categories:
                return default_categories[market.type]
            else:
                raise ValidationError(f"Categories not available for market type: {market.type}")
        except Exception as e:
            raise ValidationError(f"Error fetching categories: {str(e)}")

    async def get_market_analytics(self, market_id: UUID) -> dict:
        """Get analytics for a specific market"""
        market = await self.get_market(market_id)
        
        try:
            # In a real implementation, this would fetch actual analytics data
            # For now, returning mock data
            return {
                "total_products": 1000000,
                "active_deals": 5000,
                "average_discount": 25.5,
                "top_categories": [
                    {"name": "Electronics", "deal_count": 1500},
                    {"name": "Home & Kitchen", "deal_count": 1200},
                    {"name": "Fashion", "deal_count": 800}
                ],
                "price_ranges": {
                    "0-50": 2000,
                    "51-100": 1500,
                    "101-500": 1000,
                    "500+": 500
                },
                "daily_stats": {
                    "new_deals": 250,
                    "expired_deals": 200,
                    "price_drops": 300
                }
            }
        except Exception as e:
            raise ValidationError(f"Error fetching market analytics: {str(e)}")

    async def get_market_comparison(self, market_ids: List[UUID]) -> dict:
        """Compare multiple markets"""
        markets = []
        for market_id in market_ids:
            market = await self.get_market(market_id)
            markets.append(market)
        
        try:
            # In a real implementation, this would fetch actual comparison data
            # For now, returning mock data
            return {
                "comparison_date": "2024-02-03",
                "markets": [
                    {
                        "id": str(market.id),
                        "name": market.name,
                        "type": market.type.value,
                        "metrics": {
                            "total_products": 1000000,
                            "active_deals": 5000,
                            "average_discount": 25.5,
                            "response_time": "120ms",
                            "success_rate": 99.5
                        }
                    }
                    for market in markets
                ],
                "summary": {
                    "best_prices": markets[0].name if markets else None,
                    "most_deals": markets[-1].name if markets else None,
                    "fastest_updates": markets[0].name if markets else None
                }
            }
        except Exception as e:
            raise ValidationError(f"Error comparing markets: {str(e)}")

    async def validate_market_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate market configuration.
        
        Args:
            config: Market configuration dictionary
            
        Returns:
            Dict[str, Any]: The validated configuration 
            
        Raises:
            ValidationError: If the configuration is invalid
        """
        try:
            required_fields = ['headers', 'params']
            for field in required_fields:
                if field not in config:
                    raise ValidationError(f"Missing required config field: {field}")
                    
            if 'timeout' not in config.get('params', {}):
                raise ValidationError("Missing timeout parameter in config")
                
            return config
        except Exception as e:
            raise ValidationError(f"Invalid market configuration: {str(e)}")

    async def test_market_connection(self, market_id: UUID) -> bool:
        """Test connection to a market.
        
        Args:
            market_id: The ID of the market to test
            
        Returns:
            bool: True if connection is successful
            
        Raises:
            MarketNotFoundError: If the market is not found
            MarketConnectionError: If the connection test fails
        """
        try:
            market = await self.get_market(market_id)
            
            # Simulated connection test
            if not market.api_endpoint or not market.api_key:
                raise MarketConnectionError(
                    market=market.name if hasattr(market, 'name') else "Unknown",
                    reason="Market is missing required connection parameters"
                )
                
            # In a real implementation, we would make an actual API request
            # to test the connection. Here we'll just return True.
            return True
        except MarketNotFoundError:
            raise
        except Exception as e:
            raise MarketConnectionError(
                market=getattr(market, 'name', str(market_id)),
                reason=f"Failed to connect to market: {str(e)}"
            )

    async def make_request(self, market_id: UUID, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make a request to a market API endpoint.
        
        Args:
            market_id: The ID of the market to make the request to
            endpoint: The API endpoint to call
            **kwargs: Additional parameters for the request
            
        Returns:
            Dict[str, Any]: Response data from the market API
            
        Raises:
            MarketNotFoundError: If the market is not found
            MarketConnectionError: If the connection fails
            MarketRateLimitError: If the rate limit is exceeded
        """
        try:
            market = await self.get_market(market_id)
            
            # Rate limiting check
            # In a real implementation, this would be more sophisticated
            # For testing, we'll simulate rate limiting based on a counter
            if not hasattr(self, '_request_counter'):
                self._request_counter = {}
            
            if market_id not in self._request_counter:
                self._request_counter[market_id] = 0
                
            self._request_counter[market_id] += 1
            
            # Simple rate limit simulation
            if self._request_counter[market_id] > market.rate_limit:
                return {
                    "status": "rate_limited",
                    "message": "Rate limit exceeded",
                    "retry_after": 60  # seconds
                }
            
            # In a real implementation, we would make an actual API request
            # For testing, we'll just return a simulated response
            return {
                "status": "success",
                "data": {
                    "endpoint": endpoint,
                    "request_id": f"req_{self._request_counter[market_id]}",
                    "timestamp": datetime.now().isoformat()
                }
            }
            
        except MarketNotFoundError:
            raise
        except Exception as e:
            raise MarketConnectionError(
                market=getattr(market, 'name', str(market_id)),
                reason=f"Failed to make request to market: {str(e)}"
            )

    async def update_product_price(self, market_id: UUID, product_url: str, new_price: Decimal) -> Dict[str, Any]:
        """Update the price of a product in a market.
        
        Args:
            market_id: The ID of the market
            product_url: The URL of the product
            new_price: The new price value
            
        Returns:
            Dict containing update status and information
            
        Raises:
            MarketNotFound: If the market doesn't exist
            MarketOperationError: If there's an error updating the price
            ValidationError: If the inputs are invalid
        """
        try:
            # Validate inputs
            if not isinstance(market_id, UUID):
                raise ValidationError(
                    message="Market ID must be a valid UUID",
                    resource_type="market",
                    resource_id=str(market_id)
                )
                
            if not product_url or not isinstance(product_url, str):
                raise ValidationError(
                    message="Product URL must be a valid string",
                    resource_type="product",
                    resource_id=product_url
                )
                
            if not isinstance(new_price, Decimal) or new_price <= 0:
                raise ValidationError(
                    message="Price must be a positive decimal",
                    resource_type="product",
                    resource_id=product_url
                )
            
            # Get the market
            market = await self.get_market(market_id)
            
            # Check cache for existing data
            cache_key = f"market:{market_id}:product:{self._hash_url(product_url)}"
            existing_data = None
            
            if self._redis:
                try:
                    cached_data = await self._redis.get(cache_key)
                    if cached_data:
                        existing_data = json.loads(cached_data)
                except Exception as e:
                    logger.warning(f"Error retrieving from cache: {str(e)}")
            
            # Create update data
            update_data = {
                "url": product_url,
                "price": str(new_price),  # Convert Decimal to string for serialization
                "currency": market.default_currency or "USD",
                "market_id": str(market_id),
                "updated_at": datetime.utcnow().isoformat(),
                "previous_price": existing_data["price"] if existing_data else None,
                "price_change": str(Decimal(existing_data["price"]) - new_price) if existing_data and "price" in existing_data else None,
                "source": "manual_update"
            }
            
            # Update cache
            if self._redis:
                try:
                    await self._redis.set(
                        cache_key, 
                        json.dumps(update_data),
                        ex=3600 * 24  # 24 hour cache
                    )
                except Exception as e:
                    logger.warning(f"Error updating cache: {str(e)}")
            
            logger.info(
                f"Updated product price in market {market.name}",
                extra={
                    "market_id": str(market_id),
                    "product_url": product_url,
                    "new_price": str(new_price),
                    "old_price": existing_data["price"] if existing_data and "price" in existing_data else "unknown"
                }
            )
            
            return update_data
            
        except NotFoundException as e:
            logger.error(
                f"Market not found for price update: {str(e)}",
                extra={
                    "market_id": str(market_id),
                    "product_url": product_url
                }
            )
            raise
            
        except ValidationError as e:
            logger.error(
                f"Validation error on product price update: {str(e)}",
                extra={
                    "market_id": str(market_id),
                    "product_url": product_url,
                    "new_price": str(new_price) if isinstance(new_price, Decimal) else str(new_price)
                }
            )
            raise
            
        except Exception as e:
            # Get market name if possible
            market_name = None
            try:
                market = await self.get_market(market_id)
                market_name = market.name
            except:
                market_name = str(market_id)
                
            # Add required parameters to the MarketOperationError
            raise MarketOperationError(
                f"Failed to update product price: {str(e)}",
                operation="update_product_price",
                market=market_name,
                reason=f"Error processing request: {str(e)}"
            )
            
    def _hash_url(self, url: str) -> str:
        """Create a hash of a URL to use as a cache key."""
        return hashlib.md5(url.encode('utf-8')).hexdigest() 