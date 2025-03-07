import os
import sys
import logging
import asyncio
import json
from datetime import datetime
from uuid import uuid4

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the parent directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.utils.llm import get_llm_instance, LLMProvider, reset_llm_instance

async def test_llm_provider():
    """Test the LLM provider configuration and verify DeepSeek is prioritized"""
    # Print environment variables
    logger.info('Testing LLM Provider Configuration')
    logger.info(f'DEEPSEEK_API_KEY exists: {bool(os.environ.get("DEEPSEEK_API_KEY"))}')
    logger.info(f'OPENAI_API_KEY exists: {bool(os.environ.get("OPENAI_API_KEY"))}')
    
    # First test with OPENAI_API_KEY removed to force DeepSeek
    if "OPENAI_API_KEY" in os.environ:
        openai_key = os.environ["OPENAI_API_KEY"]
        # Temporarily remove OpenAI key
        del os.environ["OPENAI_API_KEY"]
        
        # Set a test DeepSeek key
        os.environ["DEEPSEEK_API_KEY"] = "test_deepseek_key"
        
        # Reset any existing instance
        reset_llm_instance()
        
        # Set LLM_PROVIDER to deepseek to ensure it's used
        os.environ['LLM_PROVIDER'] = 'deepseek'
        
        # Get the LLM instance
        logger.info("Testing with DeepSeek key only")
        try:
            llm = get_llm_instance()
            logger.info(f'LLM instance type: {type(llm).__name__}')
            logger.info(f'LLM provider: {llm.provider if hasattr(llm, "provider") else "Unknown"}')
            logger.info(f'LLM model: {llm.model_name if hasattr(llm, "model_name") else "Unknown"}')
        except Exception as e:
            logger.error(f"Error getting LLM instance with DeepSeek: {str(e)}")
        
        # Restore OpenAI key
        os.environ["OPENAI_API_KEY"] = openai_key
    
    # Test with both keys available
    os.environ["DEEPSEEK_API_KEY"] = "test_deepseek_key"
    
    # Reset any existing instance
    reset_llm_instance()
    
    # Set LLM_PROVIDER to deepseek to ensure it's used
    os.environ['LLM_PROVIDER'] = 'deepseek'
    
    # Get the LLM instance
    logger.info("Testing with both DeepSeek and OpenAI keys")
    try:
        llm = get_llm_instance()
        logger.info(f'LLM instance type: {type(llm).__name__}')
        logger.info(f'LLM provider: {llm.provider if hasattr(llm, "provider") else "Unknown"}')
        logger.info(f'LLM model: {llm.model_name if hasattr(llm, "model_name") else "Unknown"}')
    except Exception as e:
        logger.error(f"Error getting LLM instance with both keys: {str(e)}")
    
    # Test with force set to OpenAI
    reset_llm_instance()
    os.environ['LLM_PROVIDER'] = 'openai'
    logger.info("Testing with LLM_PROVIDER explicitly set to OpenAI")
    try:
        llm = get_llm_instance()
        logger.info(f'LLM instance type when OpenAI forced: {type(llm).__name__}')
    except Exception as e:
        logger.error(f"Error getting OpenAI LLM instance: {str(e)}")
    
    # Set back to DeepSeek
    reset_llm_instance()
    os.environ['LLM_PROVIDER'] = 'deepseek'
    logger.info("Testing final configuration with LLM_PROVIDER set to DeepSeek")
    try:
        llm = get_llm_instance()
        logger.info(f'Final LLM instance type: {type(llm).__name__}')
        if hasattr(llm, "provider"):
            logger.info(f'Final LLM provider: {llm.provider}')
    except Exception as e:
        logger.error(f"Error getting final LLM instance: {str(e)}")
        
    logger.info("LLM provider testing complete")

if __name__ == '__main__':
    asyncio.run(test_llm_provider())
