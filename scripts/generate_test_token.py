import sys
import os
import json
import time
from datetime import datetime, timedelta
from jose import jwt

# Add the parent directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the settings - use config instead of settings
from core.config import settings

def create_test_token(user_id="00000000-0000-4000-a000-000000000000", expires_in_seconds=30):
    """Create a test token that expires in a short time."""
    # Current timestamp
    now = int(time.time())
    
    # Set expiration time to the future
    expiry = now + expires_in_seconds
    
    # Create token payload
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": expiry,
        "type": "access_token",
        "jti": "test-token-id-12345",
    }
    
    # Create token
    token = jwt.encode(
        payload, 
        "test_jwt_secret_key_for_testing_only",  # Use test secret key
        algorithm=settings.JWT_ALGORITHM
    )
    
    # Calculate expiry time in human-readable format
    expiry_time = datetime.fromtimestamp(expiry).strftime('%Y-%m-%d %H:%M:%S')
    
    return {
        "token": token,
        "expires_at": expiry_time,
        "expires_in_seconds": expires_in_seconds
    }

if __name__ == "__main__":
    # Generate the token
    token_info = create_test_token()
    
    # Print the token info as JSON
    print(json.dumps(token_info, indent=2))
    
    print("\nUse this token for testing:")
    print(f"Authorization: Bearer {token_info['token']}")
    print(f"\nThis token will expire at {token_info['expires_at']} (in {token_info['expires_in_seconds']} seconds)") 