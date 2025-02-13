"""Base agent interface.

This module defines the base agent interface and common functionality
for all agents in the system.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from datetime import datetime
import asyncio
from pydantic import BaseModel

from core.agents.config.agent_config import (
    PriorityLevel,
    LLMProvider,
    PRIORITY_CONFIGS,
    LLM_CONFIGS,
    PERFORMANCE_THRESHOLDS
)
from core.utils.redis import get_redis_client
from core.utils.logger import get_logger

logger = get_logger(__name__)

class AgentRequest(BaseModel):
    """Base model for agent requests"""
    request_id: str
    user_id: str
    priority: PriorityLevel
    payload: Dict[str, Any]
    timestamp: datetime = datetime.utcnow()
    context: Optional[Dict[str, Any]] = None

class AgentResponse(BaseModel):
    """Base model for agent responses"""
    request_id: str
    status: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    processing_time: float
    cache_hit: bool = False

class BaseAgent(ABC):
    """Base agent class implementing common functionality"""

    def __init__(self, name: str):
        self.name = name
        self.redis_client = None
        self._initialize_metrics()

    async def initialize(self):
        """Initialize agent resources"""
        self.redis_client = await get_redis_client()
        await self._setup_agent()

    @abstractmethod
    async def _setup_agent(self):
        """Agent-specific setup"""
        pass

    async def process(self, request: AgentRequest) -> AgentResponse:
        """Main processing method with monitoring and error handling"""
        start_time = datetime.utcnow()
        
        try:
            # Check cache first
            cache_key = self._generate_cache_key(request)
            cached_response = await self._get_cached_response(cache_key)
            if cached_response:
                return AgentResponse(
                    request_id=request.request_id,
                    status="success",
                    data=cached_response,
                    processing_time=(datetime.utcnow() - start_time).total_seconds(),
                    cache_hit=True
                )

            # Process request
            config = PRIORITY_CONFIGS[request.priority]
            result = await asyncio.wait_for(
                self._process_request(request),
                timeout=config.timeout
            )

            # Cache successful response
            if result and "error" not in result:
                await self._cache_response(cache_key, result)

            return AgentResponse(
                request_id=request.request_id,
                status="success",
                data=result,
                processing_time=(datetime.utcnow() - start_time).total_seconds(),
                cache_hit=False
            )

        except asyncio.TimeoutError:
            logger.error(f"Agent {self.name} timeout for request {request.request_id}")
            return self._create_error_response(
                request.request_id,
                "Processing timeout",
                start_time
            )
        except Exception as e:
            logger.error(f"Agent {self.name} error: {str(e)}", exc_info=True)
            return self._create_error_response(
                request.request_id,
                str(e),
                start_time
            )

    @abstractmethod
    async def _process_request(self, request: AgentRequest) -> Dict[str, Any]:
        """Agent-specific request processing"""
        pass

    async def _get_cached_response(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached response if available"""
        if self.redis_client:
            return await self.redis_client.get(cache_key)
        return None

    async def _cache_response(self, cache_key: str, response: Dict[str, Any]):
        """Cache successful response"""
        if self.redis_client:
            await self.redis_client.set(
                cache_key,
                response,
                ex=PERFORMANCE_THRESHOLDS["cache_ttl"]
            )

    def _generate_cache_key(self, request: AgentRequest) -> str:
        """Generate cache key for request"""
        return f"agent:{self.name}:request:{request.request_id}"

    def _create_error_response(
        self,
        request_id: str,
        error_message: str,
        start_time: datetime
    ) -> AgentResponse:
        """Create error response"""
        return AgentResponse(
            request_id=request_id,
            status="error",
            error=error_message,
            processing_time=(datetime.utcnow() - start_time).total_seconds(),
            cache_hit=False
        )

    def _initialize_metrics(self):
        """Initialize agent metrics"""
        self.metrics = {
            "requests_processed": 0,
            "cache_hits": 0,
            "errors": 0,
            "average_processing_time": 0
        }

    async def get_metrics(self) -> Dict[str, Any]:
        """Get agent metrics"""
        return self.metrics

    async def health_check(self) -> bool:
        """Check agent health"""
        try:
            if self.redis_client:
                await self.redis_client.ping()
            return True
        except Exception as e:
            logger.error(f"Agent {self.name} health check failed: {str(e)}")
            return False 