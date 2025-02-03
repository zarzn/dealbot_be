from typing import Optional, Dict, Any, List
from uuid import UUID
import json
from datetime import datetime, timedelta
import aioredis
import logging

from core.config import settings
from core.exceptions import TokenCacheError
from ..utils.logger import get_logger

logger = logging.getLogger(__name__)

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
    
    def __init__(self, redis: aioredis.Redis):
        self.redis = redis
        self.ttl = settings.TOKEN_CACHE_TTL

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

    async def get_allowance(self, user_id: UUID, spender: str) -> Optional[float]:
        """Get cached token allowance."""
        try:
            allowance = await self.redis.get(f"allowance:{user_id}:{spender}")
            return float(allowance) if allowance else None
        except Exception as e:
            logger.error(f"Error getting allowance from cache: {e}")
            return None

    async def set_allowance(self, user_id: UUID, spender: str, amount: float) -> None:
        """Cache token allowance."""
        try:
            await self.redis.setex(
                f"allowance:{user_id}:{spender}",
                self.ttl,
                str(amount)
            )
        except Exception as e:
            logger.error(f"Error setting allowance in cache: {e}")
            raise TokenCacheError(f"Failed to cache allowance: {str(e)}")

    async def invalidate_allowance(self, user_id: UUID, spender: str) -> None:
        """Invalidate cached token allowance."""
        try:
            await self.redis.delete(f"allowance:{user_id}:{spender}")
        except Exception as e:
            logger.error(f"Error invalidating allowance cache: {e}")
            raise TokenCacheError(f"Failed to invalidate allowance cache: {str(e)}")

    async def get_rewards(self, user_id: UUID) -> Optional[float]:
        """Get cached token rewards."""
        try:
            rewards = await self.redis.get(f"rewards:{user_id}")
            return float(rewards) if rewards else None
        except Exception as e:
            logger.error(f"Error getting rewards from cache: {e}")
            return None

    async def set_rewards(self, user_id: UUID, amount: float) -> None:
        """Cache token rewards."""
        try:
            await self.redis.setex(
                f"rewards:{user_id}",
                self.ttl,
                str(amount)
            )
        except Exception as e:
            logger.error(f"Error setting rewards in cache: {e}")
            raise TokenCacheError(f"Failed to cache rewards: {str(e)}")

    async def invalidate_rewards(self, user_id: UUID) -> None:
        """Invalidate cached token rewards."""
        try:
            await self.redis.delete(f"rewards:{user_id}")
        except Exception as e:
            logger.error(f"Error invalidating rewards cache: {e}")
            raise TokenCacheError(f"Failed to invalidate rewards cache: {str(e)}")

    async def get_usage(self, user_id: UUID) -> Optional[Dict[str, Any]]:
        """Get cached token usage stats."""
        try:
            usage = await self.redis.get(f"usage:{user_id}")
            return json.loads(usage) if usage else None
        except Exception as e:
            logger.error(f"Error getting usage stats from cache: {e}")
            return None

    async def set_usage(self, user_id: UUID, usage: Dict[str, Any]) -> None:
        """Cache token usage stats."""
        try:
            await self.redis.setex(
                f"usage:{user_id}",
                self.ttl,
                json.dumps(usage)
            )
        except Exception as e:
            logger.error(f"Error setting usage stats in cache: {e}")
            raise TokenCacheError(f"Failed to cache usage stats: {str(e)}")

    async def invalidate_usage(self, user_id: UUID) -> None:
        """Invalidate cached token usage stats."""
        try:
            await self.redis.delete(f"usage:{user_id}")
        except Exception as e:
            logger.error(f"Error invalidating usage stats cache: {e}")
            raise TokenCacheError(f"Failed to invalidate usage stats cache: {str(e)}")

    async def clear_all(self, user_id: UUID) -> None:
        """Clear all cached data for user."""
        try:
            keys = await self.redis.keys(f"*:{user_id}*")
            if keys:
                await self.redis.delete(*keys)
        except Exception as e:
            logger.error(f"Error clearing all cache for user: {e}")
            raise TokenCacheError(f"Failed to clear all cache: {str(e)}")

    async def get_metrics(self, user_id: UUID) -> Optional[Dict[str, Any]]:
        """Get cached token metrics."""
        try:
            metrics = await self.redis.get(f"metrics:{user_id}")
            return json.loads(metrics) if metrics else None
        except Exception as e:
            logger.error(f"Error getting metrics from cache: {e}")
            return None

    async def set_metrics(self, user_id: UUID, metrics: Dict[str, Any]) -> None:
        """Cache token metrics."""
        try:
            await self.redis.setex(
                f"metrics:{user_id}",
                self.ttl,
                json.dumps(metrics)
            )
        except Exception as e:
            logger.error(f"Error setting metrics in cache: {e}")
            raise TokenCacheError(f"Failed to cache metrics: {str(e)}")

    async def invalidate_metrics(self, user_id: UUID) -> None:
        """Invalidate cached token metrics."""
        try:
            await self.redis.delete(f"metrics:{user_id}")
        except Exception as e:
            logger.error(f"Error invalidating metrics cache: {e}")
            raise TokenCacheError(f"Failed to invalidate metrics cache: {str(e)}")

    async def get_rate_limit(self, key: str) -> Optional[int]:
        """Get rate limit counter."""
        try:
            count = await self.redis.get(f"ratelimit:{key}")
            return int(count) if count else None
        except Exception as e:
            logger.error(f"Error getting rate limit from cache: {e}")
            return None

    async def increment_rate_limit(self, key: str, ttl: int) -> int:
        """Increment rate limit counter."""
        try:
            count = await self.redis.incr(f"ratelimit:{key}")
            await self.redis.expire(f"ratelimit:{key}", ttl)
            return count
        except Exception as e:
            logger.error(f"Error incrementing rate limit in cache: {e}")
            raise TokenCacheError(f"Failed to increment rate limit: {str(e)}")

    async def reset_rate_limit(self, key: str) -> None:
        """Reset rate limit counter."""
        try:
            await self.redis.delete(f"ratelimit:{key}")
        except Exception as e:
            logger.error(f"Error resetting rate limit in cache: {e}")
            raise TokenCacheError(f"Failed to reset rate limit: {str(e)}")

    async def get_lock(self, key: str) -> bool:
        """Acquire distributed lock."""
        try:
            return await self.redis.set(
                f"lock:{key}",
                "1",
                ex=settings.TOKEN_LOCK_TTL,
                nx=True
            )
        except Exception as e:
            logger.error(f"Error acquiring lock in cache: {e}")
            return False

    async def release_lock(self, key: str) -> None:
        """Release distributed lock."""
        try:
            await self.redis.delete(f"lock:{key}")
        except Exception as e:
            logger.error(f"Error releasing lock in cache: {e}")
            raise TokenCacheError(f"Failed to release lock: {str(e)}")

    async def get_pending_transactions(self, user_id: UUID) -> List[Dict[str, Any]]:
        """Get list of pending transactions."""
        try:
            tx_list = await self.redis.lrange(f"pending_tx:{user_id}", 0, -1)
            return [json.loads(tx) for tx in tx_list]
        except Exception as e:
            logger.error(f"Error getting pending transactions from cache: {e}")
            return []

    async def add_pending_transaction(self, user_id: UUID, tx_data: Dict[str, Any]) -> None:
        """Add transaction to pending list."""
        try:
            await self.redis.lpush(
                f"pending_tx:{user_id}",
                json.dumps(tx_data)
            )
            await self.redis.ltrim(
                f"pending_tx:{user_id}",
                0,
                settings.MAX_PENDING_TRANSACTIONS - 1
            )
        except Exception as e:
            logger.error(f"Error adding pending transaction to cache: {e}")
            raise TokenCacheError(f"Failed to add pending transaction: {str(e)}")

    async def remove_pending_transaction(self, user_id: UUID, tx_id: str) -> None:
        """Remove transaction from pending list."""
        try:
            tx_list = await self.redis.lrange(f"pending_tx:{user_id}", 0, -1)
            for tx in tx_list:
                tx_data = json.loads(tx)
                if tx_data.get("id") == tx_id:
                    await self.redis.lrem(f"pending_tx:{user_id}", 1, tx)
                    break
        except Exception as e:
            logger.error(f"Error removing pending transaction from cache: {e}")
            raise TokenCacheError(f"Failed to remove pending transaction: {str(e)}")

    async def get_transaction_history(self, user_id: UUID, limit: int = 10) -> List[Dict[str, Any]]:
        """Get cached transaction history."""
        try:
            tx_list = await self.redis.lrange(f"tx_history:{user_id}", 0, limit - 1)
            return [json.loads(tx) for tx in tx_list]
        except Exception as e:
            logger.error(f"Error getting transaction history from cache: {e}")
            return []

    async def add_transaction_history(self, user_id: UUID, tx_data: Dict[str, Any]) -> None:
        """Add transaction to history cache."""
        try:
            await self.redis.lpush(
                f"tx_history:{user_id}",
                json.dumps(tx_data)
            )
            await self.redis.ltrim(
                f"tx_history:{user_id}",
                0,
                settings.MAX_TRANSACTION_HISTORY - 1
            )
        except Exception as e:
            logger.error(f"Error adding transaction to history cache: {e}")
            raise TokenCacheError(f"Failed to add transaction to history: {str(e)}")

    async def clear_transaction_history(self, user_id: UUID) -> None:
        """Clear transaction history cache."""
        try:
            await self.redis.delete(f"tx_history:{user_id}")
        except Exception as e:
            logger.error(f"Error clearing transaction history cache: {e}")
            raise TokenCacheError(f"Failed to clear transaction history: {str(e)}") 