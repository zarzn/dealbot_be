"""
Test script for DeepSeek LLM integration.

This script verifies that the DeepSeek LLM is properly configured and can be used
in the AI Agentic Deals System.
"""

import os
import sys
import traceback

def test_deepseek():
    """Test DeepSeek integration."""
    # Set up environment
    os.environ["LLM_PROVIDER"] = "deepseek"
    os.environ["LLM_MODEL"] = "deepseek-chat"
    
    # Clear any existing LLM instance
    if "_llm_instance" in globals():
        print("Resetting global LLM instance")
        globals()["_llm_instance"] = None
    
    # Log available keys (masked for security)
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    
    if deepseek_key:
        print(f"DeepSeek API key available: {deepseek_key[:5]}...{deepseek_key[-5:]}")
    else:
        print("DeepSeek API key not available")
    
    if openai_key:
        print(f"OpenAI API key available: {openai_key[:5]}...{openai_key[-5:]}")
    else:
        print("OpenAI API key not available")
    
    # We need to get the current settings from core.config
    from core.config import settings
    # Print current settings for LLM
    print(f"Current settings:")
    print(f"  LLM_PROVIDER: {settings.LLM_PROVIDER}")
    print(f"  LLM_MODEL: {settings.LLM_MODEL}")
    
    # Override settings if needed
    if hasattr(settings, "LLM_PROVIDER"):
        settings.LLM_PROVIDER = "deepseek"
    if hasattr(settings, "LLM_MODEL"):
        settings.LLM_MODEL = "deepseek-chat"
    
    print(f"Updated settings:")
    print(f"  LLM_PROVIDER: {settings.LLM_PROVIDER}")
    print(f"  LLM_MODEL: {settings.LLM_MODEL}")
    
    # Import the LLM module
    print("Importing LLM module")
    try:
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from core.utils.llm import get_llm_instance, reset_llm_instance
        
        # Reset any existing instance
        print("Resetting LLM instance")
        reset_llm_instance()
        
        # Get a new LLM instance
        print("Getting LLM instance")
        llm = get_llm_instance()
        
        # Log the LLM instance details
        print(f"LLM instance type: {type(llm).__name__}")
        if hasattr(llm, "model_name"):
            print(f"LLM model name: {llm.model_name}")

        # Test the LLM with a simple prompt
        print("Testing LLM with a simple prompt")
        prompt = "What is your name and what model are you?"
        
        # Convert to proper messages format if needed
        if hasattr(llm, "client") and "openai" in str(type(llm.client)).lower():
            print("Using OpenAI-style client")
            from langchain_core.messages import HumanMessage, SystemMessage
            messages = [
                SystemMessage(content="You are a helpful assistant."),
                HumanMessage(content=prompt)
            ]
            response = llm.invoke(messages)
        else:
            print("Using direct text prompt")
            response = llm.invoke(prompt)
        
        print(f"LLM response: {str(response)[:200]}...")
        print("DeepSeek test completed successfully")
        return True
    except Exception as e:
        print(f"Error: {str(e)}")
        traceback.print_exc()
        return False 

if __name__ == "__main__":
    # Run the test
    print("Running DeepSeek test...")
    success = test_deepseek()
    print(f"Test {'succeeded' if success else 'failed'}")
    sys.exit(0 if success else 1) 