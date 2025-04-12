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
import threading
from typing import Optional, Dict, Any, List, Union
from enum import Enum
import time

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
_llm_instance_lock = threading.Lock()

# Custom exceptions
class MonkeyPatchingError(Exception):
    """Exception raised when monkey patching fails."""
    pass

class LLMProvider(str, Enum):
    """Enum for LLM providers."""
    DEEPSEEK = "deepseek"
    OPENAI = "openai"

def create_llm_chain(prompt_template: Union[str, PromptTemplate], output_parser=None):
    """Create an LLM chain with the specified prompt template and output parser.
    
    Args:
        prompt_template: The template for the prompt. Can be a string or a PromptTemplate object.
        output_parser: Optional output parser. Defaults to StrOutputParser.
        
    Returns:
        A runnable LLM chain or None if no LLM is available.
    """
    if output_parser is None:
        output_parser = StrOutputParser()
        
    llm = get_llm_instance()
    
    if llm is None:
        logger.warning("Cannot create LLM chain: No LLM instance available")
        return None
    
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
    """Get a language model instance for AI functionalities.
    
    This function implements the singleton pattern to ensure only one LLM
    instance is created for the application lifetime.
    
    Returns:
        An instance of a language model to use for AI functions or None if no LLM is available
    """
    global _llm_instance
    
    # Thread safety for LLM instance creation
    with _llm_instance_lock:
        # Double-check pattern: Return existing instance if available
        if _llm_instance is not None:
            logger.debug("Returning existing LLM instance")
            return _llm_instance
            
        # Set retry count for robustness
        max_retries = 2
        retry_count = 0
        last_error = None
        
        while retry_count <= max_retries:
            try:
                # Get environment and testing status
                environment = getattr(settings, "ENVIRONMENT", "development")
                testing = getattr(settings, "TESTING", False)
                
                # Check if API keys are available - try both environment variables and settings
                openai_key = None
                if "OPENAI_API_KEY" in os.environ and os.environ.get("OPENAI_API_KEY"):
                    openai_key = os.environ.get("OPENAI_API_KEY")
                    logger.info("Found OpenAI API key in environment variables")
                elif hasattr(settings, "OPENAI_API_KEY") and settings.OPENAI_API_KEY:
                    try:
                        openai_key = settings.OPENAI_API_KEY.get_secret_value()
                        logger.info("Found OpenAI API key in settings")
                    except:
                        openai_key = str(settings.OPENAI_API_KEY)
                        logger.info("Found OpenAI API key in settings (not secret)")
                        
                deepseek_key = None
                if "DEEPSEEK_API_KEY" in os.environ and os.environ.get("DEEPSEEK_API_KEY"):
                    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
                    logger.info("Found DeepSeek API key in environment variables")
                elif hasattr(settings, "DEEPSEEK_API_KEY") and settings.DEEPSEEK_API_KEY:
                    try:
                        deepseek_key = settings.DEEPSEEK_API_KEY.get_secret_value()
                        logger.info("Found DeepSeek API key in settings")
                    except:
                        deepseek_key = str(settings.DEEPSEEK_API_KEY)
                        logger.info("Found DeepSeek API key in settings (not secret)")
                
                # Check if keys were found
                openai_key_available = openai_key is not None
                deepseek_key_available = deepseek_key is not None
                
                # Log environment info for debugging
                logger.info(f"Initializing LLM (attempt {retry_count+1}/{max_retries+1}) - Environment: {environment}, Testing: {testing}")
                logger.info(f"API keys available - DeepSeek: {deepseek_key_available}, OpenAI: {openai_key_available}")
                
                # If no API keys are available, return None
                if not deepseek_key_available and not openai_key_available:
                    logger.warning("No LLM API keys available. AI functionality will be disabled.")
                    return None
                
                # Set default provider
                provider = None
                
                # Import optional dependencies - with improved error handling
                try:
                    from langchain_core.runnables import Runnable
                    
                    # Determine the provider - always prefer DeepSeek unless explicitly set to OpenAI
                    provider_str = getattr(settings, "LLM_PROVIDER", "deepseek").lower()
                    try:
                        provider = LLMProvider(provider_str) if isinstance(provider_str, str) else LLMProvider.DEEPSEEK
                        logger.info(f"Configured LLM provider: {provider}")
                    except ValueError:
                        logger.warning(f"Invalid LLM provider: {provider_str}, falling back to DeepSeek")
                        provider = LLMProvider.DEEPSEEK
                        
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
                                
                                # Use lower temperature for more deterministic responses
                                # Use a fixed low temperature of 0.2 to ensure consistent outputs
                                temperature = 0.2
                                
                                # Use lower max_tokens to speed up responses
                                # Limit to 250 tokens which is sufficient for structured outputs
                                max_tokens = 250
                                
                                logger.info(f"Initializing DeepSeek model: {model_name} with max_tokens={max_tokens}, temperature={temperature}")
                                llm = ChatDeepSeek(
                                    api_key=os.environ.get("DEEPSEEK_API_KEY"),
                                    model_name=model_name,
                                    temperature=temperature,
                                    max_tokens=max_tokens,
                                    request_timeout=10  # Reduced timeout to 10 seconds for faster failures
                                )
                                logger.info("DeepSeek model initialized successfully")
                                _llm_instance = llm
                                return _llm_instance
                            except Exception as e:
                                logger.warning(f"DeepSeek model initialization failed: {str(e)}. Trying OpenAI fallback.")
                                logger.warning(traceback.format_exc())
                                provider = LLMProvider.OPENAI
                    
                    # OPENAI CONFIGURATION
                    if provider == LLMProvider.OPENAI:
                        if not openai_key_available:
                            logger.warning("OpenAI model requested but API key not available, AI functionality will be disabled")
                            return None
                        elif ChatOpenAI is None:
                            logger.error("OpenAI model requested but ChatOpenAI class is not available, AI functionality will be disabled")
                            return None
                        else:
                            try:
                                # Get model name from settings
                                model_name = getattr(settings, "OPENAI_MODEL", "gpt-3.5-turbo")
                                
                                # Use fixed low temperature for more deterministic responses
                                temperature = 0.2
                                
                                # Use fixed lower max_tokens to speed up responses
                                max_tokens = 250
                                
                                logger.info(f"Initializing OpenAI model: {model_name} with max_tokens={max_tokens}, temperature={temperature}")
                                llm = ChatOpenAI(
                                    api_key=os.environ.get("OPENAI_API_KEY"),
                                    model_name=model_name,
                                    temperature=temperature,
                                    max_tokens=max_tokens,
                                    request_timeout=10  # Reduced timeout to 10 seconds
                                )
                                logger.info("OpenAI model initialized successfully")
                                _llm_instance = llm
                                return _llm_instance
                            except Exception as e:
                                logger.warning(f"OpenAI model initialization failed: {str(e)}. AI functionality will be disabled.")
                                logger.warning(traceback.format_exc())
                                return None
                except Exception as e:
                    logger.error(f"Error during dependency imports: {str(e)}")
                    logger.error(traceback.format_exc())
                    return None
                
                # If we get here, we couldn't initialize any LLM
                logger.warning("Failed to initialize any LLM. AI functionality will be disabled.")
                return None
                
            except Exception as e:
                last_error = e
                logger.error(f"LLM initialization attempt {retry_count+1}/{max_retries+1} failed: {str(e)}")
                logger.error(traceback.format_exc())
                retry_count += 1
                if retry_count <= max_retries:
                    # Exponential backoff for retries (0.5s, 1s)
                    retry_delay = 0.5 * (2 ** (retry_count - 1))
                    logger.info(f"Retrying LLM initialization in {retry_delay:.1f} seconds...")
                    time.sleep(retry_delay)
        
        # All retries failed
        logger.error(f"All LLM initialization attempts failed: {str(last_error)}")
        logger.error("AI functionality will be disabled.")
        return None

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

def initialize_deepseek_llm() -> Optional[BaseChatModel]:
    """Initialize DeepSeek LLM.

    Returns:
        BaseChatModel: DeepSeek LLM instance or None if not available
    """
    try:
        from langchain_deepseek import ChatDeepSeek
    except ImportError:
        try:
            from langchain_community.chat_models import ChatDeepSeek
        except ImportError:
            logger.error("Failed to import ChatDeepSeek. Please install langchain-deepseek or ensure langchain-community is up to date.")
            return None

    if not settings.DEEPSEEK_API_KEY:
        logger.error("Missing DEEPSEEK_API_KEY. DeepSeek LLM initialization failed.")
        return None

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
