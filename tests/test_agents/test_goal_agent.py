"""Tests for goal agent functionality."""

# Standard library imports
import pytest
from unittest.mock import patch, AsyncMock
from typing import Dict, Any
from datetime import datetime

# Core imports
from core.services.agent import AgentService
from core.agents.config.agent_config import PriorityLevel, LLMProvider
from core.models.goal import Goal
from core.models.goal_types import GoalType
from core.models.enums import GoalStatus, GoalPriority

# Test imports
from tests.mocks.redis_mock import AsyncRedisMock

@pytest.fixture
def mock_goal_data():
    """Mock goal data."""
    return {
        "id": "test_goal_123",
        "user_id": "test_user_123",
        "title": "Find gaming laptop deals",
        "item_category": "ELECTRONICS",
        "constraints": {
            "max_price": 1500,
            "min_price": 800,
            "brands": ["Lenovo", "ASUS", "MSI"],
            "conditions": ["new", "refurbished"],
            "keywords": ["gaming laptop", "RTX 3070", "16GB RAM"]
        },
        "status": GoalStatus.ACTIVE,
        "priority": GoalPriority.MEDIUM,
        "created_at": datetime.utcnow(),
        "deadline": None
    }

@pytest.fixture
def agent_service(async_session):
    """Fixture for agent service."""
    return AgentService(db=async_session)

@pytest.mark.asyncio
async def test_goal_analysis(agent_service, mock_goal_data):
    """Test goal analysis functionality."""
    with patch('core.agents.utils.llm_manager.LLMManager.generate_response',
              new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {
            "analysis": {
                "keywords": ["gaming laptop", "RTX 3070", "under $1500"],
                "search_queries": [
                    "gaming laptop RTX 3070",
                    "MSI gaming laptop RTX 3070",
                    "ASUS gaming laptop RTX 3070"
                ],
                "priority_features": ["GPU", "Price", "Brand"],
                "confidence": 0.95
            }
        }
        
        goal = Goal(**mock_goal_data)
        goal_analyst = await agent_service.create_goal_analyst(
            user_id=goal.user_id,
            goal_id=goal.id
        )
        
        analysis = await agent_service._analyze_goal(goal_analyst)
        
        assert "keywords" in analysis
        assert "search_queries" in analysis
        assert "confidence" in analysis
        assert analysis["confidence"] > 0.9
        mock_llm.assert_called_once()

@pytest.mark.asyncio
async def test_goal_validation(agent_service, mock_goal_data):
    """Test goal validation."""
    # Test valid goal
    valid_goal = Goal(**mock_goal_data)
    goal_analyst = await agent_service.create_goal_analyst(
        user_id=valid_goal.user_id,
        goal_id=valid_goal.id
    )
    
    validation = await agent_service._analyze_goal(goal_analyst)
    assert validation["is_valid"]
    assert validation["confidence"] > 0.8
    
    # Test invalid goal (missing required constraints)
    invalid_data = mock_goal_data.copy()
    invalid_data["constraints"] = {}
    invalid_goal = Goal(**invalid_data)
    goal_analyst = await agent_service.create_goal_analyst(
        user_id=invalid_goal.user_id,
        goal_id=invalid_goal.id
    )
    
    validation = await agent_service._analyze_goal(goal_analyst)
    assert not validation["is_valid"]
    assert "missing constraints" in validation["reasons"]

@pytest.mark.asyncio
async def test_goal_refinement(agent_service, mock_goal_data):
    """Test goal refinement functionality."""
    with patch('core.agents.utils.llm_manager.LLMManager.generate_response',
              new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {
            "refined_goal": {
                "additional_keywords": ["gaming", "laptop", "nvidia"],
                "excluded_terms": ["desktop", "console"],
                "price_range": {
                    "min": 800,
                    "max": 1500
                },
                "confidence": 0.9
            }
        }
        
        refinement = await agent_service.refine_goal(Goal(**mock_goal_data))
        
        assert "additional_keywords" in refinement
        assert "price_range" in refinement
        assert refinement["confidence"] > 0.8
        mock_llm.assert_called_once()

@pytest.mark.asyncio
async def test_goal_progress_tracking(agent_service, mock_goal_data):
    """Test goal progress tracking."""
    goal = Goal(**mock_goal_data)
    
    # Simulate progress updates
    updates = [
        {"matches_found": 5, "best_price": 1400},
        {"matches_found": 8, "best_price": 1350},
        {"matches_found": 12, "best_price": 1299}
    ]
    
    for update in updates:
        await agent_service.update_goal_progress(goal, update)
    
    progress = await agent_service.get_goal_progress(goal)
    assert progress["total_matches"] == 12
    assert progress["best_price"] == 1299
    assert progress["price_trend"] == "decreasing"

@pytest.mark.asyncio
async def test_goal_completion_check(agent_service, mock_goal_data):
    """Test goal completion checking."""
    goal = Goal(**mock_goal_data)
    goal_analyst = await agent_service.create_goal_analyst(
        user_id=goal.user_id,
        goal_id=goal.id
    )
    
    # Test not completed (price above target)
    completion = await agent_service._analyze_goal(goal_analyst)
    assert not completion["is_completed"]
    
    # Test completed (found matching deal)
    completion = await agent_service._analyze_goal(goal_analyst)
    assert completion["is_completed"]
    assert completion["reason"] == "price_target_met"

@pytest.mark.asyncio
async def test_goal_priority_adjustment(agent_service, mock_goal_data):
    """Test goal priority adjustment."""
    goal = Goal(**mock_goal_data)
    
    # Test priority increase (deadline approaching)
    adjusted = await agent_service.adjust_goal_priority(
        goal,
        {"days_remaining": 2}
    )
    assert adjusted["new_priority"] == PriorityLevel.HIGH
    
    # Test priority decrease (many matches found)
    adjusted = await agent_service.adjust_goal_priority(
        goal,
        {"matches_found": 50}
    )
    assert adjusted["new_priority"] == PriorityLevel.LOW

@pytest.mark.asyncio
async def test_goal_notification_generation(agent_service, mock_goal_data):
    """Test notification generation for goals."""
    goal = Goal(**mock_goal_data)
    
    # Test deal found notification
    notification = await agent_service.generate_goal_notification(
        goal,
        {
            "type": "deal_found",
            "price": 1299,
            "url": "https://example.com/deal"
        }
    )
    assert "deal found" in notification["message"].lower()
    assert notification["priority"] == "high"
    
    # Test progress update notification
    notification = await agent_service.generate_goal_notification(
        goal,
        {
            "type": "progress_update",
            "matches_found": 25
        }
    )
    assert "matches found" in notification["message"].lower()
    assert notification["priority"] == "medium" 