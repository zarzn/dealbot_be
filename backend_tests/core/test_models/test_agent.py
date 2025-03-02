"""Tests for the agent model."""

import pytest
import uuid
from datetime import datetime
from sqlalchemy import select

from core.models.agent import Agent, AgentType, AgentStatus
from core.models.user import User
from core.models.deal import Deal
from core.models.enums import DealStatus, MarketType

@pytest.mark.asyncio
@pytest.mark.core
async def test_agent_creation(db_session):
    """Test creating an agent in the database."""
    # Create a user
    user = User(
        email="agent_test@example.com",
        username="agentuser",
        full_name="Agent Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a deal
    deal = Deal(
        title="Agent Test Deal",
        description="A deal for testing agent model",
        status=DealStatus.DRAFT.value.lower(),
        market_type=MarketType.CRYPTO.value.lower(),
        user_id=user.id,
        metadata={"test": True}
    )
    db_session.add(deal)
    await db_session.commit()
    
    # Create an agent
    agent = Agent(
        name="Test Agent",
        type=AgentType.MARKET_ANALYST.value.lower(),
        status=AgentStatus.ACTIVE.value.lower(),
        user_id=user.id,
        deal_id=deal.id,
        configuration={
            "model": "gpt-4",
            "temperature": 0.7,
            "max_tokens": 1000
        },
        metadata={
            "specialty": "cryptocurrency",
            "experience_level": "expert"
        }
    )
    
    # Add to session and commit
    db_session.add(agent)
    await db_session.commit()
    await db_session.refresh(agent)
    
    # Verify the agent was created with an ID
    assert agent.id is not None
    assert isinstance(agent.id, uuid.UUID)
    assert agent.name == "Test Agent"
    assert agent.type == AgentType.MARKET_ANALYST.value.lower()
    assert agent.status == AgentStatus.ACTIVE.value.lower()
    assert agent.user_id == user.id
    assert agent.deal_id == deal.id
    
    # Verify configuration and metadata
    assert agent.configuration["model"] == "gpt-4"
    assert agent.configuration["temperature"] == 0.7
    assert agent.configuration["max_tokens"] == 1000
    assert agent.metadata["specialty"] == "cryptocurrency"
    assert agent.metadata["experience_level"] == "expert"
    
    # Verify created_at and updated_at were set
    assert agent.created_at is not None
    assert agent.updated_at is not None
    assert isinstance(agent.created_at, datetime)
    assert isinstance(agent.updated_at, datetime)

@pytest.mark.asyncio
@pytest.mark.core
async def test_agent_relationships(db_session):
    """Test agent relationships with user and deal."""
    # Create a user
    user = User(
        email="agent_rel_test@example.com",
        username="agentreluser",
        full_name="Agent Relationship Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a deal
    deal = Deal(
        title="Agent Relationship Test Deal",
        description="A deal for testing agent relationships",
        status=DealStatus.DRAFT.value.lower(),
        market_type=MarketType.CRYPTO.value.lower(),
        user_id=user.id,
        metadata={"test": True}
    )
    db_session.add(deal)
    await db_session.commit()
    
    # Create an agent
    agent = Agent(
        name="Relationship Test Agent",
        type=AgentType.DEAL_NEGOTIATOR.value.lower(),
        status=AgentStatus.ACTIVE.value.lower(),
        user_id=user.id,
        deal_id=deal.id,
        configuration={"model": "gpt-4"},
        metadata={"test": True}
    )
    db_session.add(agent)
    await db_session.commit()
    
    # Query the agent with relationships
    stmt = select(Agent).where(Agent.id == agent.id)
    result = await db_session.execute(stmt)
    loaded_agent = result.scalar_one()
    
    # Verify relationships
    assert loaded_agent.id == agent.id
    assert loaded_agent.user_id == user.id
    assert loaded_agent.deal_id == deal.id

@pytest.mark.asyncio
@pytest.mark.core
async def test_agent_update(db_session):
    """Test updating an agent."""
    # Create a user
    user = User(
        email="agent_update@example.com",
        username="agentupdateuser",
        full_name="Agent Update Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a deal
    deal = Deal(
        title="Agent Update Test Deal",
        description="A deal for testing agent updates",
        status=DealStatus.DRAFT.value.lower(),
        market_type=MarketType.CRYPTO.value.lower(),
        user_id=user.id,
        metadata={"test": True}
    )
    db_session.add(deal)
    await db_session.commit()
    
    # Create an agent
    agent = Agent(
        name="Update Test Agent",
        type=AgentType.RISK_ASSESSOR.value.lower(),
        status=AgentStatus.ACTIVE.value.lower(),
        user_id=user.id,
        deal_id=deal.id,
        configuration={"model": "gpt-4", "temperature": 0.7},
        metadata={"specialty": "risk analysis"}
    )
    db_session.add(agent)
    await db_session.commit()
    
    # Update the agent
    agent.name = "Updated Agent Name"
    agent.status = AgentStatus.PAUSED.value.lower()
    agent.configuration["temperature"] = 0.5
    agent.configuration["max_tokens"] = 2000
    agent.metadata["specialty"] = "advanced risk analysis"
    agent.metadata["priority"] = "high"
    
    await db_session.commit()
    await db_session.refresh(agent)
    
    # Verify the updates
    assert agent.name == "Updated Agent Name"
    assert agent.status == AgentStatus.PAUSED.value.lower()
    assert agent.configuration["temperature"] == 0.5
    assert agent.configuration["max_tokens"] == 2000
    assert agent.metadata["specialty"] == "advanced risk analysis"
    assert agent.metadata["priority"] == "high"
    
    # Verify updated_at was updated
    assert agent.updated_at is not None

@pytest.mark.asyncio
@pytest.mark.core
async def test_agent_deletion(db_session):
    """Test deleting an agent."""
    # Create a user
    user = User(
        email="agent_delete@example.com",
        username="agentdeleteuser",
        full_name="Agent Delete Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a deal
    deal = Deal(
        title="Agent Delete Test Deal",
        description="A deal for testing agent deletion",
        status=DealStatus.DRAFT.value.lower(),
        market_type=MarketType.CRYPTO.value.lower(),
        user_id=user.id,
        metadata={"test": True}
    )
    db_session.add(deal)
    await db_session.commit()
    
    # Create an agent
    agent = Agent(
        name="Delete Test Agent",
        type=AgentType.MARKET_ANALYST.value.lower(),
        status=AgentStatus.ACTIVE.value.lower(),
        user_id=user.id,
        deal_id=deal.id,
        configuration={"model": "gpt-4"},
        metadata={"test": True}
    )
    db_session.add(agent)
    await db_session.commit()
    
    # Get the agent ID
    agent_id = agent.id
    
    # Delete the agent
    await db_session.delete(agent)
    await db_session.commit()
    
    # Try to find the deleted agent
    stmt = select(Agent).where(Agent.id == agent_id)
    result = await db_session.execute(stmt)
    deleted_agent = result.scalar_one_or_none()
    
    # Verify the agent was deleted
    assert deleted_agent is None 

import pytest
import uuid
from datetime import datetime
from sqlalchemy import select

from core.models.agent import Agent, AgentType, AgentStatus
from core.models.user import User
from core.models.deal import Deal
from core.models.enums import DealStatus, MarketType

@pytest.mark.asyncio
@pytest.mark.core
async def test_agent_creation(db_session):
    """Test creating an agent in the database."""
    # Create a user
    user = User(
        email="agent_test@example.com",
        username="agentuser",
        full_name="Agent Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a deal
    deal = Deal(
        title="Agent Test Deal",
        description="A deal for testing agent model",
        status=DealStatus.DRAFT.value.lower(),
        market_type=MarketType.CRYPTO.value.lower(),
        user_id=user.id,
        metadata={"test": True}
    )
    db_session.add(deal)
    await db_session.commit()
    
    # Create an agent
    agent = Agent(
        name="Test Agent",
        type=AgentType.MARKET_ANALYST.value.lower(),
        status=AgentStatus.ACTIVE.value.lower(),
        user_id=user.id,
        deal_id=deal.id,
        configuration={
            "model": "gpt-4",
            "temperature": 0.7,
            "max_tokens": 1000
        },
        metadata={
            "specialty": "cryptocurrency",
            "experience_level": "expert"
        }
    )
    
    # Add to session and commit
    db_session.add(agent)
    await db_session.commit()
    await db_session.refresh(agent)
    
    # Verify the agent was created with an ID
    assert agent.id is not None
    assert isinstance(agent.id, uuid.UUID)
    assert agent.name == "Test Agent"
    assert agent.type == AgentType.MARKET_ANALYST.value.lower()
    assert agent.status == AgentStatus.ACTIVE.value.lower()
    assert agent.user_id == user.id
    assert agent.deal_id == deal.id
    
    # Verify configuration and metadata
    assert agent.configuration["model"] == "gpt-4"
    assert agent.configuration["temperature"] == 0.7
    assert agent.configuration["max_tokens"] == 1000
    assert agent.metadata["specialty"] == "cryptocurrency"
    assert agent.metadata["experience_level"] == "expert"
    
    # Verify created_at and updated_at were set
    assert agent.created_at is not None
    assert agent.updated_at is not None
    assert isinstance(agent.created_at, datetime)
    assert isinstance(agent.updated_at, datetime)

@pytest.mark.asyncio
@pytest.mark.core
async def test_agent_relationships(db_session):
    """Test agent relationships with user and deal."""
    # Create a user
    user = User(
        email="agent_rel_test@example.com",
        username="agentreluser",
        full_name="Agent Relationship Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a deal
    deal = Deal(
        title="Agent Relationship Test Deal",
        description="A deal for testing agent relationships",
        status=DealStatus.DRAFT.value.lower(),
        market_type=MarketType.CRYPTO.value.lower(),
        user_id=user.id,
        metadata={"test": True}
    )
    db_session.add(deal)
    await db_session.commit()
    
    # Create an agent
    agent = Agent(
        name="Relationship Test Agent",
        type=AgentType.DEAL_NEGOTIATOR.value.lower(),
        status=AgentStatus.ACTIVE.value.lower(),
        user_id=user.id,
        deal_id=deal.id,
        configuration={"model": "gpt-4"},
        metadata={"test": True}
    )
    db_session.add(agent)
    await db_session.commit()
    
    # Query the agent with relationships
    stmt = select(Agent).where(Agent.id == agent.id)
    result = await db_session.execute(stmt)
    loaded_agent = result.scalar_one()
    
    # Verify relationships
    assert loaded_agent.id == agent.id
    assert loaded_agent.user_id == user.id
    assert loaded_agent.deal_id == deal.id

@pytest.mark.asyncio
@pytest.mark.core
async def test_agent_update(db_session):
    """Test updating an agent."""
    # Create a user
    user = User(
        email="agent_update@example.com",
        username="agentupdateuser",
        full_name="Agent Update Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a deal
    deal = Deal(
        title="Agent Update Test Deal",
        description="A deal for testing agent updates",
        status=DealStatus.DRAFT.value.lower(),
        market_type=MarketType.CRYPTO.value.lower(),
        user_id=user.id,
        metadata={"test": True}
    )
    db_session.add(deal)
    await db_session.commit()
    
    # Create an agent
    agent = Agent(
        name="Update Test Agent",
        type=AgentType.RISK_ASSESSOR.value.lower(),
        status=AgentStatus.ACTIVE.value.lower(),
        user_id=user.id,
        deal_id=deal.id,
        configuration={"model": "gpt-4", "temperature": 0.7},
        metadata={"specialty": "risk analysis"}
    )
    db_session.add(agent)
    await db_session.commit()
    
    # Update the agent
    agent.name = "Updated Agent Name"
    agent.status = AgentStatus.PAUSED.value.lower()
    agent.configuration["temperature"] = 0.5
    agent.configuration["max_tokens"] = 2000
    agent.metadata["specialty"] = "advanced risk analysis"
    agent.metadata["priority"] = "high"
    
    await db_session.commit()
    await db_session.refresh(agent)
    
    # Verify the updates
    assert agent.name == "Updated Agent Name"
    assert agent.status == AgentStatus.PAUSED.value.lower()
    assert agent.configuration["temperature"] == 0.5
    assert agent.configuration["max_tokens"] == 2000
    assert agent.metadata["specialty"] == "advanced risk analysis"
    assert agent.metadata["priority"] == "high"
    
    # Verify updated_at was updated
    assert agent.updated_at is not None

@pytest.mark.asyncio
@pytest.mark.core
async def test_agent_deletion(db_session):
    """Test deleting an agent."""
    # Create a user
    user = User(
        email="agent_delete@example.com",
        username="agentdeleteuser",
        full_name="Agent Delete Test User",
        hashed_password="hashed_password_value",
        is_active=True
    )
    db_session.add(user)
    await db_session.commit()
    
    # Create a deal
    deal = Deal(
        title="Agent Delete Test Deal",
        description="A deal for testing agent deletion",
        status=DealStatus.DRAFT.value.lower(),
        market_type=MarketType.CRYPTO.value.lower(),
        user_id=user.id,
        metadata={"test": True}
    )
    db_session.add(deal)
    await db_session.commit()
    
    # Create an agent
    agent = Agent(
        name="Delete Test Agent",
        type=AgentType.MARKET_ANALYST.value.lower(),
        status=AgentStatus.ACTIVE.value.lower(),
        user_id=user.id,
        deal_id=deal.id,
        configuration={"model": "gpt-4"},
        metadata={"test": True}
    )
    db_session.add(agent)
    await db_session.commit()
    
    # Get the agent ID
    agent_id = agent.id
    
    # Delete the agent
    await db_session.delete(agent)
    await db_session.commit()
    
    # Try to find the deleted agent
    stmt = select(Agent).where(Agent.id == agent_id)
    result = await db_session.execute(stmt)
    deleted_agent = result.scalar_one_or_none()
    
    # Verify the agent was deleted
    assert deleted_agent is None 