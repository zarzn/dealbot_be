"""
Direct test of the DeepSeek integration using LangChain.
"""

import os
import sys
import logging
import asyncio
import traceback
from pathlib import Path

# Add the parent directory to the path so we can import from backend
sys.path.append(str(Path(__file__).parent.parent))

# Set up logging - make it more verbose
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Try to import DeepSeek directly
try:
    from langchain_deepseek import ChatDeepSeek
    logger.info("Successfully imported ChatDeepSeek from langchain_deepseek")
    DEEPSEEK_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Error importing from langchain_deepseek: {e}")
    try:
        from langchain_community.chat_models import ChatDeepSeek
        logger.info("Successfully imported ChatDeepSeek from langchain_community.chat_models")
        DEEPSEEK_AVAILABLE = True
    except ImportError as e:
        logger.error(f"Error importing from langchain_community: {e}")
        logger.error("Could not import ChatDeepSeek from any package")
        DEEPSEEK_AVAILABLE = False

async def test_direct_deepseek():
    """Test the DeepSeek LLM integration directly."""
    logger.info("Testing DeepSeek LLM integration directly")
    
    # Check environment variables
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
    if deepseek_key:
        logger.info(f"DeepSeek API key available: {deepseek_key[:5]}...{deepseek_key[-5:]}")
    else:
        logger.error("DeepSeek API key not found in environment")
        return False
    
    if not DEEPSEEK_AVAILABLE:
        logger.error("DeepSeek integration not available")
        return False
    
    try:
        # Create the DeepSeek model directly
        logger.info("Creating DeepSeek model directly...")
        llm = ChatDeepSeek(
            api_key=deepseek_key,
            model_name="deepseek-chat",
            temperature=0.7,
            max_tokens=1000
        )
        logger.info(f"Direct LLM instance type: {type(llm).__name__}")
        logger.info(f"Direct LLM model name: {llm.model_name}")
        logger.info(f"Direct LLM attributes: {dir(llm)}")
        
        if hasattr(llm, "client"):
            logger.info(f"LLM client type: {type(llm.client).__name__}")
        
        # Try to generate a response
        logger.info("Testing LLM with a simple prompt")
        prompt = "What is your name and what model are you?"
        
        # Convert string to chat messages
        from langchain_core.messages import HumanMessage, SystemMessage
        messages = [
            SystemMessage(content="You are a helpful assistant."),
            HumanMessage(content=prompt)
        ]
        
        # Invoke the model
        logger.info("Invoking the model...")
        try:
            response = llm.invoke(messages)
            logger.info(f"LLM response: {response.content[:200]}...")
            logger.info("DeepSeek LLM test completed successfully")
            return True
        except Exception as e:
            logger.error(f"Error invoking the model: {e}")
            logger.error(traceback.format_exc())
            return False
    except Exception as e:
        logger.error(f"Error testing DeepSeek directly: {e}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    # Run the direct test
    print("Starting DeepSeek direct test...")
    success = asyncio.run(test_direct_deepseek())
    print(f"Test {'succeeded' if success else 'failed'}")
    sys.exit(0 if success else 1) 