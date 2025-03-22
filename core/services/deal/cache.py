"""Deal caching module.

This module provides caching functionality for deal objects.
"""

import json
import logging
from typing import Optional, Dict, Any
from uuid import UUID
from redis.asyncio import Redis
from datetime import datetime
import asyncio

from core.models.deal import Deal
from core.services.redis import UUIDEncoder
from .utils import _deal_to_dict

logger = logging.getLogger(__name__)

# Cache TTL constants
CACHE_TTL_BASIC = 7200  # 2 hours
CACHE_TTL_FULL = 3600   # 1 hour
CACHE_TTL_PRICE_HISTORY = 86400  # 24 hours

async def _cache_deal(self, deal: Deal) -> None:
    """Cache a deal in Redis.
    
    Args:
        deal: The deal to cache
    """
    if not self._redis:
        logger.debug("Redis client not available, skipping deal caching")
        return
        
    try:
        # Convert deal to JSON-serializable dict
        deal_dict = _deal_to_dict(deal)
        
        # Cache basic deal info with appropriate TTL
        await self._redis.set(
            f"deal:{deal.id}:basic",
            json.dumps(deal_dict, cls=UUIDEncoder),
            ex=CACHE_TTL_BASIC
        )
        
        # Cache full deal info including price history if available
        full_deal = deal_dict.copy()
        
        if hasattr(deal, 'price_history') and deal.price_history:
            # Add price history if available
            full_deal['price_history'] = [
                {
                    'id': str(ph.id),
                    'deal_id': str(ph.deal_id),
                    'price': float(ph.price) if hasattr(ph, 'price') else 0.0,
                    'source': ph.source if hasattr(ph, 'source') else "unknown",
                    'timestamp': ph.timestamp.isoformat() if hasattr(ph, 'timestamp') and ph.timestamp else None
                }
                for ph in deal.price_history
            ]
            
        # Store additional metadata if available
        if hasattr(deal, 'analytics') and deal.analytics:
            try:
                full_deal['analytics'] = deal.analytics if isinstance(deal.analytics, dict) else dict(deal.analytics)
            except (TypeError, ValueError):
                full_deal['analytics'] = {'error': 'Could not convert analytics to dict'}
                
        # Set full deal with appropriate TTL
        await self._redis.set(
            f"deal:{deal.id}:full",
            json.dumps(full_deal, cls=UUIDEncoder),
            ex=CACHE_TTL_FULL
        )
        
        # Store in deals by category set if category exists
        if hasattr(deal, 'category') and deal.category:
            category_key = f"deals:category:{deal.category}"
            await self._redis.zadd(
                category_key,
                {str(deal.id): float(datetime.utcnow().timestamp())},
                nx=True
            )
            # Set expiration on the sorted set
            await self._redis.expire(category_key, CACHE_TTL_BASIC)
            
        # Store in deals by user set if user_id exists
        if hasattr(deal, 'user_id') and deal.user_id:
            user_key = f"user:{deal.user_id}:deals"
            await self._redis.zadd(
                user_key,
                {str(deal.id): float(datetime.utcnow().timestamp())},
                nx=True
            )
            # Set expiration on the sorted set
            await self._redis.expire(user_key, CACHE_TTL_BASIC)
        
        logger.debug(f"Deal {deal.id} cached successfully")
    except Exception as e:
        logger.error(f"Failed to cache deal {deal.id}: {str(e)}")
        # Don't raise exception - caching errors shouldn't break the main flow

async def _get_cached_deal(self, deal_id: str) -> Optional[Deal]:
    """Get a deal from the Redis cache.
    
    Args:
        deal_id: The deal ID
        
    Returns:
        Deal object if found in cache, None otherwise
    """
    if not self._redis:
        logger.debug("Redis client not available, skipping cache fetch")
        return None
        
    try:
        # Try to get deal from cache
        cached_deal = await self._redis.get(f"deal:{deal_id}:full")
        if not cached_deal:
            logger.debug(f"Deal {deal_id} not found in cache")
            return None
            
        # Parse cached deal JSON and convert to Deal object
        deal_dict = json.loads(cached_deal)
        
        # Create a Deal object from the cached data
        from core.models.deal import Deal
        
        # Handle UUID fields
        if 'id' in deal_dict and deal_dict['id']:
            deal_dict['id'] = UUID(deal_dict['id'])
        if 'user_id' in deal_dict and deal_dict['user_id']:
            deal_dict['user_id'] = UUID(deal_dict['user_id'])
        if 'goal_id' in deal_dict and deal_dict['goal_id']:
            deal_dict['goal_id'] = UUID(deal_dict['goal_id'])
        if 'market_id' in deal_dict and deal_dict['market_id']:
            deal_dict['market_id'] = UUID(deal_dict['market_id'])
        
        # Handle price as Decimal
        if 'price' in deal_dict and deal_dict['price']:
            from decimal import Decimal
            deal_dict['price'] = Decimal(str(deal_dict['price']))
            
        # Handle original_price as Decimal if present
        if 'original_price' in deal_dict and deal_dict['original_price']:
            from decimal import Decimal
            deal_dict['original_price'] = Decimal(str(deal_dict['original_price']))
            
        # Handle dates
        if 'created_at' in deal_dict and deal_dict['created_at']:
            from datetime import datetime
            try:
                deal_dict['created_at'] = datetime.fromisoformat(deal_dict['created_at'].replace('Z', '+00:00'))
            except (ValueError, TypeError):
                deal_dict['created_at'] = datetime.utcnow()
                
        if 'updated_at' in deal_dict and deal_dict['updated_at']:
            from datetime import datetime
            try:
                deal_dict['updated_at'] = datetime.fromisoformat(deal_dict['updated_at'].replace('Z', '+00:00'))
            except (ValueError, TypeError):
                deal_dict['updated_at'] = datetime.utcnow()
                
        if 'found_at' in deal_dict and deal_dict['found_at']:
            from datetime import datetime
            try:
                deal_dict['found_at'] = datetime.fromisoformat(deal_dict['found_at'].replace('Z', '+00:00'))
            except (ValueError, TypeError):
                deal_dict['found_at'] = datetime.utcnow()
                
        if 'expires_at' in deal_dict and deal_dict['expires_at']:
            from datetime import datetime
            try:
                deal_dict['expires_at'] = datetime.fromisoformat(deal_dict['expires_at'].replace('Z', '+00:00'))
            except (ValueError, TypeError):
                deal_dict['expires_at'] = None
        
        # Remove any fields that aren't part of the Deal model
        for key in list(deal_dict.keys()):
            if key not in Deal.__annotations__ and key not in ['price_history', 'analytics']:
                deal_dict.pop(key)
                
        # Create a proper Deal instance
        deal = Deal(**deal_dict)
        
        # Update the last accessed timestamp to extend caching for frequently accessed deals
        asyncio.create_task(self._update_cache_access(deal_id))
            
        logger.debug(f"Deal {deal_id} retrieved from cache")
        return deal
        
    except Exception as e:
        logger.error(f"Failed to get cached deal {deal_id}: {str(e)}")
        return None
        
async def _update_cache_access(self, deal_id: str) -> None:
    """Update the last access timestamp for a cached deal.
    
    This helps extend caching for frequently accessed deals.
    
    Args:
        deal_id: The deal ID
    """
    if not self._redis:
        return
        
    try:
        # Update access time in frequently accessed set
        await self._redis.zadd(
            "deals:frequently_accessed",
            {deal_id: float(datetime.utcnow().timestamp())}
        )
        
        # Keep the set size manageable - trim to 1000 most recent
        await self._redis.zremrangebyrank("deals:frequently_accessed", 0, -1001)
        
        # Extend TTL for frequently accessed deals
        await self._redis.expire(f"deal:{deal_id}:basic", CACHE_TTL_BASIC * 2)
        await self._redis.expire(f"deal:{deal_id}:full", CACHE_TTL_FULL * 2)
    except Exception as e:
        logger.debug(f"Error updating cache access for deal {deal_id}: {str(e)}")
        # Non-critical error, don't propagate 