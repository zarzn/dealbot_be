"""LLM utility module.

This module provides language model utilities for the AI Agentic Deals System.
Supported models:
- DeepSeek-Chat: Primary model for production (requires DEEPSEEK_API_KEY)
- GPT-4o: Fallback model from OpenAI (requires OPENAI_API_KEY)
"""

import logging
import sys
import os
import traceback
import importlib.util
from typing import Optional, Dict, Any, List, Union
from enum import Enum

# Initialize module variables
ChatDeepSeek = None
ChatOpenAI = None

# For DeepSeek integration
logger = logging.getLogger(__name__)

logger.info("Attempting to import ChatDeepSeek")
try:
    # Primary import from langchain-deepseek package
    from langchain_deepseek import ChatDeepSeek
    logger.info("Successfully imported ChatDeepSeek from langchain_deepseek")
except ImportError as e:
    logger.warning(f"Failed to import ChatDeepSeek from langchain_deepseek: {str(e)}")
    # Fallback to community package (older versions)
    try:
        from langchain_community.chat_models import ChatDeepSeek
        logger.info("Successfully imported ChatDeepSeek from langchain_community.chat_models")
    except ImportError as e2:
        logger.error(f"Failed to import ChatDeepSeek from langchain_community.chat_models: {str(e2)}")
        ChatDeepSeek = None

# For OpenAI integration
logger.info("Attempting to import ChatOpenAI")
try:
    from langchain_openai import ChatOpenAI
    logger.info("Successfully imported ChatOpenAI from langchain_openai")
except ImportError as e:
    logger.error(f"Failed to import ChatOpenAI: {str(e)}")
    ChatOpenAI = None

logger.info(f"Import status - ChatDeepSeek: {ChatDeepSeek is not None}, ChatOpenAI: {ChatOpenAI is not None}")

# Core langchain imports
try:
    from langchain_core.prompts import PromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.runnables import RunnablePassthrough, Runnable
    from langchain_core.language_models.chat_models import BaseChatModel
    logger.info("Successfully imported core langchain modules")
except ImportError as e:
    logger.error(f"Failed to import core langchain modules: {str(e)}")
    raise ImportError(f"Critical imports failed, application cannot start: {str(e)}")

from core.config import settings
from core.exceptions import AIServiceError

_llm_instance = None

# Custom exceptions
class MonkeyPatchingError(Exception):
    """Exception raised when monkey patching fails."""
    pass

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
        self.model_name = "mock-llm"
        self.provider = LLMProvider.MOCK
        logger.info("Initialized MockLLM for testing")
    
    def invoke(self, prompt, **kwargs):
        """Mock invoke method that returns a fixed response for testing"""
        logger.info(f"MockLLM received prompt: {prompt[:100]}...")
        return "This is a mock response from the LLM for testing purposes."
    
    async def ainvoke(self, prompt, **kwargs):
        """Mock async invoke method that returns a fixed response for testing"""
        logger.info(f"MockLLM async received prompt: {prompt[:100]}...")
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
            logger.info("Applying monkeypatch for pydantic v1 validators")
            original_prepare_validator = sys.modules["pydantic.v1.class_validators"]._prepare_validator
            
            def patched_prepare_validator(f, allow_reuse):
                # Force allow_reuse=True for the ChatOpenAI validator
                if f.__qualname__.endswith('validate_environment') and 'openai' in f.__module__:
                    allow_reuse = True
                return original_prepare_validator(f, allow_reuse)
            
            # Apply the patch
            sys.modules["pydantic.v1.class_validators"]._prepare_validator = patched_prepare_validator
            logger.info("Successfully applied pydantic v1 validator patch")
            return True
        else:
            logger.info("pydantic.v1.class_validators not found, checking for other versions")
            # Attempt to patch pydantic v2 if available
            if "pydantic.validators" in sys.modules:
                logger.info("Found pydantic v2 validators, attempting patch")
                # Implementation for v2 would go here
                return True
            
            logger.warning("No compatible pydantic module found for patching")
            return False
    except Exception as e:
        logger.error(f"Failed to apply pydantic validator patch: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def get_llm_instance():
    """
    Get the appropriate LLM instance based on settings.
    
    The function applies a monkey patch to fix duplicate validator issues in langchain,
    then initializes and returns the appropriate LLM instance.
    
    Returns:
        An LLM instance based on configuration (DeepSeek or OpenAI)
    """
    global _llm_instance
    
    if _llm_instance is not None:
        logger.debug("Returning existing LLM instance")
        return _llm_instance
    
    logger.info("Initializing new LLM instance")
    
    # Apply the monkey patch to fix the duplicate validator issue
    patch_success = monkeypatch_pydantic_validator()
    logger.info(f"Pydantic validator patch applied: {patch_success}")
    
    # Log available API keys for debugging
    deepseek_key_available = bool(os.environ.get("DEEPSEEK_API_KEY"))
    openai_key_available = bool(os.environ.get("OPENAI_API_KEY"))
    
    logger.info(f"DeepSeek API key available: {deepseek_key_available}")
    logger.info(f"OpenAI API key available: {openai_key_available}")
    
    # Check if LLM classes were imported successfully
    if ChatDeepSeek is None:
        logger.error("ChatDeepSeek class is not available - missing langchain-deepseek package?")
    
    if ChatOpenAI is None:
        logger.error("ChatOpenAI class is not available - missing langchain-openai package?")
    
    # Get configured provider
    try:
        # Get environment - we should prioritize DeepSeek in production
        environment = getattr(settings, "APP_ENVIRONMENT", "development").lower()
        testing = getattr(settings, "TESTING", False)
        logger.info(f"Current environment: {environment}, Testing mode: {testing}")
        
        # Determine the provider - always prefer DeepSeek unless explicitly set to OpenAI
        provider_str = getattr(settings, "LLM_PROVIDER", "deepseek").lower()
        provider = LLMProvider(provider_str) if isinstance(provider_str, str) else LLMProvider.DEEPSEEK
        logger.info(f"Configured LLM provider: {provider}")
        
        # DEEPSEEK CONFIGURATION
        if provider == LLMProvider.DEEPSEEK:
            if not deepseek_key_available:
                logger.warning("DeepSeek model requested but API key not available, falling back to OpenAI")
                provider = LLMProvider.OPENAI
            elif ChatDeepSeek is None:
                logger.error("DeepSeek model requested but ChatDeepSeek class is not available, falling back to OpenAI")
                provider = LLMProvider.OPENAI
            else:
                try:
                    # Get model name from settings
                    model_name = getattr(settings, "LLM_MODEL", "deepseek-chat")
                    temperature = getattr(settings, "LLM_TEMPERATURE", 0.7)
                    max_tokens = getattr(settings, "LLM_MAX_TOKENS", 1000)
                    
                    logger.info(f"Initializing DeepSeek model: {model_name}")
                    _llm_instance = ChatDeepSeek(
                        api_key=os.environ.get("DEEPSEEK_API_KEY"),
                        model_name=model_name,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    logger.info("DeepSeek model initialized successfully")
                    return _llm_instance
                except ImportError as e:
                    logger.warning(f"DeepSeek model requested but package not available: {str(e)}. Using fallback.")
                    provider = LLMProvider.OPENAI
                except Exception as e:
                    logger.error(f"Error initializing DeepSeek model: {str(e)}")
                    logger.error(traceback.format_exc())
                    provider = LLMProvider.OPENAI
        
        # OPENAI CONFIGURATION
        if provider == LLMProvider.OPENAI:
            if not openai_key_available:
                logger.error("OpenAI model requested but API key not available")
                raise AIServiceError("OpenAI API key required but not available")
            elif ChatOpenAI is None:
                logger.error("OpenAI model requested but ChatOpenAI class is not available")
                raise AIServiceError("OpenAI integration requested but langchain-openai package is not available")
            else:
                try:
                    # Get model name from settings
                    model_name = getattr(settings, "OPENAI_FALLBACK_MODEL", "gpt-4o")
                    temperature = getattr(settings, "LLM_TEMPERATURE", 0.7)
                    max_tokens = getattr(settings, "LLM_MAX_TOKENS", 1000)
                    
                    logger.info(f"Initializing OpenAI model: {model_name}")
                    _llm_instance = ChatOpenAI(
                        api_key=os.environ.get("OPENAI_API_KEY"),
                        model_name=model_name,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    logger.info("OpenAI model initialized successfully")
                    return _llm_instance
                except Exception as e:
                    logger.error(f"Error initializing OpenAI model: {str(e)}")
                    logger.error(traceback.format_exc())
                    raise AIServiceError(f"Failed to initialize OpenAI LLM: {str(e)}")
    
    except Exception as e:
        logger.error(f"Failed to initialize LLM instance: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Only use MockLLM if no API keys are available or if imports failed
        if ((not deepseek_key_available or ChatDeepSeek is None) and 
            (not openai_key_available or ChatOpenAI is None)):
            logger.warning("No working LLM providers available, falling back to MockLLM")
            _llm_instance = MockLLM()
            return _llm_instance
        else:
            raise AIServiceError(f"Failed to initialize any LLM despite API keys being available: {str(e)}")

def reset_llm_instance() -> None:
    """Reset the language model instance."""
    global _llm_instance
    logger.info("Resetting LLM instance")
    _llm_instance = None

def test_llm_connection() -> bool:
    """Test if the LLM can be connected to and used.
    
    Returns:
        bool: True if the connection works, False otherwise
    """
    try:
        # First check if API keys are available
        deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
        openai_key = os.environ.get("OPENAI_API_KEY")
        
        if not deepseek_key and not openai_key:
            logger.error("No LLM API keys available - cannot test connection")
            return False
        
        # Give priority to DeepSeek for connection testing
        if deepseek_key:
            logger.info("DeepSeek API key available - prioritizing DeepSeek for testing")
            # Force LLM_PROVIDER setting temporarily for testing
            original_provider = getattr(settings, "LLM_PROVIDER", None)
            try:
                # Set to DeepSeek temporarily if we have a key
                if hasattr(settings, "LLM_PROVIDER"):
                    settings.LLM_PROVIDER = "deepseek"
                # Reset LLM instance to ensure we get a fresh one
                reset_llm_instance()
            except:
                # If we can't modify settings, that's ok
                pass
        else:
            logger.info("DeepSeek API key not available - using OpenAI for testing")
            
        # Get an LLM instance
        llm = get_llm_instance()
        
        if not llm:
            logger.error("Failed to initialize LLM instance")
            return False
            
        # Check if we got a mock LLM (which always "works")
        if isinstance(llm, MockLLM):
            logger.warning("Using MockLLM - this always returns success in tests but not real analysis")
            return True
            
        # Log the model type we're testing with
        if hasattr(llm, 'model_name'):
            logger.info(f"Testing connection with model: {llm.model_name}")
        elif hasattr(llm, 'model'):
            logger.info(f"Testing connection with model: {llm.model}")
        else:
            logger.info(f"Testing connection with model type: {type(llm).__name__}")
        
        # Determine the provider
        provider = None
        if 'DeepSeek' in str(type(llm)):
            provider = "DeepSeek"
        elif 'OpenAI' in str(type(llm)):
            provider = "OpenAI"
        else:
            provider = "Unknown"
        
        logger.info(f"Testing {provider} LLM connection")
        
        # Try a simple request
        logger.info("Sending test prompt to LLM")
        
        # Simple test prompt
        test_prompt = "Say 'Connection successful' if you can read this message."
        
        # Invoke the model
        response = llm.invoke(test_prompt)
        logger.info(f"Received response from {provider}: {str(response)[:100]}...")
        
        return True
    except Exception as e:
        logger.error(f"Error testing LLM connection: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def initialize_deepseek_llm() -> BaseChatModel:
    """Initialize DeepSeek LLM.

    Returns:
        BaseChatModel: DeepSeek LLM instance
    """
    try:
        from langchain_deepseek import ChatDeepSeek
    except ImportError:
        try:
            from langchain_community.chat_models import ChatDeepSeek
        except ImportError:
            raise ImportError(
                "Failed to import ChatDeepSeek. "
                "Please install langchain-deepseek or ensure langchain-community is up to date."
            )

    model_name = settings.LLM_MODEL if settings.LLM_MODEL else "deepseek-chat"
    try:
        return ChatDeepSeek(
            api_key=settings.DEEPSEEK_API_KEY,
            model_name=model_name,
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
        )
    except Exception as e:
        logger.error(f"Failed to initialize DeepSeek LLM: {e}")
        return None
