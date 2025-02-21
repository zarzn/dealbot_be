import pytest
from unittest.mock import AsyncMock
from core.agents.coordinator import AgentCoordinator
from core.agents.config.agent_config import PriorityLevel
from core.services.agent import AgentService
from core.services.market_search import MarketSearchService
from core.models.enums import TaskStatus

@pytest.fixture
async def coordinator(redis_mock, async_session):
    """Fixture for coordinator testing."""
    coordinator = AgentCoordinator(redis_client=redis_mock)
    await coordinator.initialize()
    
    # Setup mock services with capabilities
    coordinator.goal_agent = AsyncMock(spec=AgentService)
    coordinator.goal_agent.capabilities = {
        "goal_analysis": 1.0,
        "goal_validation": 1.0,
        "goal_refinement": 1.0,
        "goal_tracking": 1.0,
        "market_search": 1.0
    }
    coordinator.goal_agent.can_handle_task = AsyncMock(return_value=True)
    coordinator.goal_agent.process_task = AsyncMock(return_value={"result": "test_result"})
    coordinator.goal_agent.health_check = AsyncMock(return_value=True)
    coordinator.goal_agent.analyze_goal = AsyncMock(return_value={"result": "test_result"})
    
    coordinator.market_agent = AsyncMock(spec=MarketSearchService)
    coordinator.market_agent.capabilities = {
        "market_search": 1.0,
        "deal_analysis": 1.0,
        "price_tracking": 1.0,
        "deal_validation": 1.0
    }
    coordinator.market_agent.can_handle_task = AsyncMock(return_value=True)
    coordinator.market_agent.process_task = AsyncMock(return_value={"result": "test_result"})
    coordinator.market_agent.health_check = AsyncMock(return_value=True)
    coordinator.market_agent.search_products = AsyncMock(return_value={"result": "test_result"})
    
    # Add agents to pool
    coordinator.agent_pool = {
        "goal": [coordinator.goal_agent],
        "market": [coordinator.market_agent]
    }
    
    # Set initialized flag
    coordinator.is_initialized = True
    
    return coordinator

@pytest.mark.asyncio
async def test_coordinator_initialization(coordinator):
    """Test coordinator initialization."""
    assert coordinator.redis_client is not None
    assert coordinator.agent_factory is not None
    assert coordinator.is_initialized is True
    assert coordinator.goal_agent is not None
    assert coordinator.market_agent is not None

@pytest.mark.asyncio
async def test_task_distribution(coordinator):
    """Test task distribution among agents."""
    # Create test tasks
    tasks = [
        {
            "type": "goal_analysis",
            "priority": PriorityLevel.HIGH,
            "data": {"goal_id": f"test_goal_{i}"}
        }
        for i in range(5)
    ]
    
    # Submit tasks
    task_ids = []
    for task in tasks:
        task_id = await coordinator.submit_task(task)
        task_ids.append(task_id)
        assert task_id is not None
    
    # Check task distribution
    assert len(coordinator.active_tasks) > 0
    assert all(task_id in coordinator.active_tasks for task_id in task_ids)

@pytest.mark.asyncio
async def test_agent_communication(coordinator):
    """Test communication between agents."""
    # Test goal-to-market communication
    goal_result = {
        "goal_id": "test_goal_123",
        "search_queries": ["gaming laptop RTX 3070"],
        "constraints": {"max_price": 1500}
    }
    
    market_result = {
        "matches_found": 3,
        "best_price": 1299.99,
        "deals": [{"id": "deal_1", "price": 1299.99}]
    }
    
    coordinator.goal_agent.analyze_goal = AsyncMock(return_value=goal_result)
    coordinator.market_agent.search_products = AsyncMock(return_value=market_result)
    
    result = await coordinator.process_goal_with_market_search(
        goal_id="test_goal_123"
    )
    
    assert "goal_analysis" in result
    assert "market_results" in result

@pytest.mark.asyncio
async def test_task_prioritization(coordinator):
    """Test task prioritization."""
    # Submit tasks with different priorities
    tasks = [
        {
            "type": "market_search",
            "priority": priority,
            "data": {"query": f"test_query_{i}"}
        }
        for i, priority in enumerate([
            PriorityLevel.LOW,
            PriorityLevel.MEDIUM,
            PriorityLevel.HIGH
        ])
    ]
    
    task_ids = []
    for task in tasks:
        task_id = await coordinator.submit_task(task)
        task_ids.append(task_id)
        assert task_id is not None
    
    # Check task queue
    assert len(coordinator.active_tasks) > 0
    assert all(task_id in coordinator.active_tasks for task_id in task_ids)

@pytest.mark.asyncio
async def test_error_handling(coordinator):
    """Test error handling in coordination."""
    # Test agent failure
    coordinator.goal_agent.analyze_goal = AsyncMock(side_effect=Exception("Agent failure"))
    
    # Submit task that will fail
    task = {
        "type": "goal_analysis",
        "priority": PriorityLevel.HIGH,
        "data": {"goal_id": "test_goal_fail"}
    }
    
    task_id = await coordinator.submit_task(task)
    assert task_id is not None
    
    # Check error handling
    status = await coordinator.get_task_status(task_id)
    assert status["status"] == TaskStatus.FAILED
    assert "error" in status

@pytest.mark.asyncio
async def test_performance_monitoring(coordinator):
    """Test performance monitoring."""
    # Submit test task
    task = {
        "type": "market_search",
        "priority": PriorityLevel.HIGH,
        "data": {"query": "test_query"}
    }
    
    task_id = await coordinator.submit_task(task)
    assert task_id is not None
    
    # Check metrics
    metrics = await coordinator.get_metrics()
    assert "tasks_assigned" in metrics
    assert metrics["tasks_assigned"] > 0

@pytest.mark.asyncio
async def test_state_management(coordinator):
    """Test state management."""
    # Set test state
    test_state = {
        "active_tasks": 5,
        "completed_tasks": 10,
        "failed_tasks": 2
    }
    
    await coordinator.save_state(test_state)
    loaded_state = await coordinator.load_state()
    
    assert loaded_state == test_state 