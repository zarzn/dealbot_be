"""LLM Service module.

This module provides services for interacting with various LLM providers
in the AI Agentic Deals System.
"""

from typing import Dict, Any, Optional, List, Union, Callable
from enum import Enum
import logging
import os
import json
import asyncio
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)

class LLMProvider(str, Enum):
    """LLM provider enumeration."""
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    MOCK = "mock"
    # Additional values expected by tests
    DEEPSEEK_R1 = "deepseek-chat"
    GPT4 = "gpt-4"

class LLMModel(str, Enum):
    """LLM model enumeration."""
    GPT4 = "gpt-3.5-turbo"
    GPT35_TURBO = "gpt-3.5-turbo"
    DEEPSEEK_R1 = "deepseek-chat"
    MOCK_LLM = "mock-llm"

class LLMConfig(BaseModel):
    """LLM configuration model."""
    provider: str = Field(default=LLMProvider.OPENAI.value)
    model: Optional[str] = Field(default=None)
    api_key: Optional[str] = Field(default=None)
    temperature: float = Field(default=0.7)
    max_tokens: int = Field(default=1000)
    timeout: int = Field(default=60)
    retry_count: int = Field(default=3)
    retry_delay: int = Field(default=2)
    additional_params: Dict[str, Any] = Field(default_factory=dict)
    fallback_provider: Optional[str] = Field(default=None)
    fallback_api_key: Optional[str] = Field(default=None)
    
    model_config = ConfigDict(extra="allow")
    
    def __init__(self, **data):
        # Handle enum values by converting to string values
        if "provider" in data and isinstance(data["provider"], LLMProvider):
            data["provider"] = data["provider"].value
        if "fallback_provider" in data and isinstance(data["fallback_provider"], LLMProvider):
            data["fallback_provider"] = data["fallback_provider"].value
        super().__init__(**data)
        # Set default model based on provider if not specified
        if self.model is None:
            if self.provider == LLMProvider.OPENAI.value or self.provider == LLMProvider.GPT4.value:
                self.model = LLMModel.GPT4.value
            elif self.provider == LLMProvider.DEEPSEEK.value or self.provider == LLMProvider.DEEPSEEK_R1.value:
                self.model = LLMModel.DEEPSEEK_R1.value
            elif self.provider == LLMProvider.MOCK.value:
                self.model = LLMModel.MOCK_LLM.value

class LLMMessage(BaseModel):
    """LLM message model."""
    role: str
    content: str
    
    model_config = ConfigDict(extra="allow")

class LLMResponse(BaseModel):
    """LLM response model."""
    content: str = Field(default="")
    model: Optional[str] = None
    provider: Optional[str] = None
    tokens_used: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = None
    text: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None
    used_fallback: bool = False
    
    model_config = ConfigDict(extra="allow")
    
    def __init__(self, **data):
        # Support both 'content' and 'text' fields for the generated text
        if "content" in data and "text" not in data:
            data["text"] = data["content"]
        elif "text" in data and "content" not in data:
            data["content"] = data["text"]
        super().__init__(**data)

class LLMError(Exception):
    """Base exception for LLM-related errors."""
    pass

class LLMService:
    """LLM service for interacting with various LLM providers."""
    
    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        config: Optional[LLMConfig] = None
    ):
        """Initialize the LLM service.
        
        Args:
            provider: The LLM provider to use
            model: The model to use (if None, a default model will be selected)
            api_key: The API key to use (if None, will try to get from environment)
            config: Configuration for the LLM service
        """
        if config:
            self.config = config
        else:
            self.config = LLMConfig(
                provider=provider or LLMProvider.OPENAI.value,
                model=model,
                api_key=api_key
            )
        
        # Set API key if not provided in config
        if not self.config.api_key:
            if self.config.provider in [LLMProvider.OPENAI.value, LLMProvider.GPT4.value]:
                self.config.api_key = os.environ.get("OPENAI_API_KEY")
            elif self.config.provider in [LLMProvider.DEEPSEEK.value, LLMProvider.DEEPSEEK_R1.value]:
                self.config.api_key = os.environ.get("DEEPSEEK_API_KEY")
            elif self.config.provider == LLMProvider.MOCK.value:
                self.config.api_key = "mock-api-key"
            else:
                raise ValueError(f"No API key found for provider: {self.config.provider}")
        
        logger.info(f"Initialized LLM service with provider: {self.config.provider}, model: {self.config.model}")
    
    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate a response from the LLM.
        
        Args:
            messages: List of messages to send to the LLM
            temperature: Temperature parameter for generation
            max_tokens: Maximum number of tokens to generate
            **kwargs: Additional parameters to pass to the LLM
            
        Returns:
            LLMResponse object containing the generated text
        """
        try:
            # Use config values if not provided
            temperature = temperature if temperature is not None else self.config.temperature
            max_tokens = max_tokens if max_tokens is not None else self.config.max_tokens
            
            if self.config.provider == LLMProvider.MOCK.value:
                # For testing purposes
                await asyncio.sleep(0.1)
                return LLMResponse(
                    content="This is a mock response from the LLM service.",
                    model=self.config.model,
                    provider=self.config.provider,
                    tokens_used=10,
                    metadata={"mock": True}
                )
            
            # Call the appropriate API based on the provider
            if self.config.provider in [LLMProvider.OPENAI.value, LLMProvider.GPT4.value]:
                return await self._call_openai_api(messages, temperature, max_tokens, **kwargs)
            elif self.config.provider in [LLMProvider.DEEPSEEK.value, LLMProvider.DEEPSEEK_R1.value]:
                return await self._call_deepseek_api(messages, temperature, max_tokens, **kwargs)
            else:
                raise LLMError(f"Unsupported provider: {self.config.provider}")
        
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            raise LLMError(f"Failed to generate response: {str(e)}")

    async def generate_text(
        self,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        use_fallback: bool = False,
        **kwargs
    ) -> LLMResponse:
        """Generate text from a single prompt string.
        
        This is a convenience wrapper around the generate method that accepts
        a single prompt string instead of a list of messages.
        
        Args:
            prompt: The text prompt to send to the LLM
            temperature: Temperature parameter for generation
            max_tokens: Maximum number of tokens to generate
            use_fallback: Whether to try the fallback provider if the primary fails
            **kwargs: Additional parameters to pass to the LLM
            
        Returns:
            LLMResponse object containing the generated text
        """
        messages = [{"role": "user", "content": prompt}]
        
        try:
            return await self.generate(messages, temperature, max_tokens, **kwargs)
        except LLMError as e:
            if use_fallback and self.config.fallback_provider:
                logger.warning(f"Primary provider failed, falling back to {self.config.fallback_provider}")
                
                # Create a temporary service with the fallback configuration
                fallback_config = LLMConfig(
                    provider=self.config.fallback_provider,
                    api_key=self.config.fallback_api_key,
                    temperature=temperature or self.config.temperature,
                    max_tokens=max_tokens or self.config.max_tokens
                )
                fallback_service = LLMService(config=fallback_config)
                
                # Generate using the fallback service
                response = await fallback_service.generate(messages, temperature, max_tokens, **kwargs)
                
                # Add used_fallback flag to response
                response_dict = response.model_dump()
                response_dict["used_fallback"] = True
                return LLMResponse(**response_dict)
            else:
                # If no fallback is configured or fallback is disabled, re-raise the error
                raise
    
    async def _call_openai_api(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        **kwargs
    ) -> LLMResponse:
        """Call the OpenAI API to generate a response.
        
        Args:
            messages: List of messages to send to the API
            temperature: Temperature parameter for generation
            max_tokens: Maximum number of tokens to generate
            **kwargs: Additional parameters to pass to the API
            
        Returns:
            LLMResponse object containing the generated text
        """
        # Mock implementation for now
        await asyncio.sleep(0.2)
        return LLMResponse(
            content=f"Response from {self.config.model} via OpenAI",
            model=self.config.model or LLMModel.GPT4.value,
            provider=self.config.provider,
            tokens_used=50,
            metadata={
                "temperature": temperature,
                "max_tokens": max_tokens,
                **kwargs
            },
            usage={
                "prompt_tokens": 20,
                "completion_tokens": 30,
                "total_tokens": 50
            }
        )
    
    async def _call_deepseek_api(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        **kwargs
    ) -> LLMResponse:
        """Call the DeepSeek API to generate a response.
        
        Args:
            messages: List of messages to send to the API
            temperature: Temperature parameter for generation
            max_tokens: Maximum number of tokens to generate
            **kwargs: Additional parameters to pass to the API
            
        Returns:
            LLMResponse object containing the generated text
        """
        # Mock implementation for now
        await asyncio.sleep(0.2)
        return LLMResponse(
            content=f"Response from {self.config.model} via DeepSeek",
            model=self.config.model or LLMModel.DEEPSEEK_R1.value,
            provider=self.config.provider,
            tokens_used=40,
            metadata={
                "temperature": temperature,
                "max_tokens": max_tokens,
                **kwargs
            },
            usage={
                "prompt_tokens": 15,
                "completion_tokens": 25,
                "total_tokens": 40
            }
        )

async def get_llm_service(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    config: Optional[LLMConfig] = None
) -> LLMService:
    """Get an LLM service instance.
    
    Args:
        provider: The LLM provider to use (defaults to environment configuration)
        model: The model to use
        api_key: The API key to use
        config: Configuration for the LLM service
        
    Returns:
        An LLMService instance
    """
    # Use environment variables to determine default provider
    if provider is None and config is None:
        if os.environ.get("DEEPSEEK_API_KEY"):
            provider = LLMProvider.DEEPSEEK_R1.value
        elif os.environ.get("OPENAI_API_KEY"):
            provider = LLMProvider.GPT4.value
        else:
            provider = LLMProvider.MOCK.value
    
    return LLMService(
        provider=provider,
        model=model,
        api_key=api_key,
        config=config
    )
