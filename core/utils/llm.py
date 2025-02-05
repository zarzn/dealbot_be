"""LLM utility module.

This module provides language model utilities for the AI Agentic Deals System.
"""

import logging
from typing import Optional

from langchain_community.chat_models import ChatOpenAI
from langchain.llms.base import BaseLLM

from core.config import settings
from core.exceptions import AIServiceError

logger = logging.getLogger(__name__)

_llm_instance: Optional[BaseLLM] = None

def get_llm_instance() -> BaseLLM:
    """Get or create a language model instance."""
    global _llm_instance
    
    if _llm_instance is not None:
        return _llm_instance
    
    try:
        if settings.LLM_MODEL.lower() == "openai":
            if not settings.OPENAI_API_KEY:
                raise AIServiceError("OpenAI API key not configured")
            _llm_instance = ChatOpenAI(
                model_name="gpt-4",
                openai_api_key=settings.OPENAI_API_KEY,
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=settings.LLM_MAX_TOKENS
            )
        else:
            raise AIServiceError(f"Unsupported LLM model: {settings.LLM_MODEL}")
        
        return _llm_instance
    except Exception as e:
        logger.error(f"Failed to initialize LLM instance: {str(e)}")
        raise AIServiceError(f"Failed to initialize LLM: {str(e)}")

def reset_llm_instance() -> None:
    """Reset the language model instance."""
    global _llm_instance
    _llm_instance = None
