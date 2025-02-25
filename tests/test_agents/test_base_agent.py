"""Test base agent functionality."""

import pytest
from datetime import datetime
from typing import Optional, Dict, Any, Union
from uuid import uuid4
import asyncio
from collections import defaultdict

from core.agents.base.base_agent import BaseAgent, AgentRequest, AgentResponse
from core.agents.config.agent_config import PriorityLevel
from core.utils.redis import RedisClient
from tests.mocks.redis_mock import RedisMock

@pytest.fixture
async def redis_client():
    """Create Redis client fixture."""
    redis_mock = RedisMock()
    await redis_mock.auth("test_password")  # Authenticate mock
    client = RedisClient()  # Initialize without mock
    await client.init(redis_mock)  # Initialize with mock after creation
    yield client
    await client.close()

class TestAgent(BaseAgent):
    """Test agent implementation."""
    
    def __init__(self):
        """Initialize test agent."""
        super().__init__("test")
        self._error_logs = {}
        self._metrics = defaultdict(int)
        self._request = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize test agent."""
        if not self._initialized:
            await super().initialize()
            self._initialized = True
    
    async def _setup_agent(self) -> bool:
        """Set up test agent."""
        self.capabilities = {
            "test.process": 1.0,
            "test.health_check": 1.0
        }
        return True
    
    async def _process_request(self, request: AgentRequest) -> Dict[str, Any]:
        """Process a test request.
        
        Args:
            request: Request data
            
        Returns:
            Processed result
            
        Raises:
            TimeoutError: If request times out
            ValueError: If request should raise error
        """
        self._request = request  # Store the request for later use
        
        # Handle error test case
        if request.payload.get("raise_error"):
            raise ValueError("Test error case")
            
        # Handle timeout test case
        if request.payload.get("timeout"):
            await asyncio.sleep(1.0)  # Simulate long processing
            raise TimeoutError("Request processing timed out")
            
        await asyncio.sleep(0.1)  # Simulate some processing time
        return {"test": "data"}  # Return test data for basic requests
        
    async def track_metric(self, metric_name: str, value: Union[int, float]) -> None:
        """Track a metric value.
        
        Args:
            metric_name: Metric name
            value: Metric value
        """
        self._metrics[metric_name] = value
        self.metrics[metric_name] = value  # Update base metrics directly
        
    async def log_error(self, error_id: str, error_message: str) -> str:
        """Log an error.
        
        Args:
            error_id: Error ID
            error_message: Error message
            
        Returns:
            Error ID
        """
        self._error_logs[error_id] = {
            "message": error_message,
            "timestamp": datetime.utcnow()
        }
        return error_id  # Return the error ID

    async def get_error_log(self, error_id: str) -> Optional[Dict[str, Any]]:
        """Get an error log by ID.
        
        Args:
            error_id: Error ID
            
        Returns:
            Error log data
        """
        return self._error_logs.get(error_id)

    async def process_with_timeout(self, request: AgentRequest, timeout: float) -> AgentResponse:
        """Process a request with a timeout.
        
        Args:
            request: Request data
            timeout: Timeout in seconds
            
        Returns:
            Processed result or error response
        """
        try:
            async with asyncio.timeout(timeout):
                result = await self.process(request)
                if result.status == "error":
                    raise TimeoutError(result.error)
                return result
        except asyncio.TimeoutError:
            raise TimeoutError("Request processing timed out")

    async def cleanup(self) -> None:
        """Cleanup test agent resources."""
        if self.redis_client:
            await self.redis_client.close()

@pytest.fixture
async def test_agent(redis_client):
    """Create test agent instance."""
    agent = TestAgent()
    agent.redis_client = redis_client  # Use the fixture's Redis client
    await agent.initialize()
    yield agent
    await agent.cleanup()

@pytest.mark.asyncio
async def test_agent_initialization(test_agent):
    """Test agent initialization."""
    assert test_agent.name == "test"
    assert test_agent.redis_client is not None
    assert test_agent.capabilities is not None

@pytest.mark.asyncio
async def test_basic_request_processing(test_agent):
    """Test basic request processing."""
    request = AgentRequest(
        request_id=str(uuid4()),
        user_id=str(uuid4()),
        priority=PriorityLevel.MEDIUM,
        payload={"test": "data"}
    )
    response = await test_agent.process(request)
    assert response.status == "success"
    assert response.data == {"test": "data"}

@pytest.mark.asyncio
async def test_request_caching(test_agent):
    """Test request result caching."""
    request = AgentRequest(
        request_id=str(uuid4()),
        user_id=str(uuid4()),
        priority=PriorityLevel.MEDIUM,
        payload={"test": "data"}
    )
    
    # Process initial request
    response1 = await test_agent.process(request)
    assert not response1.cache_hit
    assert response1.data == {"test": "data"}
    
    # Second request - should hit cache
    response2 = await test_agent.process(request)
    assert response2.cache_hit
    assert response2.data == response1.data

@pytest.mark.asyncio
async def test_metrics_tracking(test_agent):
    """Test agent metrics tracking."""
    metric_name = "test_metric"
    metric_value = 1.0
    await test_agent.track_metric(metric_name, metric_value)
    
    # Check both the base metrics and custom metric
    metrics = await test_agent.get_metrics()
    assert metrics[metric_name] == metric_value
    assert metrics["requests_processed"] >= 0
    assert metrics["cache_hits"] >= 0
    assert metrics["errors"] >= 0
    assert metrics["average_processing_time"] >= 0

@pytest.mark.asyncio
async def test_error_handling(test_agent):
    """Test agent error handling."""
    error_message = "Test error"
    error_id = str(uuid4())
    
    # Test error logging
    returned_id = await test_agent.log_error(error_id, error_message)
    assert returned_id == error_id
    
    # Test error retrieval
    error_log = await test_agent.get_error_log(error_id)
    assert error_log is not None
    assert error_message in error_log["message"]
    assert "timestamp" in error_log
    
    # Test error in request processing
    request = AgentRequest(
        request_id=str(uuid4()),
        user_id=str(uuid4()),
        priority=PriorityLevel.LOW,
        payload={"raise_error": True}
    )
    
    response = await test_agent.process(request)
    assert response.status == "error"
    assert response.error is not None

@pytest.mark.asyncio
async def test_timeout_handling(test_agent):
    """Test request timeout handling."""
    request = AgentRequest(
        request_id=str(uuid4()),
        user_id=str(uuid4()),
        priority=PriorityLevel.LOW,
        payload={"timeout": True}
    )
    
    # Test timeout in process_with_timeout
    with pytest.raises(TimeoutError, match="Request processing timed out"):
        await test_agent.process_with_timeout(request, timeout=0.1)
    
    # Test timeout in regular processing
    response = await test_agent.process(request)
    assert response.status == "error"
    assert "timeout" in response.error.lower()

@pytest.mark.asyncio
async def test_health_check(test_agent):
    """Test agent health check."""
    health = await test_agent.health_check()
    assert health["status"] == "healthy"
    
    # Test Redis connection failure
    test_agent.redis_client = None
    health = await test_agent.health_check()
    assert health["status"] == "unhealthy"
    assert "No Redis client" in health["reason"] 