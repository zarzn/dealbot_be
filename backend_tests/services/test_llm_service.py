"""Tests for the LLM service."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import os
from typing import Dict, Any

from core.services.llm_service import (
    LLMService,
    get_llm_service,
    LLMProvider,
    LLMConfig,
    LLMResponse,
    LLMError
)

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
def mock_llm_responses():
    """Mock responses for different LLM providers."""
    return {
        "deepseek": {
            "text": "Response from DeepSeek R1",
            "usage": {"prompt_tokens": 15, "completion_tokens": 25, "total_tokens": 40}
        },
        "gpt4": {
            "text": "Response from GPT-4",
            "usage": {"prompt_tokens": 20, "completion_tokens": 30, "total_tokens": 50}
        }
    }

@pytest.mark.asyncio
@pytest.mark.service
async def test_llm_service_initialization(mock_env_vars):
    """Test LLM service initialization with different providers."""
    # Test DeepSeek R1 initialization
    deepseek_config = LLMConfig(
        provider=LLMProvider.DEEPSEEK_R1,
        api_key="test_deepseek_key",
        temperature=0.5,
        max_tokens=2000
    )
    deepseek_service = LLMService(config=deepseek_config)
    assert deepseek_service.config.provider == LLMProvider.DEEPSEEK_R1
    assert deepseek_service.config.api_key == "test_deepseek_key"
    
    # Test GPT-4 initialization
    gpt4_config = LLMConfig(
        provider=LLMProvider.GPT4,
        api_key="test_openai_key",
        temperature=0.3,
        max_tokens=3000
    )
    gpt4_service = LLMService(config=gpt4_config)
    assert gpt4_service.config.provider == LLMProvider.GPT4
    assert gpt4_service.config.api_key == "test_openai_key"

@pytest.mark.asyncio
@pytest.mark.service
async def test_get_llm_service(mock_env_vars):
    """Test the get_llm_service factory function."""
    # Test default service (should be DeepSeek R1 in development)
    default_service = await get_llm_service()
    assert default_service.config.provider == LLMProvider.DEEPSEEK_R1
    
    # Test getting specific provider
    deepseek_service = await get_llm_service(provider=LLMProvider.DEEPSEEK_R1)
    assert deepseek_service.config.provider == LLMProvider.DEEPSEEK_R1
    
    # Test custom configuration
    custom_config = LLMConfig(
        provider=LLMProvider.GPT4,
        api_key="custom_key",
        temperature=0.1,
        max_tokens=500
    )
    custom_service = await get_llm_service(config=custom_config)
    assert custom_service.config.provider == LLMProvider.GPT4
    assert custom_service.config.api_key == "custom_key"
    assert custom_service.config.temperature == 0.1
    assert custom_service.config.max_tokens == 500

@pytest.mark.asyncio
@pytest.mark.service
async def test_llm_service_generate_text(mock_env_vars, mock_llm_responses):
    """Test LLM service text generation with different providers."""
    prompt = "Generate a product description for a smartphone."
    messages = [{"role": "user", "content": prompt}]
    
    # Test DeepSeek R1
    with patch("core.services.llm_service.LLMService._call_deepseek_api", 
               new_callable=AsyncMock) as mock_deepseek:
        mock_deepseek.return_value = LLMResponse(
            text=mock_llm_responses["deepseek"]["text"],
            usage=mock_llm_responses["deepseek"]["usage"]
        )
        
        deepseek_config = LLMConfig(
            provider=LLMProvider.DEEPSEEK_R1,
            api_key="test_deepseek_key"
        )
        deepseek_service = LLMService(config=deepseek_config)
        response = await deepseek_service.generate_text(prompt)
        
        assert response.text == mock_llm_responses["deepseek"]["text"]
        assert response.usage == mock_llm_responses["deepseek"]["usage"]
        # Check that the method was called with the correct message format and parameters
        mock_deepseek.assert_called_once_with(messages, 0.7, 1000)
    
    # Test GPT-4
    with patch("core.services.llm_service.LLMService._call_openai_api", 
               new_callable=AsyncMock) as mock_openai:
        mock_openai.return_value = LLMResponse(
            text=mock_llm_responses["gpt4"]["text"],
            usage=mock_llm_responses["gpt4"]["usage"]
        )
        
        gpt4_config = LLMConfig(
            provider=LLMProvider.GPT4,
            api_key="test_openai_key"
        )
        gpt4_service = LLMService(config=gpt4_config)
        response = await gpt4_service.generate_text(prompt)
        
        assert response.text == mock_llm_responses["gpt4"]["text"]
        assert response.usage == mock_llm_responses["gpt4"]["usage"]
        # Check that the method was called with the correct message format and parameters
        mock_openai.assert_called_once_with(messages, 0.7, 1000)

@pytest.mark.asyncio
@pytest.mark.service
async def test_llm_service_fallback(mock_env_vars, mock_llm_responses):
    """Test LLM service fallback mechanism."""
    prompt = "Generate a product description for a smartphone."
    
    # Mock primary provider (DeepSeek) to fail
    with patch("core.services.llm_service.LLMService._call_deepseek_api", 
               new_callable=AsyncMock) as mock_deepseek:
        mock_deepseek.side_effect = LLMError("DeepSeek API error")
        
        # Mock fallback provider (GPT-4) to succeed
        with patch("core.services.llm_service.LLMService._call_openai_api", 
                   new_callable=AsyncMock) as mock_openai:
            mock_openai.return_value = LLMResponse(
                text=mock_llm_responses["gpt4"]["text"],
                usage=mock_llm_responses["gpt4"]["usage"]
            )
            
            # Configure service with fallback
            config = LLMConfig(
                provider=LLMProvider.DEEPSEEK_R1,
                api_key="test_deepseek_key",
                fallback_provider=LLMProvider.GPT4,
                fallback_api_key="test_openai_key"
            )
            service = LLMService(config=config)
            
            # Generate text should fall back to GPT-4
            response = await service.generate_text(prompt, use_fallback=True)
            
            # Verify primary was called and failed
            mock_deepseek.assert_called_once()
            
            # Verify fallback was called and succeeded
            mock_openai.assert_called_once()
            
            # Verify response is from fallback
            assert response.text == mock_llm_responses["gpt4"]["text"]
            assert response.usage == mock_llm_responses["gpt4"]["usage"]
            assert response.used_fallback is True

@pytest.mark.asyncio
@pytest.mark.service
async def test_llm_service_error_handling(mock_env_vars):
    """Test LLM service error handling."""
    prompt = "Generate a product description for a smartphone."
    
    # Test with rate limit error
    with patch("core.services.llm_service.LLMService._call_deepseek_api", 
               new_callable=AsyncMock) as mock_deepseek:
        mock_deepseek.side_effect = LLMError("Rate limit exceeded")
        
        deepseek_config = LLMConfig(
            provider=LLMProvider.DEEPSEEK_R1,
            api_key="test_deepseek_key"
        )
        deepseek_service = LLMService(config=deepseek_config)
        
        # Without fallback, should raise error
        with pytest.raises(LLMError) as excinfo:
            await deepseek_service.generate_text(prompt, use_fallback=False)
        assert "Rate limit exceeded" in str(excinfo.value)
    
    # Test with network error
    with patch("core.services.llm_service.LLMService._call_openai_api", 
               new_callable=AsyncMock) as mock_openai:
        mock_openai.side_effect = LLMError("Network error")
        
        gpt4_config = LLMConfig(
            provider=LLMProvider.GPT4,
            api_key="test_openai_key"
        )
        gpt4_service = LLMService(config=gpt4_config)
        
        # Without fallback, should raise error
        with pytest.raises(LLMError) as excinfo:
            await gpt4_service.generate_text(prompt, use_fallback=False)
        assert "Network error" in str(excinfo.value) 