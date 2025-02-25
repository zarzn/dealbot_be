"""LLM utility module.

This module provides language model utilities for the AI Agentic Deals System.
Supported models:
- DeepSeek: Primary model for production (requires DEEPSEEK_API_KEY)
- GPT-4: Fallback model (requires OPENAI_API_KEY)
"""

import logging
import sys
from typing import Optional, Dict, Any, List, Union
from enum import Enum

from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, Runnable

from core.config import settings
from core.exceptions import AIServiceError

logger = logging.getLogger(__name__)

_llm_instance = None

class LLMProvider(str, Enum):
    """Enum for LLM providers."""
    DEEPSEEK = "deepseek"
    OPENAI = "openai"
    MOCK = "mock"

class MockLLM(Runnable):
    """
    A simple mock LLM for testing purposes
    """
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
    
    def invoke(self, prompt, **kwargs):
        """Mock invoke method that returns a fixed response for testing"""
        return "This is a mock response from the LLM for testing purposes."
    
    async def ainvoke(self, prompt, **kwargs):
        """Mock async invoke method that returns a fixed response for testing"""
        return "This is a mock async response from the LLM for testing purposes."

def create_llm_chain(prompt_template: Union[str, PromptTemplate], output_parser=None):
    """Create an LLM chain with the specified prompt template and output parser.
    
    Args:
        prompt_template: The template for the prompt. Can be a string or a PromptTemplate object.
        output_parser: Optional output parser. Defaults to StrOutputParser.
        
    Returns:
        A runnable LLM chain.
    """
    if output_parser is None:
        output_parser = StrOutputParser()
        
    llm = get_llm_instance()
    
    # Handle both string and PromptTemplate inputs
    if isinstance(prompt_template, str):
        prompt = PromptTemplate.from_template(prompt_template)
    else:
        # Assume it's already a PromptTemplate
        prompt = prompt_template
    
    chain = (
        {"input": RunnablePassthrough()}
        | prompt
        | llm
        | output_parser
    )
    
    return chain

def monkeypatch_pydantic_validator():
    """
    Apply a monkey patch to fix the duplicate validator issue in langchain.
    
    This patches the _prepare_validator function in pydantic to always set allow_reuse=True
    for the ChatOpenAI.validate_environment validator.
    """
    try:
        # First, try to import the specific validator function to patch
        if "pydantic.v1.class_validators" in sys.modules:
            original_prepare_validator = sys.modules["pydantic.v1.class_validators"]._prepare_validator
            
            def patched_prepare_validator(f, allow_reuse):
                # Force allow_reuse=True for the ChatOpenAI validator
                if f.__qualname__.endswith('validate_environment') and 'openai' in f.__module__:
                    allow_reuse = True
                return original_prepare_validator(f, allow_reuse)
            
            # Apply the patch
            sys.modules["pydantic.v1.class_validators"]._prepare_validator = patched_prepare_validator
            return True
    except Exception as e:
        logger.error(f"Failed to apply pydantic validator patch: {str(e)}")
        return False

def get_llm_instance():
    """
    Get the appropriate LLM instance based on settings.
    
    The function applies a monkey patch to fix duplicate validator issues in langchain,
    then initializes and returns the appropriate LLM instance.
    """
    # Apply the monkey patch to fix the duplicate validator issue
    patch_success = monkeypatch_pydantic_validator()
    
    # For testing, return a mock LLM if in test mode
    if settings.TESTING:
        return MockLLM()
    
    try:
        # Try to get the configured provider, default to OPENAI if not specified
        provider = getattr(settings, "LLM_PROVIDER", LLMProvider.OPENAI)
        
        if provider == LLMProvider.DEEPSEEK:
            try:
                # We need to lazy import to avoid the validator issue
                from langchain_community.chat_models import ChatDeepseek
                
                return ChatDeepseek(
                    api_key=settings.DEEPSEEK_API_KEY,
                    model_name="deepseek-chat",
                    temperature=0.7
                )
            except ImportError as e:
                logger.warning(f"DeepSeek model requested but not available: {str(e)}. Using fallback.")
                # Fall back to OpenAI
                provider = LLMProvider.OPENAI
        
        if provider == LLMProvider.OPENAI:
            # Lazy import after applying the patch
            from langchain_community.chat_models import ChatOpenAI
            
            return ChatOpenAI(
                api_key=settings.OPENAI_API_KEY,
                model_name="gpt-3.5-turbo",
                temperature=0.7
            )
    
    except Exception as e:
        logger.error(f"Failed to initialize LLM instance: {str(e)}")
        raise AIServiceError(f"Failed to initialize LLM: {str(e)}")

def reset_llm_instance() -> None:
    """Reset the language model instance."""
    global _llm_instance
    _llm_instance = None
