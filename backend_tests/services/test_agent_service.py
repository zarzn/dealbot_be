"""Tests for Agent Service.

This module contains tests for the AgentService class, which manages AI agents
for the AI Agentic Deals System.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from uuid import uuid4
from decimal import Decimal

from core.services.agent import AgentService
from core.repositories.agent import AgentRepository
from core.models.agent import Agent, AgentCreate, AgentUpdate, AgentType, AgentStatus
from core.exceptions import (
    AgentError,
    AgentNotFoundError,
    AgentValidationError,
    AgentCreationError
)
from utils.markers import service_test, depends_on

pytestmark = pytest.mark.asyncio

@pytest.fixture
async def mock_agent_repository():
    """Create a mock agent repository."""
    mock_repo = AsyncMock(spec=AgentRepository)
    
    # Set up default behaviors
    mock_repo.create.side_effect = lambda obj: obj
    mock_repo.get.return_value = None
    mock_repo.update.side_effect = lambda obj: obj
    mock_repo.delete.return_value = True
    
    return mock_repo

@pytest.fixture
async def mock_redis_service():
    """Create a mock Redis service."""
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True
    mock_redis.ping.return_value = True
    mock_redis.delete.return_value = True
    mock_redis.exists.return_value = False
    return mock_redis

@pytest.fixture
async def agent_service(mock_agent_repository, mock_redis_service):
    """Create an agent service with mock dependencies."""
    async def mock_get_redis_service():
        return mock_redis_service
        
    with patch("core.services.agent.get_redis_service", side_effect=mock_get_redis_service):
        service = AgentService(AsyncMock())
        service.repository = mock_agent_repository
        yield service

@service_test
async def test_create_goal_analyst(agent_service, mock_agent_repository):
    """Test creating a goal analyst agent."""
    # Setup
    user_id = uuid4()
    goal_id = uuid4()
    
    # Mock repository to return a valid agent
    mock_agent = MagicMock(spec=Agent)
    mock_agent.id = uuid4()
    mock_agent.user_id = user_id
    mock_agent.goal_id = goal_id
    mock_agent.type = AgentType.GOAL_ANALYST
    mock_agent.status = AgentStatus.INITIALIZED
    mock_agent_repository.create.return_value = mock_agent
    
    # Execute
    result = await agent_service.create_goal_analyst(user_id, goal_id)
    
    # Verify
    assert result is mock_agent
    assert result.user_id == user_id
    assert result.goal_id == goal_id
    assert result.type == AgentType.GOAL_ANALYST
    
    # Verify repository was called with correct parameters
    mock_agent_repository.create.assert_called_once()
    create_call = mock_agent_repository.create.call_args[0][0]
    assert create_call.user_id == user_id
    assert create_call.goal_id == goal_id
    assert create_call.type == AgentType.GOAL_ANALYST

@service_test
async def test_create_deal_finder(agent_service, mock_agent_repository):
    """Test creating a deal finder agent."""
    # Setup
    user_id = uuid4()
    goal_id = uuid4()
    
    # Mock repository to return a valid agent
    mock_agent = MagicMock(spec=Agent)
    mock_agent.id = uuid4()
    mock_agent.user_id = user_id
    mock_agent.goal_id = goal_id
    mock_agent.type = AgentType.DEAL_FINDER
    mock_agent.status = AgentStatus.INITIALIZED
    mock_agent_repository.create.return_value = mock_agent
    
    # Execute
    result = await agent_service.create_deal_finder(user_id, goal_id)
    
    # Verify
    assert result is mock_agent
    assert result.user_id == user_id
    assert result.goal_id == goal_id
    assert result.type == AgentType.DEAL_FINDER
    
    # Verify repository was called with correct parameters
    mock_agent_repository.create.assert_called_once()
    create_call = mock_agent_repository.create.call_args[0][0]
    assert create_call.user_id == user_id
    assert create_call.goal_id == goal_id
    assert create_call.type == AgentType.DEAL_FINDER

@service_test
async def test_create_price_analyst(agent_service, mock_agent_repository):
    """Test creating a price analyst agent."""
    # Setup
    user_id = uuid4()
    goal_id = uuid4()
    
    # Mock repository to return a valid agent
    mock_agent = MagicMock(spec=Agent)
    mock_agent.id = uuid4()
    mock_agent.user_id = user_id
    mock_agent.goal_id = goal_id
    mock_agent.type = AgentType.PRICE_ANALYST
    mock_agent.status = AgentStatus.INITIALIZED
    mock_agent_repository.create.return_value = mock_agent
    
    # Execute
    result = await agent_service.create_price_analyst(user_id, goal_id)
    
    # Verify
    assert result is mock_agent
    assert result.user_id == user_id
    assert result.goal_id == goal_id
    assert result.type == AgentType.PRICE_ANALYST

@service_test
async def test_create_notifier(agent_service, mock_agent_repository):
    """Test creating a notifier agent."""
    # Setup
    user_id = uuid4()
    goal_id = uuid4()
    
    # Mock repository to return a valid agent
    mock_agent = MagicMock(spec=Agent)
    mock_agent.id = uuid4()
    mock_agent.user_id = user_id
    mock_agent.goal_id = goal_id
    mock_agent.type = AgentType.NOTIFIER
    mock_agent.status = AgentStatus.INITIALIZED
    mock_agent_repository.create.return_value = mock_agent
    
    # Execute
    result = await agent_service.create_notifier(user_id, goal_id)
    
    # Verify
    assert result is mock_agent
    assert result.user_id == user_id
    assert result.goal_id == goal_id
    assert result.type == AgentType.NOTIFIER

@service_test
async def test_process_goal(agent_service):
    """Test processing a goal with agents."""
    # Setup
    goal_id = uuid4()
    
    # Mock agent creation methods
    agent_service.create_goal_analyst = AsyncMock()
    agent_service.create_deal_finder = AsyncMock()
    agent_service.create_price_analyst = AsyncMock()
    agent_service.create_notifier = AsyncMock()
    
    # Mock background tasks
    mock_background_tasks = MagicMock()
    agent_service._background_tasks = mock_background_tasks
    
    # Execute
    await agent_service.process_goal(goal_id)
    
    # Verify agent creation methods were called
    agent_service.create_goal_analyst.assert_called_once()
    agent_service.create_deal_finder.assert_called_once()
    agent_service.create_price_analyst.assert_called_once()
    agent_service.create_notifier.assert_called_once()
    
    # Verify background task was added
    mock_background_tasks.add_task.assert_called_once()

@service_test
async def test_process_goal_no_background_tasks(agent_service):
    """Test processing a goal without background tasks."""
    # Setup
    goal_id = uuid4()
    
    # Mock agent creation methods
    agent_service.create_goal_analyst = AsyncMock()
    agent_service.create_deal_finder = AsyncMock()
    agent_service.create_price_analyst = AsyncMock()
    agent_service.create_notifier = AsyncMock()
    
    # Mock _process_goal_async method
    agent_service._process_goal_async = AsyncMock()
    
    # Set background tasks to None
    agent_service._background_tasks = None
    
    # Execute
    await agent_service.process_goal(goal_id)
    
    # Verify _process_goal_async was called directly
    agent_service._process_goal_async.assert_called_once()

@service_test
async def test_add_background_task(agent_service):
    """Test adding a background task."""
    # Setup
    mock_task = AsyncMock()
    task_arg = "test_arg"
    task_kwarg = "test_kwarg"
    
    # Mock background tasks
    mock_background_tasks = MagicMock()
    agent_service._background_tasks = mock_background_tasks
    
    # Execute
    agent_service.add_background_task(mock_task, task_arg, kwarg=task_kwarg)
    
    # Verify
    mock_background_tasks.add_task.assert_called_once_with(mock_task, task_arg, kwarg=task_kwarg)

@service_test
async def test_add_background_task_no_tasks_object(agent_service):
    """Test adding a background task when no background tasks object exists."""
    # Setup
    mock_task = AsyncMock()
    
    # Set background tasks to None
    agent_service._background_tasks = None
    
    # Execute
    # Should not raise an exception
    agent_service.add_background_task(mock_task)
    
    # No assertion needed - just verifying it doesn't crash

@service_test
async def test_process_task(agent_service):
    """Test processing a generic task."""
    # Setup
    task = {
        "type": "analyze_goal",
        "goal_id": str(uuid4()),
        "user_id": str(uuid4())
    }
    
    # Mock analyze_goal method
    expected_result = {"status": "success", "data": {"score": 85}}
    agent_service.analyze_goal = AsyncMock(return_value=expected_result)
    
    # Execute
    result = await agent_service.process_task(task)
    
    # Verify
    assert result == expected_result
    agent_service.analyze_goal.assert_called_once_with(task)

@service_test
async def test_process_task_unsupported_type(agent_service):
    """Test processing an unsupported task type."""
    # Setup
    task = {
        "type": "unsupported_task_type",
        "data": {"key": "value"}
    }
    
    # Execute
    result = await agent_service.process_task(task)
    
    # Verify
    assert "error" in result
    assert "Unsupported task type" in result["error"]

@service_test
async def test_can_handle_task(agent_service):
    """Test checking if the service can handle a task."""
    # Setup - mock get_capabilities
    agent_service.get_capabilities = AsyncMock(return_value=[
        "analyze_goal",
        "analyze_deal",
        "search_market"
    ])
    
    # Execute
    can_handle_1 = await agent_service.can_handle_task({"type": "analyze_goal"})
    can_handle_2 = await agent_service.can_handle_task({"type": "unsupported_task"})
    
    # Verify
    assert can_handle_1 is True
    assert can_handle_2 is False

@service_test
async def test_get_capabilities(agent_service):
    """Test getting service capabilities."""
    # Execute
    capabilities = await agent_service.get_capabilities()
    
    # Verify
    assert isinstance(capabilities, list)
    assert "analyze_goal" in capabilities
    assert "analyze_deal" in capabilities
    assert "search_market" in capabilities
    assert "predict_price" in capabilities
    assert "find_matches" in capabilities
    assert "validate_deal" in capabilities
    assert "generate_notification" in capabilities

@service_test
async def test_health_check(agent_service, mock_redis_service):
    """Test service health check."""
    # Execute
    is_healthy = await agent_service.health_check()
    
    # Verify
    assert is_healthy is True

@service_test
@patch("core.services.agent.logger")
async def test_analyze_goal(agent_service, mock_logger):
    """Test analyzing a goal."""
    # Setup
    goal_data = {
        "goal_id": str(uuid4()),
        "user_id": str(uuid4()),
        "title": "Test Goal",
        "description": "A test goal for analysis",
        "criteria": ["Low risk", "High returns"],
        "preferences": {"risk_tolerance": "medium"}
    }
    
    # Execute
    result = await agent_service.analyze_goal(goal_data)
    
    # Verify
    assert "analysis" in result
    assert "score" in result
    assert isinstance(result["score"], (int, float))
    assert 0 <= result["score"] <= 100
    assert "recommendations" in result
    assert isinstance(result["recommendations"], list)
    mock_logger.info.assert_called()

@service_test
async def test_analyze_deal(agent_service, mock_agent_repository):
    """Test analyzing a deal."""
    # Setup
    deal_id = uuid4()
    
    # Mock repository to return deal details
    mock_agent_repository.get_deal.return_value = {
        "id": str(deal_id),
        "title": "Test Deal",
        "price": 100.0,
        "market_cap": 1000000.0,
        "volume": 5000.0,
        "features": ["feature1", "feature2"]
    }
    
    # Execute
    result = await agent_service.analyze_deal(deal_id)
    
    # Verify
    assert "analysis" in result
    assert "score" in result
    assert isinstance(result["score"], (int, float))
    assert 0 <= result["score"] <= 100
    assert "risk_assessment" in result
    assert "recommendation" in result

@service_test
async def test_search_market(agent_service):
    """Test searching a market."""
    # Setup
    market_id = uuid4()
    search_params = {
        "query": "test product",
        "min_price": 50,
        "max_price": 200,
        "category": "electronics"
    }
    
    # Execute
    results = await agent_service.search_market(market_id, search_params)
    
    # Verify
    assert isinstance(results, list)
    assert len(results) > 0
    
    # Check all results contain required fields
    for result in results:
        assert "id" in result
        assert "title" in result
        assert "price" in result
        assert "url" in result
        assert "score" in result

@service_test
async def test_predict_price(agent_service):
    """Test predicting price for a deal."""
    # Setup
    deal_id = uuid4()
    days = 7
    
    # Execute
    result = await agent_service.predict_price(deal_id, days)
    
    # Verify
    assert "current_price" in result
    assert "predicted_price" in result
    assert "confidence" in result
    assert 0 <= result["confidence"] <= 1
    assert "prediction_date" in result
    assert "price_history" in result
    assert isinstance(result["price_history"], list)
    assert "trend_direction" in result
    assert result["trend_direction"] in ["up", "down", "stable"]

@service_test
async def test_find_matches(agent_service, mock_agent_repository):
    """Test finding matches for a goal."""
    # Setup
    goal_id = uuid4()
    
    # Mock repository to return goal details
    mock_agent_repository.get_goal.return_value = {
        "id": str(goal_id),
        "title": "Test Goal",
        "description": "A test goal for matching",
        "criteria": ["feature1", "feature2"],
        "preferences": {"min_score": 70}
    }
    
    # Mock repository to return deal matches
    mock_deals = [
        {
            "id": str(uuid4()),
            "title": "Match Deal 1",
            "match_score": 85,
            "price": 110.5,
            "features": ["feature1", "feature2"]
        },
        {
            "id": str(uuid4()),
            "title": "Match Deal 2",
            "match_score": 75,
            "price": 99.99,
            "features": ["feature1", "feature3"]
        }
    ]
    mock_agent_repository.find_matching_deals.return_value = mock_deals
    
    # Execute
    matches = await agent_service.find_matches(goal_id)
    
    # Verify
    assert isinstance(matches, list)
    assert len(matches) == 2
    
    # Deals should be sorted by match score
    assert matches[0]["match_score"] >= matches[1]["match_score"]
    
    # All matches should have analysis
    for match in matches:
        assert "id" in match
        assert "title" in match
        assert "match_score" in match
        assert "analysis" in match

@service_test
async def test_validate_deal(agent_service):
    """Test validating a deal."""
    # Setup
    deal_id = uuid4()
    
    # Execute
    result = await agent_service.validate_deal(deal_id)
    
    # Verify
    assert "is_valid" in result
    assert isinstance(result["is_valid"], bool)
    assert "validation_score" in result
    assert 0 <= result["validation_score"] <= 100
    assert "issues" in result
    assert isinstance(result["issues"], list)
    assert "recommendations" in result
    assert isinstance(result["recommendations"], list)

@service_test
async def test_generate_notification(agent_service):
    """Test generating a notification."""
    # Setup
    user_id = uuid4()
    goal_id = uuid4()
    deal_id = uuid4()
    event_type = "price_drop"
    
    # Execute
    result = await agent_service.generate_notification(user_id, goal_id, deal_id, event_type)
    
    # Verify
    assert "message" in result
    assert "priority" in result
    assert "action_url" in result
    assert "timestamp" in result
    assert isinstance(result["timestamp"], str)
    assert "id" in result
    assert "meta" in result
    
    # Verify specific event type
    assert event_type in result["message"].lower()

@service_test
async def test_initialize(agent_service, mock_redis_service):
    """Test service initialization."""
    # Execute
    await agent_service.initialize()
    
    # Verify Redis service is initialized
    assert agent_service.redis is mock_redis_service 