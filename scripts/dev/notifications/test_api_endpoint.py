import asyncio
import aiohttp
import json
import base64
import hmac
import hashlib
import time

def generate_test_jwt_token(user_id="0070a2a6-0d5b-475c-abd4-906f784afc39"):
    """Generate a JWT token for test purposes with the given user ID."""
    # Header
    header = {
        "alg": "HS256",
        "typ": "JWT"
    }
    
    # Payload with the specified user ID
    payload = {
        "sub": user_id,  # Test user ID
        "exp": int(time.time()) + 3600,  # 1 hour expiry
        "iat": int(time.time()),
        "type": "access"
    }
    
    # Convert to base64
    header_json = json.dumps(header).encode()
    header_b64 = base64.urlsafe_b64encode(header_json).decode().rstrip('=')
    
    payload_json = json.dumps(payload).encode()
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode().rstrip('=')
    
    # Create signature
    secret = "test_jwt_secret_key"  # Use the same test secret as backend
    message = f"{header_b64}.{payload_b64}"
    signature = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).digest()
    signature_b64 = base64.urlsafe_b64encode(signature).decode().rstrip('=')
    
    # Create token
    token = f"{header_b64}.{payload_b64}.{signature_b64}"
    return token

async def test_notifications_api():
    # Generate JWT token with test user ID
    token = generate_test_jwt_token("0070a2a6-0d5b-475c-abd4-906f784afc39")
    print(f"Generated token for test user: {token}")
    
    # API endpoint
    url = "http://localhost:8000/api/v1/notifications?page=1&limit=20"
    
    # Headers with authentication
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    try:
        # Make the API request
        async with aiohttp.ClientSession() as session:
            print(f"Making GET request to {url}")
            
            # First, try a OPTIONS request to see what's allowed
            async with session.options(url) as options_response:
                print(f"OPTIONS Response Status: {options_response.status}")
                if options_response.status == 200:
                    print("OPTIONS headers:", dict(options_response.headers))
            
            # Then make the actual GET request
            async with session.get(url, headers=headers) as response:
                print(f"Response Status: {response.status}")
                
                # Get response headers
                print("Response Headers:")
                for key, value in response.headers.items():
                    print(f"  {key}: {value}")
                
                # Get response body
                try:
                    data = await response.json()
                    print("\nResponse JSON:")
                    print(json.dumps(data, indent=2))
                    
                    # Check if we got notifications
                    if 'notifications' in data:
                        print(f"\nFound {len(data['notifications'])} notifications")
                        if len(data['notifications']) > 0:
                            print("First notification:", data['notifications'][0])
                    else:
                        print("No 'notifications' field in response")
                except Exception as e:
                    text = await response.text()
                    print(f"Failed to parse JSON: {e}")
                    print("Raw Response:", text)
    
    except Exception as e:
        print(f"Error making API request: {e}")

if __name__ == "__main__":
    print("Testing notifications API endpoint...")
    asyncio.run(test_notifications_api()) 