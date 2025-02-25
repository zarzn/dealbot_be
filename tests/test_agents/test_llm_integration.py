import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from core.agents.utils.llm_manager import LLMProvider, LLMRequest
from core.exceptions.agent_exceptions import LLMProviderError

@pytest.fixture
def mock_gemini_response():
    """Mock Gemini API response."""
    response = MagicMock()
    response.text = "Test response from Gemini"
    return response

@pytest.fixture
def mock_deepseek_response():
    """Mock DeepSeek API response."""
    return {
        "choices": [{
            "message": {
                "content": "Test response from DeepSeek"
            }
        }],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30
        }
    }

@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response."""
    class MockResponse:
        def __init__(self):
            self.choices = [
                type('Choice', (), {
                    'message': type('Message', (), {
                        'content': "Test response from OpenAI"
                    })
                })()
            ]
            self.usage = type('Usage', (), {
                'total_tokens': 40
            })
    return MockResponse()

@pytest.mark.asyncio
async def test_gemini_integration(llm_manager, mock_gemini_response):
    """Test Gemini integration."""
    with patch('google.generativeai.GenerativeModel.generate_content', new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value = mock_gemini_response
        
        # Disable development mode for this test
        llm_manager.is_development = False
        
        response = await llm_manager.generate(
            LLMRequest(
                prompt="Test prompt",
                provider=LLMProvider.GEMINI,
                temperature=0.7
            )
        )
        
        assert response.text == mock_gemini_response.text
        assert response.provider == LLMProvider.GEMINI
        mock_generate.assert_called_once()

@pytest.mark.asyncio
async def test_deepseek_integration(llm_manager, mock_deepseek_response):
    """Test DeepSeek integration."""
    async def mock_post(*args, **kwargs):
        mock = AsyncMock()
        mock.status_code = 200
        mock.json = AsyncMock(return_value=mock_deepseek_response)
        return mock

    with patch('httpx.AsyncClient.post', new_callable=AsyncMock) as mock_client:
        mock_client.return_value = await mock_post()
        
        # Disable development mode for this test
        llm_manager.is_development = False
        
        response = await llm_manager.generate(
            LLMRequest(
                prompt="Test prompt",
                provider=LLMProvider.DEEPSEEK,
                temperature=0.7
            )
        )
        
        assert response.text == mock_deepseek_response["choices"][0]["message"]["content"]
        assert response.provider == LLMProvider.DEEPSEEK
        mock_client.assert_called_once()

@pytest.mark.asyncio
async def test_openai_integration(llm_manager, mock_openai_response):
    """Test OpenAI integration."""
    with patch('openai.resources.chat.completions.AsyncCompletions.create',
              new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_openai_response
        
        # Disable development mode for this test
        llm_manager.is_development = False
        
        response = await llm_manager.generate(
            LLMRequest(
                prompt="Test prompt",
                provider=LLMProvider.OPENAI,
                temperature=0.7
            )
        )
        
        assert response.text == mock_openai_response.choices[0].message.content
        assert response.provider == LLMProvider.OPENAI
        mock_create.assert_called_once()

@pytest.mark.asyncio
async def test_fallback_mechanism(llm_manager, mock_deepseek_response, mock_openai_response):
    """Test fallback mechanism when primary provider fails."""
    async def mock_deepseek_error(*args, **kwargs):
        mock = AsyncMock()
        mock.status_code = 500
        mock.text = "DeepSeek API error"
        return mock

    with patch('httpx.AsyncClient.post',
              new_callable=AsyncMock) as mock_deepseek:
        mock_deepseek.return_value = await mock_deepseek_error()
        
        with patch('openai.resources.chat.completions.AsyncCompletions.create',
                  new_callable=AsyncMock) as mock_openai:
            mock_openai.return_value = mock_openai_response
            
            # Disable development mode for this test
            llm_manager.is_development = False
            
            response = await llm_manager.generate(
                LLMRequest(
                    prompt="Test prompt",
                    provider=LLMProvider.DEEPSEEK,
                    temperature=0.7
                )
            )
            
            assert response.text == mock_openai_response.choices[0].message.content
            assert response.provider == LLMProvider.OPENAI
            mock_deepseek.assert_called_once()
            mock_openai.assert_called_once()

@pytest.mark.asyncio
async def test_development_mode(llm_manager):
    """Test development mode with DeepSeek."""
    # Force development mode
    llm_manager.is_development = True
    
    response = await llm_manager.generate(
        LLMRequest(
            prompt="Test prompt",
            provider=LLMProvider.DEEPSEEK,
            temperature=0.7
        )
    )
    
    assert response.text == f"Development response from {LLMProvider.DEEPSEEK.value.title()}"
    assert response.provider == LLMProvider.DEEPSEEK

@pytest.mark.asyncio
async def test_error_handling(llm_manager):
    """Test error handling for all providers."""
    with patch('httpx.AsyncClient.post',
              side_effect=Exception("DeepSeek error")), \
         patch('openai.resources.chat.completions.AsyncCompletions.create',
              side_effect=Exception("OpenAI error")):
        
        # Disable development mode for this test
        llm_manager.is_development = False
        
        with pytest.raises(LLMProviderError) as exc_info:
            await llm_manager.generate(
                LLMRequest(
                    prompt="Test prompt",
                    provider=LLMProvider.DEEPSEEK,
                    temperature=0.7
                )
            )
        
        assert "All LLM providers failed" in str(exc_info.value) 