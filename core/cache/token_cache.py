from typing import Optional, Dict, Any, List
import json
from datetime import datetime, timedelta
from redis import Redis
from ..utils.logger import get_logger

logger = get_logger(__name__)

class TokenCache:
    """Cache handler for token-related data"""
    
    # Cache key prefixes
    BALANCE_PREFIX = "token:balance:"
    PRICE_PREFIX = "token:price:"
    TRANSACTION_PREFIX = "token:transaction:"
    WALLET_PREFIX = "token:wallet:"
    METRICS_PREFIX = "token:metrics:"
    
    # Default TTLs (in seconds)
    BALANCE_TTL = 300  # 5 minutes
    PRICE_TTL = 60    # 1 minute
    TRANSACTION_TTL = 3600  # 1 hour
    WALLET_TTL = 3600  # 1 hour
    METRICS_TTL = 60  # 1 minute
    
    def __init__(self, redis_client: Redis):
        self.redis = redis_client

    async def get_user_balance(
        self,
        user_id: str
    ) -> Optional[float]:
        """Get cached user balance"""
        try:
            key = f"{self.BALANCE_PREFIX}{user_id}"
            value = await self.redis.get(key)
            
            if value:
                return float(value.decode())
            return None
            
        except Exception as e:
            logger.error(f"Error getting cached balance for user {user_id}: {str(e)}")
            return None

    async def set_user_balance(
        self,
        user_id: str,
        balance: float,
        ttl: Optional[int] = None
    ) -> bool:
        """Set user balance in cache"""
        try:
            key = f"{self.BALANCE_PREFIX}{user_id}"
            await self.redis.set(
                key,
                str(balance),
                ex=ttl or self.BALANCE_TTL
            )
            return True
            
        except Exception as e:
            logger.error(f"Error caching balance for user {user_id}: {str(e)}")
            return False

    async def get_token_price(
        self,
        source: str = "default"
    ) -> Optional[Dict[str, Any]]:
        """Get cached token price"""
        try:
            key = f"{self.PRICE_PREFIX}{source}"
            value = await self.redis.get(key)
            
            if value:
                return json.loads(value.decode())
            return None
            
        except Exception as e:
            logger.error(f"Error getting cached price from {source}: {str(e)}")
            return None

    async def set_token_price(
        self,
        price_data: Dict[str, Any],
        source: str = "default",
        ttl: Optional[int] = None
    ) -> bool:
        """Set token price in cache"""
        try:
            key = f"{self.PRICE_PREFIX}{source}"
            await self.redis.set(
                key,
                json.dumps(price_data),
                ex=ttl or self.PRICE_TTL
            )
            return True
            
        except Exception as e:
            logger.error(f"Error caching price for source {source}: {str(e)}")
            return False

    async def get_transaction(
        self,
        transaction_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get cached transaction"""
        try:
            key = f"{self.TRANSACTION_PREFIX}{transaction_id}"
            value = await self.redis.get(key)
            
            if value:
                return json.loads(value.decode())
            return None
            
        except Exception as e:
            logger.error(f"Error getting cached transaction {transaction_id}: {str(e)}")
            return None

    async def set_transaction(
        self,
        transaction_id: str,
        transaction_data: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """Set transaction in cache"""
        try:
            key = f"{self.TRANSACTION_PREFIX}{transaction_id}"
            await self.redis.set(
                key,
                json.dumps(transaction_data),
                ex=ttl or self.TRANSACTION_TTL
            )
            return True
            
        except Exception as e:
            logger.error(f"Error caching transaction {transaction_id}: {str(e)}")
            return False

    async def get_wallet(
        self,
        wallet_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get cached wallet"""
        try:
            key = f"{self.WALLET_PREFIX}{wallet_id}"
            value = await self.redis.get(key)
            
            if value:
                return json.loads(value.decode())
            return None
            
        except Exception as e:
            logger.error(f"Error getting cached wallet {wallet_id}: {str(e)}")
            return None

    async def set_wallet(
        self,
        wallet_id: str,
        wallet_data: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """Set wallet in cache"""
        try:
            key = f"{self.WALLET_PREFIX}{wallet_id}"
            await self.redis.set(
                key,
                json.dumps(wallet_data),
                ex=ttl or self.WALLET_TTL
            )
            return True
            
        except Exception as e:
            logger.error(f"Error caching wallet {wallet_id}: {str(e)}")
            return False

    async def get_metrics(
        self,
        metric_name: str
    ) -> Optional[Dict[str, Any]]:
        """Get cached metrics"""
        try:
            key = f"{self.METRICS_PREFIX}{metric_name}"
            value = await self.redis.get(key)
            
            if value:
                return json.loads(value.decode())
            return None
            
        except Exception as e:
            logger.error(f"Error getting cached metrics {metric_name}: {str(e)}")
            return None

    async def set_metrics(
        self,
        metric_name: str,
        metric_data: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """Set metrics in cache"""
        try:
            key = f"{self.METRICS_PREFIX}{metric_name}"
            await self.redis.set(
                key,
                json.dumps(metric_data),
                ex=ttl or self.METRICS_TTL
            )
            return True
            
        except Exception as e:
            logger.error(f"Error caching metrics {metric_name}: {str(e)}")
            return False

    async def invalidate_user_balance(
        self,
        user_id: str
    ) -> bool:
        """Invalidate user balance cache"""
        try:
            key = f"{self.BALANCE_PREFIX}{user_id}"
            await self.redis.delete(key)
            return True
            
        except Exception as e:
            logger.error(f"Error invalidating balance cache for user {user_id}: {str(e)}")
            return False

    async def invalidate_token_price(
        self,
        source: str = "default"
    ) -> bool:
        """Invalidate token price cache"""
        try:
            key = f"{self.PRICE_PREFIX}{source}"
            await self.redis.delete(key)
            return True
            
        except Exception as e:
            logger.error(f"Error invalidating price cache for source {source}: {str(e)}")
            return False

    async def invalidate_transaction(
        self,
        transaction_id: str
    ) -> bool:
        """Invalidate transaction cache"""
        try:
            key = f"{self.TRANSACTION_PREFIX}{transaction_id}"
            await self.redis.delete(key)
            return True
            
        except Exception as e:
            logger.error(f"Error invalidating transaction cache {transaction_id}: {str(e)}")
            return False

    async def invalidate_wallet(
        self,
        wallet_id: str
    ) -> bool:
        """Invalidate wallet cache"""
        try:
            key = f"{self.WALLET_PREFIX}{wallet_id}"
            await self.redis.delete(key)
            return True
            
        except Exception as e:
            logger.error(f"Error invalidating wallet cache {wallet_id}: {str(e)}")
            return False

    async def clear_all_token_cache(self) -> bool:
        """Clear all token-related cache"""
        try:
            # Get all keys with token prefix
            keys = []
            for prefix in [
                self.BALANCE_PREFIX,
                self.PRICE_PREFIX,
                self.TRANSACTION_PREFIX,
                self.WALLET_PREFIX,
                self.METRICS_PREFIX
            ]:
                pattern = f"{prefix}*"
                keys.extend(await self.redis.keys(pattern))
            
            if keys:
                await self.redis.delete(*keys)
            
            return True
            
        except Exception as e:
            logger.error(f"Error clearing all token cache: {str(e)}")
            return False

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            stats = {
                "balances": len(await self.redis.keys(f"{self.BALANCE_PREFIX}*")),
                "prices": len(await self.redis.keys(f"{self.PRICE_PREFIX}*")),
                "transactions": len(await self.redis.keys(f"{self.TRANSACTION_PREFIX}*")),
                "wallets": len(await self.redis.keys(f"{self.WALLET_PREFIX}*")),
                "metrics": len(await self.redis.keys(f"{self.METRICS_PREFIX}*"))
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting cache stats: {str(e)}")
            return {} 