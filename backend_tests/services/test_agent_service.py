"""Tests for Agent Service.

This module contains tests for the AgentService class, which manages AI agents
for the AI Agentic Deals System.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from uuid import uuid4, UUID
from decimal import Decimal
from fastapi import BackgroundTasks

from core.services.agent import AgentService
from core.repositories.agent import AgentRepository
from core.models.agent import Agent, AgentCreate, AgentUpdate, AgentType, AgentStatus
from core.services.ai import AIService
from core.services.llm_service import LLMResponse, LLMService
from core.exceptions import (
    AgentError,
    AgentNotFoundError,
    AgentValidationError,
    AgentCreationError
)
from backend_tests.utils.markers import service_test, depends_on

pytestmark = pytest.mark.asyncio

@pytest.fixture
async def mock_agent_repository():
    """Create a mock agent repository."""
    mock_repo = AsyncMock(spec=AgentRepository)
    
    # Mock agent data
    mock_agents = [
        Agent(
            id=str(uuid4()),
            name=f"Test Agent {i}",
            type=list(AgentType)[i % len(AgentType)].value,
            role=f"Test role {i}",
            backstory=f"Test backstory {i}",
            status=AgentStatus.ACTIVE.value,
            agent_metadata={"temperature": 0.7, "max_tokens": 1000},
            created_at=datetime.now() - timedelta(days=i),
            updated_at=datetime.now()
        )
        for i in range(5)
    ]
    
    # Setup repository methods
    mock_repo.get_by_id.side_effect = lambda agent_id: next(
        (agent for agent in mock_agents if agent.id == agent_id), None
    )
    mock_repo.list.return_value = mock_agents
    mock_repo.create.side_effect = lambda agent: agent
    
    return mock_repo

@pytest.fixture
async def mock_redis_service():
    """Create a mock Redis service."""
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True
    mock_redis.delete.return_value = True
    return mock_redis

@pytest.fixture
async def mock_ai_service():
    """Create a mock AI service."""
    mock_ai = AsyncMock(spec=AIService)
    
    # Mock AI response
    mock_ai.analyze_goal.return_value = {
        "analysis": "This is a test goal analysis",
        "keywords": ["test", "goal"],
        "complexity": 0.7,
        "recommended_actions": ["search", "monitor"]
    }
    
    mock_ai.analyze_deal.return_value = {
        "score": 0.85,
        "analysis": "This is a test deal analysis",
        "price_analysis": "Good price",
        "recommendation": "Consider purchasing"
    }
    
    # We'll change this part to not rely on a missing method
    # Instead, add the method to the mock directly
    mock_ai.search_market = AsyncMock(return_value=[
        {"id": "deal1", "title": "Test Deal 1", "price": 199.99},
        {"id": "deal2", "title": "Test Deal 2", "price": 249.99}
    ])
    
    return mock_ai

@pytest.fixture
async def mock_llm_service():
    """Create a mock LLM service."""
    mock_llm = AsyncMock(spec=LLMService)
    
    # Mock LLM response
    mock_llm.generate_text.return_value = LLMResponse(
        content="This is a test LLM response",
        model="test-model",
        provider="test-provider",
        tokens_used=50
    )
    
    return mock_llm

@pytest.fixture
async def mock_db():
    """Create a mock database session."""
    return AsyncMock()

@pytest.fixture
async def agent_service(mock_db, mock_redis_service, mock_ai_service, mock_llm_service):
    """Create an agent service with mocked dependencies."""
    with patch("core.services.redis.get_redis_service") as mock_get_redis_service:
        mock_get_redis_service.return_value = mock_redis_service
        
        with patch("core.services.ai.AIService") as MockAIService:
            MockAIService.return_value = mock_ai_service
            
            with patch("core.services.llm_service.LLMService") as MockLLMService:
                MockLLMService.return_value = mock_llm_service
                
                service = AgentService(db=mock_db)
                # Make sure to set the mock AI service explicitly
                service.ai_service = mock_ai_service
                yield service

@service_test
async def test_create_goal_analyst(agent_service):
    """Test creating a goal analyst agent."""
    # Prepare test data
    user_id = UUID(str(uuid4()))
    goal_id = UUID(str(uuid4()))
    
    # Mock repository create method
    with patch.object(agent_service.repository, "create") as mock_create:
        mock_create.return_value = Agent(
            id=str(uuid4()),
            user_id=user_id,
            goal_id=goal_id,
            agent_type=AgentType.GOAL_ANALYST.value,
            name="Goal Analyst",
            description="Analyze and understand user goals",
            meta_data={"specialization": "goal_analysis", "backstory": "I am an AI agent specialized in understanding and analyzing user goals."},
            status=AgentStatus.ACTIVE.value,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # Call service method
        agent = await agent_service.create_goal_analyst(user_id, goal_id)
        
        # Verify result
        assert agent.name == "Goal Analyst"
        assert agent.agent_type == AgentType.GOAL_ANALYST.value
        assert agent.user_id == user_id
        assert agent.goal_id == goal_id
        
        # Verify repository was called
        mock_create.assert_called_once()

@service_test
async def test_analyze_goal(agent_service, mock_ai_service):
    """Test goal analysis using the AI service."""
    # Prepare test data
    goal_data = {
        "id": str(uuid4()),
        "title": "Test Goal",
        "description": "This is a test goal",
        "criteria": {
            "price_range": {"min": 100, "max": 500},
            "keywords": ["test", "product"],
        },
        "priority": 1,
        "deadline": datetime.now() + timedelta(days=30)
    }
    
    # Call service method
    result = await agent_service.analyze_goal(goal_data)
    
    # Verify AI service was called
    mock_ai_service.analyze_goal.assert_called_once_with(goal_data)
    
    # Verify result
    assert "analysis" in result
    assert "keywords" in result
    assert "complexity" in result
    assert "recommended_actions" in result

@service_test
async def test_analyze_deal(agent_service, mock_ai_service):
    """Test deal analysis using the AI service."""
    # Prepare test data
    deal_id = UUID(str(uuid4()))
    
    # Call service method
    result = await agent_service.analyze_deal(deal_id)
    
    # Verify AI service was called
    mock_ai_service.analyze_deal.assert_called_once_with(deal_id)
    
    # Verify result
    assert "score" in result
    assert "analysis" in result
    assert "price_analysis" in result
    assert "recommendation" in result

@service_test
async def test_search_market(agent_service, mock_ai_service):
    """Test market search query generation."""
    # Prepare test data
    market_id = UUID(str(uuid4()))
    search_params = {
        "price_range": {"min": 100, "max": 500},
        "keywords": ["test", "product"],
    }
    
    # Call service method
    result = await agent_service.search_market(market_id, search_params)
    
    # Verify result is a list
    assert isinstance(result, list)

@service_test
async def test_llm_integration(agent_service, mock_llm_service):
    """Test LLM integration in the agent service."""
    # Prepare test data
    prompt = "Generate a product description for test item."
    
    # Call underlying LLM service through agent_service
    with patch.object(agent_service, "_get_llm_service", return_value=mock_llm_service):
        result = await agent_service.generate_text(prompt)
    
    # Verify LLM service was called
    mock_llm_service.generate_text.assert_called_once_with(prompt)
    
    # Verify result
    assert result is not None
    assert "This is a test LLM response" in result 