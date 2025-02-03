"""Redis session utility.

This module provides a Redis-based session management implementation.
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union

import redis.asyncio as redis
from redis.exceptions import RedisError

from ..exceptions import CacheConnectionError, CacheOperationError
from ..config import settings

logger = logging.getLogger(__name__)

class RedisSession:
    """Asynchronous Redis-based session manager."""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        prefix: str = "session",
        default_ttl: int = 3600,  # 1 hour
        cleanup_interval: int = 300  # 5 minutes
    ):
        """Initialize session manager.
        
        Args:
            redis_client: Redis client instance
            prefix: Session key prefix
            default_ttl: Default session TTL in seconds
            cleanup_interval: Interval for cleaning expired sessions
        """
        self.redis = redis_client
        self.prefix = prefix
        self.default_ttl = default_ttl
        self.cleanup_interval = cleanup_interval

    def _make_key(self, session_id: str) -> str:
        """Create session key.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session key
        """
        return f"{self.prefix}:{session_id}"

    async def create_session(
        self,
        data: Dict[str, Any],
        session_id: Optional[str] = None,
        ttl: Optional[int] = None
    ) -> str:
        """Create new session.
        
        Args:
            data: Session data
            session_id: Optional session ID
            ttl: Optional session TTL in seconds
            
        Returns:
            Session ID
            
        Raises:
            CacheOperationError: If session creation fails
        """
        try:
            session_id = session_id or str(uuid.uuid4())
            key = self._make_key(session_id)
            
            session = {
                "id": session_id,
                "data": data,
                "created_at": datetime.utcnow().timestamp(),
                "last_accessed": datetime.utcnow().timestamp()
            }
            
            await self.redis.setex(
                key,
                ttl or self.default_ttl,
                json.dumps(session)
            )
            
            return session_id
            
        except RedisError as e:
            raise CacheOperationError(
                message="Failed to create session",
                details={"session_id": session_id, "error": str(e)}
            )

    async def get_session(
        self,
        session_id: str,
        update_access: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Get session data.
        
        Args:
            session_id: Session identifier
            update_access: Whether to update last access time
            
        Returns:
            Session data or None if not found
            
        Raises:
            CacheOperationError: If session retrieval fails
        """
        try:
            key = self._make_key(session_id)
            data = await self.redis.get(key)
            
            if not data:
                return None
                
            session = json.loads(data)
            
            if update_access:
                session["last_accessed"] = datetime.utcnow().timestamp()
                ttl = await self.redis.ttl(key)
                
                if ttl > 0:
                    await self.redis.setex(
                        key,
                        ttl,
                        json.dumps(session)
                    )
            
            return session["data"]
            
        except RedisError as e:
            raise CacheOperationError(
                message="Failed to get session",
                details={"session_id": session_id, "error": str(e)}
            )

    async def update_session(
        self,
        session_id: str,
        data: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> None:
        """Update session data.
        
        Args:
            session_id: Session identifier
            data: New session data
            ttl: Optional new TTL in seconds
            
        Raises:
            CacheOperationError: If session update fails
        """
        try:
            key = self._make_key(session_id)
            session_data = await self.redis.get(key)
            
            if not session_data:
                raise CacheOperationError(
                    message="Session not found",
                    details={"session_id": session_id}
                )
                
            session = json.loads(session_data)
            session["data"] = data
            session["last_accessed"] = datetime.utcnow().timestamp()
            
            if ttl is not None:
                await self.redis.setex(
                    key,
                    ttl,
                    json.dumps(session)
                )
            else:
                current_ttl = await self.redis.ttl(key)
                if current_ttl > 0:
                    await self.redis.setex(
                        key,
                        current_ttl,
                        json.dumps(session)
                    )
                else:
                    await self.redis.setex(
                        key,
                        self.default_ttl,
                        json.dumps(session)
                    )
                    
        except RedisError as e:
            raise CacheOperationError(
                message="Failed to update session",
                details={"session_id": session_id, "error": str(e)}
            )

    async def delete_session(self, session_id: str) -> None:
        """Delete session.
        
        Args:
            session_id: Session identifier
            
        Raises:
            CacheOperationError: If session deletion fails
        """
        try:
            key = self._make_key(session_id)
            await self.redis.delete(key)
            
        except RedisError as e:
            raise CacheOperationError(
                message="Failed to delete session",
                details={"session_id": session_id, "error": str(e)}
            )

    async def extend_session(
        self,
        session_id: str,
        ttl: Optional[int] = None
    ) -> None:
        """Extend session TTL.
        
        Args:
            session_id: Session identifier
            ttl: Optional new TTL in seconds
            
        Raises:
            CacheOperationError: If session extension fails
        """
        try:
            key = self._make_key(session_id)
            session_data = await self.redis.get(key)
            
            if not session_data:
                raise CacheOperationError(
                    message="Session not found",
                    details={"session_id": session_id}
                )
                
            session = json.loads(session_data)
            session["last_accessed"] = datetime.utcnow().timestamp()
            
            await self.redis.setex(
                key,
                ttl or self.default_ttl,
                json.dumps(session)
            )
            
        except RedisError as e:
            raise CacheOperationError(
                message="Failed to extend session",
                details={"session_id": session_id, "error": str(e)}
            )

    async def cleanup_expired(self) -> None:
        """Clean up expired sessions."""
        try:
            pattern = f"{self.prefix}:*"
            cursor = 0
            
            while True:
                cursor, keys = await self.redis.scan(
                    cursor,
                    match=pattern,
                    count=100
                )
                
                for key in keys:
                    ttl = await self.redis.ttl(key)
                    if ttl <= 0:
                        await self.redis.delete(key)
                        
                if cursor == 0:
                    break
                    
        except RedisError as e:
            logger.error(f"Error cleaning up expired sessions: {str(e)}")

class SessionManager:
    """Manager for creating session managers."""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        default_ttl: int = 3600,
        cleanup_interval: int = 300
    ):
        """Initialize session manager.
        
        Args:
            redis_client: Redis client instance
            default_ttl: Default session TTL in seconds
            cleanup_interval: Default cleanup interval in seconds
        """
        self.redis = redis_client
        self.default_ttl = default_ttl
        self.cleanup_interval = cleanup_interval
        self._session_managers: Dict[str, RedisSession] = {}

    def get_session_manager(
        self,
        prefix: str,
        default_ttl: Optional[int] = None,
        cleanup_interval: Optional[int] = None
    ) -> RedisSession:
        """Get or create session manager.
        
        Args:
            prefix: Session manager prefix
            default_ttl: Optional default session TTL in seconds
            cleanup_interval: Optional cleanup interval in seconds
            
        Returns:
            RedisSession instance
        """
        if prefix not in self._session_managers:
            self._session_managers[prefix] = RedisSession(
                redis_client=self.redis,
                prefix=prefix,
                default_ttl=default_ttl or self.default_ttl,
                cleanup_interval=cleanup_interval or self.cleanup_interval
            )
        return self._session_managers[prefix] 