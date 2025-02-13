"""LLM Manager for handling different LLM providers and fallback logic.

This module provides a unified interface for interacting with different LLM providers,
including Gemini (development), DeepSeek (primary), and OpenAI (fallback).
"""

from typing import Dict, Any, Optional, List
import asyncio
from datetime import datetime
import google.generativeai as genai
from langchain.llms import OpenAI
from pydantic import BaseModel

from core.agents.config.agent_config import (
    LLMProvider,
    LLM_CONFIGS,
    RATE_LIMITS
)
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

    def __init__(self):
        self.redis_client = None
        self._initialize_providers()

    async def initialize(self):
        """Initialize LLM manager"""
        self.redis_client = await get_redis_client()
        await self._setup_rate_limiting()

    def _initialize_providers(self):
        """Initialize LLM providers"""
        # Initialize Gemini
        gemini_config = LLM_CONFIGS[LLMProvider.GEMINI]
        genai.configure(api_key=gemini_config.api_key)
        self.gemini_model = genai.GenerativeModel(
            model_name=gemini_config.model
        )

        # Initialize other providers here
        # TODO: Add DeepSeek and OpenAI initialization

    async def _setup_rate_limiting(self):
        """Setup rate limiting in Redis"""
        if self.redis_client:
            for provider in LLMProvider:
                key = f"rate_limit:{provider.value}"
                await self.redis_client.set(key, 0)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate response using appropriate LLM provider"""
        start_time = datetime.utcnow()

        try:
            # Check cache first
            cache_key = self._generate_cache_key(request)
            cached_response = await self._get_cached_response(cache_key)
            if cached_response:
                return LLMResponse(
                    text=cached_response["text"],
                    provider=cached_response["provider"],
                    tokens_used=cached_response["tokens_used"],
                    processing_time=0,
                    cache_hit=True
                )

            # Try providers in sequence
            for provider in self._get_provider_sequence(request.provider):
                try:
                    if await self._check_rate_limit(provider):
                        response = await self._generate_with_provider(
                            provider, request
                        )
                        
                        # Cache successful response
                        await self._cache_response(cache_key, {
                            "text": response.text,
                            "provider": response.provider,
                            "tokens_used": response.tokens_used
                        })
                        
                        return response
                except Exception as e:
                    logger.error(
                        f"Error with provider {provider}: {str(e)}",
                        exc_info=True
                    )
                    continue

            raise Exception("All LLM providers failed")

        except Exception as e:
            logger.error(f"LLM generation failed: {str(e)}", exc_info=True)
            raise

    async def _generate_with_provider(
        self,
        provider: LLMProvider,
        request: LLMRequest
    ) -> LLMResponse:
        """Generate response with specific provider"""
        config = LLM_CONFIGS[provider]
        
        if provider == LLMProvider.GEMINI:
            return await self._generate_with_gemini(request, config)
        elif provider == LLMProvider.DEEPSEEK:
            return await self._generate_with_deepseek(request, config)
        elif provider == LLMProvider.OPENAI:
            return await self._generate_with_openai(request, config)
        
        raise ValueError(f"Unsupported provider: {provider}")

    async def _generate_with_gemini(
        self,
        request: LLMRequest,
        config: Dict[str, Any]
    ) -> LLMResponse:
        """Generate response using Gemini"""
        start_time = datetime.utcnow()
        
        response = await self.gemini_model.generate_content_async(
            request.prompt,
            generation_config={
                "temperature": request.temperature or config.temperature,
                "max_output_tokens": request.max_tokens or config.max_tokens
            }
        )
        
        return LLMResponse(
            text=response.text,
            provider=LLMProvider.GEMINI,
            tokens_used=len(response.text.split()),  # Approximate
            processing_time=(datetime.utcnow() - start_time).total_seconds()
        )

    async def _generate_with_deepseek(
        self,
        request: LLMRequest,
        config: Dict[str, Any]
    ) -> LLMResponse:
        """Generate response using DeepSeek"""
        # TODO: Implement DeepSeek integration
        raise NotImplementedError("DeepSeek integration not implemented yet")

    async def _generate_with_openai(
        self,
        request: LLMRequest,
        config: Dict[str, Any]
    ) -> LLMResponse:
        """Generate response using OpenAI"""
        # TODO: Implement OpenAI integration
        raise NotImplementedError("OpenAI integration not implemented yet")

    def _get_provider_sequence(
        self,
        preferred_provider: Optional[LLMProvider]
    ) -> List[LLMProvider]:
        """Get sequence of providers to try"""
        if preferred_provider:
            return [preferred_provider]
        
        # Development environment uses Gemini
        if LLM_CONFIGS[LLMProvider.GEMINI].is_development:
            return [LLMProvider.GEMINI]
        
        # Production environment uses DeepSeek with OpenAI fallback
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
        return f"llm:request:{hash(request.prompt)}"

    async def _get_cached_response(
        self,
        cache_key: str
    ) -> Optional[Dict[str, Any]]:
        """Get cached response if available"""
        if self.redis_client:
            return await self.redis_client.get(cache_key)
        return None

    async def _cache_response(
        self,
        cache_key: str,
        response: Dict[str, Any]
    ):
        """Cache successful response"""
        if self.redis_client:
            await self.redis_client.set(
                cache_key,
                response,
                ex=3600  # 1 hour TTL
            ) 