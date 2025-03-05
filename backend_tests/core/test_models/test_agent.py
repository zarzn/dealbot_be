"""Tests for the agent model."""

import pytest
import uuid
from datetime import datetime
from sqlalchemy import select

from core.models.agent import Agent, AgentType, AgentStatus
from core.models.user import User
from core.models.deal import Deal
from core.models.enums import DealStatus, MarketType, MarketCategory, MarketStatus
from core.models.market import Market

# Skip all tests in this module since the agents table doesn't exist
# pytestmark = pytest.mark.skip(reason="The agents table doesn't exist in the test database")

@pytest.mark.asyncio
@pytest.mark.core
async def test_agent_creation(db_session):
    """Test creating an agent in the database."""
    # Create a user
    user = User(
        email="agent_test@example.com",
        name="Agent Test User",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a market
    market = Market(
        name="Agent Test Market",
        type=MarketType.TEST.value.lower(),
        status=MarketStatus.ACTIVE.value.lower()
    )
    db_session.add(market)
    await db_session.commit()
    
    # Create a deal
    deal = Deal(
        title="Agent Test Deal",
        description="A deal for testing agent relationships",
        url="https://example.com/agent-test-deal",
        price=19.99,
        currency="USD",
        status=DealStatus.ACTIVE.value.lower(),
        category=MarketCategory.ELECTRONICS.value,
        user_id=user.id,
        market_id=market.id
    )
    db_session.add(deal)
    await db_session.commit()
    
    # Create an agent
    agent = Agent(
        name="Test Agent",
        agent_type=AgentType.GOAL.value,
        status=AgentStatus.ACTIVE.value,
        description="A test agent",
        user_id=user.id,
        config={"model": "gpt-4", "temperature": 0.7},
        meta_data={"created_by": "test_suite"}
    )
    db_session.add(agent)
    await db_session.commit()
    await db_session.refresh(agent)
    
    # Verify the agent was created with an ID
    assert agent.id is not None
    assert isinstance(agent.id, uuid.UUID)
    assert agent.name == "Test Agent"
    assert agent.agent_type == AgentType.GOAL.value
    assert agent.status == AgentStatus.ACTIVE.value
    assert agent.description == "A test agent"
    assert agent.user_id == user.id
    
    # Verify config and metadata
    assert agent.config["model"] == "gpt-4"
    assert agent.config["temperature"] == 0.7
    assert agent.meta_data["created_by"] == "test_suite"
    
    # Verify created_at and updated_at were set
    assert agent.created_at is not None
    assert agent.updated_at is not None
    assert isinstance(agent.created_at, datetime)
    assert isinstance(agent.updated_at, datetime)

@pytest.mark.asyncio
@pytest.mark.core
async def test_agent_relationships(db_session):
    """Test agent relationships with other models."""
    # Create a user
    user = User(
        email="agent_rel@example.com",
        name="Agent Relationship Test User",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a market
    market = Market(
        name="Agent Relationship Test Market",
        type=MarketType.TEST.value.lower(),
        status=MarketStatus.ACTIVE.value.lower()
    )
    db_session.add(market)
    await db_session.commit()
    
    # Create a deal
    deal = Deal(
        title="Agent Relationship Test Deal",
        description="A deal for testing agent relationships",
        url="https://example.com/agent-rel-test-deal",
        price=29.99,
        currency="USD",
        status=DealStatus.ACTIVE.value.lower(),
        category=MarketCategory.ELECTRONICS.value,
        user_id=user.id,
        market_id=market.id
    )
    db_session.add(deal)
    await db_session.commit()
    
    # Create an agent
    agent = Agent(
        name="Relationship Test Agent",
        agent_type=AgentType.GOAL.value,
        status=AgentStatus.ACTIVE.value,
        description="An agent for testing relationships",
        user_id=user.id,
        config={"model": "gpt-4", "temperature": 0.7},
        meta_data={"created_by": "test_suite"}
    )
    db_session.add(agent)
    await db_session.commit()
    await db_session.refresh(agent)
    
    # Verify the relationship with user
    assert agent.user_id == user.id
    
    # Test the relationship from the user side
    stmt = select(User).where(User.id == user.id)
    result = await db_session.execute(stmt)
    loaded_user = result.scalar_one()
    
    # Explicitly refresh the user to load relationships
    await db_session.refresh(loaded_user, ['agents'])
    
    # Verify the user has the agent in its relationship
    assert len(loaded_user.agents) == 1
    assert loaded_user.agents[0].id == agent.id

@pytest.mark.asyncio
@pytest.mark.core
async def test_agent_update(db_session):
    """Test updating an agent in the database."""
    # Create a user
    user = User(
        email="agent_update@example.com",
        name="Agent Update Test User",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create an agent
    agent = Agent(
        name="Update Test Agent",
        agent_type=AgentType.GOAL.value,
        status=AgentStatus.ACTIVE.value,
        description="An agent for testing updates",
        user_id=user.id,
        config={"model": "gpt-4", "temperature": 0.7},
        meta_data={"created_by": "test_suite"}
    )
    db_session.add(agent)
    await db_session.commit()
    await db_session.refresh(agent)
    
    # Update the agent
    agent.name = "Updated Agent"
    agent.description = "An updated agent description"
    agent.status = AgentStatus.BUSY.value
    agent.config = {"model": "gpt-4-turbo", "temperature": 0.5}
    agent.meta_data = {"created_by": "test_suite", "updated": True}
    
    await db_session.commit()
    await db_session.refresh(agent)
    
    # Verify the updates
    assert agent.name == "Updated Agent"
    assert agent.description == "An updated agent description"
    assert agent.status == AgentStatus.BUSY.value
    assert agent.config["model"] == "gpt-4-turbo"
    assert agent.config["temperature"] == 0.5
    assert agent.meta_data["created_by"] == "test_suite"
    assert agent.meta_data["updated"] is True
    
    # Verify updated_at was updated
    assert agent.updated_at is not None
    assert isinstance(agent.updated_at, datetime)

@pytest.mark.asyncio
@pytest.mark.core
async def test_agent_deletion(db_session):
    """Test deleting an agent from the database."""
    # Create a user
    user = User(
        email="agent_delete@example.com",
        name="Agent Delete Test User",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create an agent
    agent = Agent(
        name="Delete Test Agent",
        agent_type=AgentType.GOAL.value,
        status=AgentStatus.ACTIVE.value,
        description="An agent for testing deletion",
        user_id=user.id,
        config={"model": "gpt-4", "temperature": 0.7},
        meta_data={"created_by": "test_suite"}
    )
    db_session.add(agent)
    await db_session.commit()
    
    # Get the agent ID
    agent_id = agent.id
    
    # Delete the agent
    await db_session.delete(agent)
    await db_session.commit()
    
    # Verify the agent was deleted
    stmt = select(Agent).where(Agent.id == agent_id)
    result = await db_session.execute(stmt)
    deleted_agent = result.scalar_one_or_none()
    
    assert deleted_agent is None 