"""Test script for the authentication mechanism.

This script tests authentication by sending a request to the /api/v1/deals/share/auth-test endpoint.
"""

import asyncio
import httpx
import traceback
import json

async def test_auth():
    """Test authentication by making a request to the auth-test endpoint."""
    client = httpx.AsyncClient(base_url='http://localhost:8000')
    headers = {'Authorization': 'Bearer test_token'}
    
    try:
        print("\n===== Testing Authentication =====")
        print("Making request to auth-test endpoint...")
        response = await client.get('/api/v1/deals/share/auth-test', headers=headers)
        
        print(f'Response status: {response.status_code}')
        try:
            print(f'Response body: {response.text}')
        except Exception as e:
            print(f"Error reading response body: {str(e)}")
        
        if response.status_code == 200:
            print("✅ Authentication test successful")
        else:
            print("❌ Authentication test failed")
            
        # Also test the share endpoint
        print("\n===== Testing Share Endpoint =====")
        data = {
            "content_type": "deal",
            "content_id": "00000000-0000-4000-a000-000000000000",  # Test UUID
            "title": "Test Share",
            "description": "Testing the share functionality",
            "visibility": "public"
        }
        
        print(f"Sending share request with data: {json.dumps(data)}")
        print(f"Headers: {headers}")
        share_response = await client.post('/api/v1/deals/share', json=data, headers=headers)
        
        print(f'Share response status: {share_response.status_code}')
        try:
            print(f'Share response body: {share_response.text}')
        except Exception as e:
            print(f"Error reading share response body: {str(e)}")
            
    except Exception as e:
        print(f"Error during testing: {str(e)}")
        traceback.print_exc()
    finally:
        await client.aclose()

if __name__ == "__main__":
    asyncio.run(test_auth()) 