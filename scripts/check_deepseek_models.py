"""
Script to check available DeepSeek models.
"""

import os
import sys
import requests
import json

def main():
    # Get API key from environment variable
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("No DEEPSEEK_API_KEY found in environment variables")
        sys.exit(1)
    
    # Print the API key (masked) for debugging
    print(f"Using API key: {api_key[:5]}...{api_key[-5:]}")
    
    # Check if the models endpoint exists
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Try to get available models
        print("Checking available models...")
        response = requests.get("https://api.deepseek.com/v1/models", headers=headers)
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            models = response.json()
            print(json.dumps(models, indent=2))
        else:
            print(f"Error: {response.text}")
        
        # Try a simple completion with the correct model name
        print("\nTesting chat completion with deepseek-chat...")
        completion_data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is your name and what model are you?"}
            ],
            "max_tokens": 100
        }
        
        completion_response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=completion_data
        )
        
        print(f"Completion response status: {completion_response.status_code}")
        
        if completion_response.status_code == 200:
            completion_result = completion_response.json()
            print(json.dumps(completion_result, indent=2))
        else:
            print(f"Completion error: {completion_response.text}")
        
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    main()
