"""LLM Manager for handling different LLM providers and fallback logic.

This module provides a unified interface for interacting with different LLM providers,
including DeepSeek (primary) and OpenAI (fallback).
"""

from typing import Dict, Any, Optional, List
import asyncio
from datetime import datetime
import httpx
from langchain_community.chat_models import ChatOpenAI
from pydantic import BaseModel
from openai import AsyncOpenAI
import os
from unittest.mock import AsyncMock

from core.agents.config.agent_config import (
    LLMProvider,
    LLM_CONFIGS,
    RATE_LIMITS
)
from core.exceptions.agent_exceptions import LLMProviderError
from core.utils.redis import get_redis_client
from core.utils.logger import get_logger

logger = get_logger(__name__)

class LLMRequest(BaseModel):
    """Model for LLM requests"""
    prompt: str
    provider: Optional[LLMProvider] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    context: Optional[Dict[str, Any]] = None

class LLMResponse(BaseModel):
    """Model for LLM responses"""
    text: str
    provider: LLMProvider
    tokens_used: int
    processing_time: float
    cache_hit: bool = False

class LLMManager:
    """Manager for handling LLM interactions"""

    def __init__(self, redis_client=None, is_development: bool = False, **kwargs):
        self.redis_client = redis_client
        self.is_development = is_development
        self._token_usage = {}
        
        # Store additional configuration parameters
        self.max_tokens = kwargs.get('max_tokens', None)
        self.temperature = kwargs.get('temperature', None)
        self.system_prompt = kwargs.get('system_prompt', None)
        self.model_params = kwargs.get('model_params', {})
        self.tools = kwargs.get('tools', [])
        self.tool_map = kwargs.get('tool_map', {})
        
        self._initialize_providers()

    async def initialize(self):
        """Initialize LLM manager"""
        if self.redis_client is None:
            self.redis_client = await get_redis_client()
        await self._setup_rate_limiting()

    def _initialize_providers(self):
        """Initialize LLM providers"""
        # Initialize OpenAI client
        openai_config = LLM_CONFIGS[LLMProvider.OPENAI]
        self.openai_client = AsyncOpenAI(
            api_key=openai_config.api_key or os.getenv("OPENAI_API_KEY")
        )

    async def _setup_rate_limiting(self):
        """Setup rate limiting in Redis"""
        if self.redis_client:
            for provider in LLMProvider:
                key = f"rate_limit:{provider.value}"
                await self.redis_client.set(key, 0)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate response using appropriate LLM provider"""
        # Get provider sequence
        provider = request.provider or LLMProvider.DEEPSEEK
        config = LLM_CONFIGS[provider]
        
        # Development mode - use mock responses
        if self.is_development:
            return LLMResponse(
                text=f"Development response from {provider.value.title()}",
                provider=provider,
                tokens_used=100,
                processing_time=0,
                cache_hit=False
            )
            
        # Production mode - use requested provider
        try:
            if provider == LLMProvider.DEEPSEEK:
                return await self._generate_with_deepseek(request, config)
            elif provider == LLMProvider.OPENAI:
                return await self._generate_with_openai(request, config)
            
            raise ValueError(f"Unsupported provider: {provider}")
        except Exception as e:
            logger.error(f"Error with provider {provider}: {str(e)}")
            raise LLMProviderError(f"Provider {provider} failed: {str(e)}")

    async def _generate_with_deepseek(
        self,
        request: LLMRequest,
        config: Dict[str, Any]
    ) -> LLMResponse:
        """Generate response using DeepSeek API."""
        try:
            api_key = config.api_key or os.getenv("DEEPSEEK_API_KEY")
            if not api_key:
                raise LLMProviderError("DeepSeek API key not configured")

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": config.model,
                        "messages": [{"role": "user", "content": request.prompt}],
                        "temperature": request.temperature or config.temperature,
                        "max_tokens": request.max_tokens or config.max_tokens
                    },
                    timeout=30.0
                )

                if response.status_code != 200:
                    raise LLMProviderError(f"DeepSeek API error: {response.status_code} - {response.text}")
                
                result = await response.json()
                
                return LLMResponse(
                    text=result["choices"][0]["message"]["content"],
                    provider=LLMProvider.DEEPSEEK,
                    tokens_used=result["usage"]["total_tokens"],
                    processing_time=0,
                    cache_hit=False
                )
        except httpx.HTTPError as e:
            raise LLMProviderError(f"DeepSeek API HTTP error: {str(e)}")
        except Exception as e:
            raise LLMProviderError(f"Unexpected error with DeepSeek: {str(e)}")

    async def _generate_with_openai(
        self,
        request: LLMRequest,
        config: Dict[str, Any]
    ) -> LLMResponse:
        """Generate text using OpenAI API.
        
        Args:
            request: Request parameters
            config: OpenAI configuration
            
        Returns:
            Response with generated text
        """
        # In development or testing environments, return a mock response
        if self.is_development:
            await asyncio.sleep(0.1)  # Simulate API delay
            return LLMResponse(
                text="OpenAI mock response for: " + request.prompt[:20] + "...",
                provider=LLMProvider.OPENAI,
                tokens_used=50,
                processing_time=0.1,
                cache_hit=False
            )
        
        start_time = datetime.now()
        
        try:
            # Use ChatOpenAI from langchain_community
            chat_model = ChatOpenAI(
                model_name=config.get("model", "gpt-3.5-turbo"),
                temperature=request.temperature or config.get("temperature", 0.7),
                max_tokens=request.max_tokens or config.get("max_tokens", 500),
                api_key=config.get("api_key")
            )
            
            # Generate response using agenerate
            response = await chat_model.agenerate([[request.prompt]])
            completion = response.generations[0][0]
            response_text = completion.text
            tokens = response.llm_output.get("token_usage", {}).get("total_tokens", 50)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return LLMResponse(
                text=response_text,
                provider=LLMProvider.OPENAI,
                tokens_used=tokens,
                processing_time=processing_time
            )
        except Exception as e:
            logger.error(f"Error with OpenAI: {str(e)}")
            raise LLMProviderError(f"OpenAI error: {str(e)}")

    def _update_token_usage(self, provider: LLMProvider, tokens: int):
        """Update token usage tracking"""
        if provider not in self._token_usage:
            self._token_usage[provider] = 0
        self._token_usage[provider] += tokens

    async def get_token_usage(self) -> Dict[str, Any]:
        """Get current token usage statistics"""
        total = sum(self._token_usage.values())
        return {
            "total_tokens": total,
            "usage_by_provider": {
                p.value: count for p, count in self._token_usage.items()
            }
        }

    def _get_provider_sequence(
        self,
        preferred_provider: Optional[LLMProvider]
    ) -> List[LLMProvider]:
        """Get sequence of providers to try"""
        # If a specific provider is requested, use it with OpenAI as fallback
        if preferred_provider:
            return [preferred_provider, LLMProvider.OPENAI]
        
        # Default production sequence
        return [LLMProvider.DEEPSEEK, LLMProvider.OPENAI]

    async def _check_rate_limit(self, provider: LLMProvider) -> bool:
        """Check if rate limit is exceeded for provider"""
        if not self.redis_client:
            return True

        key = f"rate_limit:{provider.value}"
        current = await self.redis_client.incr(key)
        
        if current == 1:
            await self.redis_client.expire(key, 60)  # 1 minute window
            
        return current <= RATE_LIMITS["llm_requests_per_minute"]

    def _generate_cache_key(self, request: LLMRequest) -> str:
        """Generate cache key for request"""
        return f"llm:response:{request.provider}:{hash(request.prompt)}"

    async def _get_cached_response(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached response if available"""
        if not self.redis_client:
            return None
            
        cached = await self.redis_client.get(key)
        return cached and eval(cached)  # Safe since we control the cache data

    async def _cache_response(self, key: str, response: Dict[str, Any]):
        """Cache response for future use"""
        if not self.redis_client:
            return
            
        await self.redis_client.setex(
            key,
            300,  # 5 minute TTL
            str(response)
        )

    async def generate_response(
        self,
        prompt: str,
        provider: Optional[LLMProvider] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate response using specified provider."""
        request = LLMRequest(
            prompt=prompt,
            provider=provider or (LLMProvider.DEEPSEEK if self.is_development else LLMProvider.DEEPSEEK),
            temperature=temperature,
            max_tokens=max_tokens
        )
        response = await self.generate(request)
        return response.text
 