"""Base agent interface.

This module defines the base agent interface and common functionality
for all agents in the system.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from datetime import datetime
import asyncio
import json
from pydantic import BaseModel

from core.agents.config.agent_config import (
    PriorityLevel,
    LLMProvider,
    PRIORITY_CONFIGS,
    LLM_CONFIGS,
    PERFORMANCE_THRESHOLDS
)
from core.agents.base.agent_interface import AgentTask
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
    processing_time: Optional[float] = None
    cache_hit: bool = False

class BaseAgent(ABC):
    """Base agent class implementing common functionality"""

    def __init__(self, name: str, redis_client: Optional[Any] = None):
        """Initialize base agent.
        
        Args:
            name: Agent name
            redis_client: Optional Redis client
        """
        self.name = name
        self.redis_client = redis_client
        self._initialize_metrics()
        self.capabilities = {}

    async def initialize(self):
        """Initialize agent resources"""
        if not self.redis_client:
            self.redis_client = await get_redis_client()
        await self._setup_agent()
        self.capabilities = await self._discover_capabilities()

    @abstractmethod
    async def _setup_agent(self):
        """Agent-specific setup"""
        pass

    async def can_handle_task(self, task: AgentTask) -> bool:
        """Check if agent can handle a task"""
        if not task.required_capabilities:
            # If no specific capabilities required, check task type
            return task.task_type in self.capabilities
        
        # Check if agent has all required capabilities
        return all(cap in self.capabilities for cap in task.required_capabilities)

    async def get_capabilities(self) -> list[str]:
        """Get list of agent capabilities"""
        return list(self.capabilities.keys())

    async def _discover_capabilities(self) -> Dict[str, float]:
        """Discover agent capabilities"""
        capabilities = {}
        
        # Get all public methods
        for method_name in dir(self):
            if not method_name.startswith('_') and callable(getattr(self, method_name)):
                capability = method_name.replace('_', '.')
                capabilities[capability] = 1.0  # Default score
                
        return capabilities

    async def process(self, request: AgentRequest) -> AgentResponse:
        """Main processing method with monitoring and error handling"""
        start_time = datetime.utcnow()
        
        try:
            # Check cache first
            cache_key = self._generate_cache_key(request)
            cached_response = await self._get_cached_response(cache_key)
            if cached_response:
                processing_time = (datetime.utcnow() - start_time).total_seconds()
                self.metrics["cache_hits"] += 1
                self.metrics["requests_processed"] += 1
                self.metrics["average_processing_time"] = (
                    (self.metrics["average_processing_time"] * (self.metrics["requests_processed"] - 1) + processing_time) 
                    / self.metrics["requests_processed"]
                )
                return AgentResponse(
                    request_id=request.request_id,
                    status="success",
                    data=cached_response,
                    processing_time=processing_time,
                    cache_hit=True
                )

            # Process request
            config = PRIORITY_CONFIGS[request.priority]
            try:
                result = await asyncio.wait_for(
                    self._process_request(request),
                    timeout=config.timeout
                )
            except asyncio.TimeoutError:
                self.metrics["errors"] += 1
                return self._create_error_response(
                    request.request_id,
                    "Processing timeout",
                    start_time
                )

            # Cache successful response
            if result and "error" not in result:
                await self._cache_response(cache_key, result)

            processing_time = (datetime.utcnow() - start_time).total_seconds()
            self.metrics["requests_processed"] += 1
            self.metrics["average_processing_time"] = (
                (self.metrics["average_processing_time"] * (self.metrics["requests_processed"] - 1) + processing_time) 
                / self.metrics["requests_processed"]
            )

            return AgentResponse(
                request_id=request.request_id,
                status="success",
                data=result,
                processing_time=processing_time,
                cache_hit=False
            )

        except Exception as e:
            logger.error(f"Agent {self.name} error: {str(e)}", exc_info=True)
            self.metrics["errors"] += 1
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
            try:
                cached = await self.redis_client.get(cache_key)
                if cached:
                    return json.loads(cached) if isinstance(cached, str) else cached
            except Exception as e:
                logger.error(f"Cache get error: {str(e)}")
        return None

    async def _cache_response(self, cache_key: str, response: Dict[str, Any]):
        """Cache successful response"""
        if self.redis_client:
            try:
                await self.redis_client.setex(
                    cache_key,
                    PERFORMANCE_THRESHOLDS["cache_ttl"],
                    json.dumps(response)
                )
            except Exception as e:
                logger.error(f"Cache set error: {str(e)}")

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

    async def track_metric(self, metric_name: str, value: float) -> None:
        """Track a custom metric.
        
        Args:
            metric_name: Name of the metric to track
            value: Value to track
        """
        self.metrics[metric_name] = value

    async def health_check(self) -> Dict[str, Any]:
        """Check agent health"""
        if not self.redis_client:
            return {"status": "unhealthy", "reason": "No Redis client"}
        try:
            await self.redis_client.ping()
            return {"status": "healthy"}
        except Exception as e:
            logger.error(f"Agent {self.name} health check failed: {str(e)}")
            return {"status": "unhealthy", "reason": str(e)} 