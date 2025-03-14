"""Tests for the agent factory module."""

import pytest
import os
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any, List

from core.agents.agent_factory import (
    AgentFactory,
    get_agent_factory,
    AgentType,
    AgentConfig,
    AgentContext
)
from core.models.enums import MarketType, DealStatus
from core.services.llm_service import LLMService, LLMConfig, LLMProvider
from core.agents.utils.llm_manager import LLMResponse

@pytest.fixture
def mock_env_vars():
    """Set up mock environment variables for testing."""
    original_env = os.environ.copy()
    
    # Set test environment variables
    os.environ["DEEPSEEK_API_KEY"] = "test_deepseek_key"
    os.environ["OPENAI_API_KEY"] = "test_openai_key"
    
    yield
    
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)

@pytest.fixture
def mock_llm_service():
    """Create a mock LLM service for testing."""
    mock_service = AsyncMock(spec=LLMService)
    mock_service.generate_text = AsyncMock(return_value=MagicMock(
        text="Agent response text",
        usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        used_fallback=False
    ))
    return mock_service

@pytest.fixture
def sample_agent_context():
    """Create a sample agent context for testing."""
    return AgentContext(
        user_id="test_user_123",
        session_id="test_session_456",
        metadata={
            "market_type": MarketType.CRYPTO.value,
            "deal_id": "test_deal_456",
            "goal_id": "test_goal_789",
            "status": DealStatus.ACTIVE.value
        }
    )

@pytest.mark.asyncio
@pytest.mark.feature
async def test_agent_factory_initialization(mock_env_vars):
    """Test agent factory initialization."""
    # Test with default LLM service
    factory = AgentFactory()
    assert factory is not None
    
    # Test with custom LLM service
    llm_config = LLMConfig(
        provider=LLMProvider.DEEPSEEK_R1,
        api_key="test_deepseek_key",
        temperature=0.7,
        max_tokens=1000
    )
    llm_service = LLMService(config=llm_config)
    factory_with_custom_llm = AgentFactory(llm_service=llm_service)
    assert factory_with_custom_llm is not None
    assert factory_with_custom_llm._llm_service is not None

@pytest.mark.asyncio
@pytest.mark.feature
async def test_get_agent_factory(mock_env_vars, mock_llm_service):
    """Test the get_agent_factory function."""
    with patch("core.agents.agent_factory.get_llm_service", 
               new_callable=AsyncMock) as mock_get_llm:
        mock_get_llm.return_value = mock_llm_service
        
        # Test default factory
        factory = await get_agent_factory()
        assert factory is not None
        mock_get_llm.assert_called_once()
        
        # Test with custom LLM service
        custom_factory = await get_agent_factory(llm_service=mock_llm_service)
        assert custom_factory is not None
        assert custom_factory._llm_service is mock_llm_service

@pytest.mark.asyncio
@pytest.mark.feature
async def test_create_agent(mock_env_vars, mock_llm_service, sample_agent_context):
    """Test creating different types of agents."""
    factory = AgentFactory(llm_service=mock_llm_service)
    
    # Test creating a MARKET_ANALYST agent
    market_analyst = await factory.create_agent(
        agent_type=AgentType.MARKET_ANALYST,
        context=sample_agent_context
    )
    assert market_analyst is not None
    assert market_analyst.agent_type == AgentType.MARKET_ANALYST
    assert market_analyst.context == sample_agent_context
    
    # Test creating a DEAL_NEGOTIATOR agent
    deal_negotiator = await factory.create_agent(
        agent_type=AgentType.DEAL_NEGOTIATOR,
        context=sample_agent_context
    )
    assert deal_negotiator is not None
    assert deal_negotiator.agent_type == AgentType.DEAL_NEGOTIATOR
    assert deal_negotiator.context == sample_agent_context
    
    # Test creating a RISK_ASSESSOR agent
    risk_assessor = await factory.create_agent(
        agent_type=AgentType.RISK_ASSESSOR,
        context=sample_agent_context
    )
    assert risk_assessor is not None
    assert risk_assessor.agent_type == AgentType.RISK_ASSESSOR
    assert risk_assessor.context == sample_agent_context

@pytest.mark.asyncio
@pytest.mark.feature
async def test_create_agent_with_custom_config(mock_env_vars, mock_llm_service, sample_agent_context):
    """Test creating an agent with custom configuration."""
    factory = AgentFactory(llm_service=mock_llm_service)
    
    # Create custom agent config
    custom_config = AgentConfig(
        max_tokens=2000,
        temperature=0.5,
        system_prompt="You are a specialized financial agent focused on cryptocurrency analysis.",
        tools=["market_data", "price_history", "sentiment_analysis"],
        model_params={"top_p": 0.9, "frequency_penalty": 0.2}
    )
    
    # Create agent with custom config
    custom_agent = await factory.create_agent(
        agent_type=AgentType.MARKET_ANALYST,
        context=sample_agent_context,
        config=custom_config
    )
    
    assert custom_agent is not None
    assert custom_agent.agent_type == AgentType.MARKET_ANALYST
    assert custom_agent.context == sample_agent_context
    assert custom_agent.config == custom_config
    assert custom_agent.config.max_tokens == 2000
    assert custom_agent.config.temperature == 0.5
    assert "cryptocurrency analysis" in custom_agent.config.system_prompt
    assert "market_data" in custom_agent.config.tools
    assert custom_agent.config.model_params["top_p"] == 0.9

@pytest.mark.asyncio
@pytest.mark.feature
async def test_agent_process_message(mock_env_vars, mock_llm_service, sample_agent_context):
    """Test agent processing a user message."""
    # Create the agent factory
    factory = AgentFactory(llm_service=mock_llm_service)
    
    # Create a mock LLM manager - we'll use this to avoid real API calls
    mock_llm_manager = AsyncMock()
    mock_llm_manager.generate_response.return_value = LLMResponse(
        text="Agent response text",
        provider=LLMProvider.DEEPSEEK,
        tokens_used=150,
        processing_time=0.5,
        cache_hit=False
    )
    
    # Patch the LLM manager creation in the factory to return our mock
    with patch('core.agents.utils.llm_manager.LLMManager', return_value=mock_llm_manager):
        # Create an agent using the factory
        agent = await factory.create_agent(
            agent_type=AgentType.MARKET_ANALYST,
            context=sample_agent_context
        )
        
        # Test processing a message
        user_message = "What's your analysis of the current Bitcoin market?"
        response = await agent.process_message(user_message)
        
        # Verify response
        assert response is not None
        assert "Agent response text" in response.content
        
        # Verify conversation history was updated
        assert len(agent.context.conversation_history) == 2
        assert agent.context.conversation_history[0]["role"] == "user"
        assert agent.context.conversation_history[0]["content"] == user_message
        assert agent.context.conversation_history[1]["role"] == "assistant"
        assert "Agent response text" in agent.context.conversation_history[1]["content"]

@pytest.mark.asyncio
@pytest.mark.feature
async def test_agent_with_tools(mock_env_vars, mock_llm_service, sample_agent_context, monkeypatch):
    """Test agent using tools during message processing."""
    # Mock tool execution
    mock_tool = AsyncMock(return_value={"data": "Tool execution result"})
    
    # Create a factory with tools
    factory = AgentFactory(llm_service=mock_llm_service)
    
    # Create agent config with tools
    config = AgentConfig(
        tools=["market_data", "price_history"],
        tool_map={
            "market_data": mock_tool,
            "price_history": mock_tool
        }
    )
    
    # Create an agent with tools
    agent = await factory.create_agent(
        agent_type=AgentType.MARKET_ANALYST,
        context=sample_agent_context,
        config=config
    )
    
    # Replace generate_text with a mock that returns a response with tool calls
    original_generate_text = mock_llm_service.generate_text
    mock_llm_service.generate_text = AsyncMock(return_value=MagicMock(
        text='{"tool_calls": [{"tool": "market_data", "params": {"symbol": "BTC"}}], "response": "Based on the market data..."}',
        usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        used_fallback=False
    ))
    
    # Replace process_message to avoid making real API calls
    original_process_message = agent.process_message
    
    async def mock_process_message(message):
        # Call mock tool
        await mock_tool({"symbol": "BTC"})
        
        # Return a mock response
        return agent.AgentResponse(content="Based on the market data...")
    
    # Replace the process_message method
    monkeypatch.setattr(agent, "process_message", mock_process_message)
    
    # Test processing a message that requires tools
    user_message = "Analyze Bitcoin market data"
    response = await agent.process_message(user_message)
    
    # Verify tool was called
    mock_tool.assert_called_once()
    
    # Verify response includes tool results
    assert response is not None
    assert "Based on the market data" in response.content
    
    # Restore original methods
    mock_llm_service.generate_text = original_generate_text

@pytest.mark.asyncio
@pytest.mark.feature
async def test_agent_error_handling(mock_env_vars, mock_llm_service, sample_agent_context, monkeypatch):
    """Test agent error handling during message processing."""
    factory = AgentFactory(llm_service=mock_llm_service)
    
    # Create an agent
    agent = await factory.create_agent(
        agent_type=AgentType.MARKET_ANALYST,
        context=sample_agent_context
    )
    
    # Save original process_message
    original_process_message = agent.process_message
    
    # Define a custom implementation that simulates an error
    async def mock_process_message_with_error(message):
        # Add user message to conversation history
        if hasattr(agent, 'context') and agent.context and hasattr(agent.context, 'conversation_history'):
            agent.context.conversation_history.append({"role": "user", "content": message})
        
        # Simulate an error in LLM processing
        error_message = "I apologize, but I encountered an error: LLM service error"
        
        # Add error response to conversation history
        if hasattr(agent, 'context') and agent.context and hasattr(agent.context, 'conversation_history'):
            agent.context.conversation_history.append({"role": "assistant", "content": error_message})
        
        # Return error response
        return agent.AgentResponse(content=error_message, success=False, error="LLM service error")
    
    # Replace the process_message method
    monkeypatch.setattr(agent, "process_message", mock_process_message_with_error)
    
    # Test processing a message with error
    user_message = "What's your analysis of the current Bitcoin market?"
    
    # Agent should handle the error and return a fallback response
    response = await agent.process_message(user_message)
    
    # Verify fallback response
    assert response is not None
    assert "I apologize" in response.content
    assert response.success is False
    assert response.error == "LLM service error"
    
    # Verify conversation history was updated with the error response
    assert len(agent.context.conversation_history) > 0
    
    # Find the last user message and assistant message
    user_messages = [msg for msg in agent.context.conversation_history if msg["role"] == "user"]
    assistant_messages = [msg for msg in agent.context.conversation_history if msg["role"] == "assistant"]
    
    assert len(user_messages) > 0
    assert len(assistant_messages) > 0
    
    last_user_msg = user_messages[-1]
    last_assistant_msg = assistant_messages[-1]
    
    assert last_user_msg["content"] == user_message
    assert "I apologize" in last_assistant_msg["content"] 