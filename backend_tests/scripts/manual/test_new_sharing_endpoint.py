"""Test script for the new API-based public sharing endpoint.

This script tests the new /api/v1/shared-public/{share_id} endpoint
to ensure it correctly handles public shared content requests.
"""

import asyncio
import httpx
import json
import uuid
from datetime import datetime, timezone
import sys

BASE_URL = "http://localhost:8000"
TEST_TOKEN = "test_token123"  # Use a test token for authentication


async def create_test_share():
    """Create a test share to get a share ID for testing."""
    
    # First create a test share
    print("Creating test share...")
    
    # Generate a UUID for content_id
    content_id = str(uuid.uuid4())
    
    # Define the request payload with all required fields
    share_data = {
        "content_type": "deal",
        "title": "Test Share for New Endpoint",
        "description": "Testing the new /api/v1/shared-public/ endpoint",
        "content_id": content_id,
        "visibility": "public",
        "include_personal_notes": False
    }
    
    # Create the share
    async with httpx.AsyncClient() as client:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {TEST_TOKEN}"
        }
        
        try:
            response = await client.post(
                f"{BASE_URL}/api/v1/deals/share/test",
                json=share_data,
                headers=headers
            )
            
            # Check if the request was successful
            if response.status_code == 200:
                share_response = response.json()
                share_id = share_response.get("share_id")
                share_link = share_response.get("shareable_link")
                
                print(f"✅ Successfully created test share with ID: {share_id}")
                print(f"📎 Share link: {share_link}")
                
                return share_id
            else:
                print(f"❌ Failed to create test share: {response.status_code}")
                print(f"Response: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error creating test share: {str(e)}")
            return None


async def test_old_endpoint(share_id):
    """Test the old /shared/{share_id} endpoint (should redirect)."""
    
    print("\nTesting old endpoint (should redirect)...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{BASE_URL}/shared/{share_id}"
            )
            
            print(f"Old endpoint status code: {response.status_code}")
            print(f"Headers: {response.headers}")
            if response.status_code == 200:
                print("✅ Old endpoint is working (or redirecting)")
            else:
                print(f"❌ Old endpoint returned non-200 status: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Error testing old endpoint: {str(e)}")


async def test_new_endpoint(share_id):
    """Test the new /api/v1/shared-public/{share_id} endpoint."""
    
    print("\nTesting new endpoint...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{BASE_URL}/api/v1/shared-public/{share_id}"
            )
            
            if response.status_code == 200:
                content = response.json()
                print("✅ New endpoint is working!")
                print(f"Title: {content.get('title')}")
                print(f"Content type: {content.get('content_type')}")
                print(f"View count: {content.get('view_count')}")
            else:
                print(f"❌ New endpoint returned non-200 status: {response.status_code}")
                print(f"Response: {response.text}")
                
        except Exception as e:
            print(f"❌ Error testing new endpoint: {str(e)}")


async def run_tests():
    """Run all tests."""
    
    print("=" * 50)
    print("TESTING NEW API SHARING ENDPOINT")
    print("=" * 50)
    
    # Create a test share
    share_id = await create_test_share()
    
    if not share_id:
        print("Cannot continue tests without a valid share ID.")
        sys.exit(1)
    
    # Test the old endpoint
    await test_old_endpoint(share_id)
    
    # Test the new endpoint
    await test_new_endpoint(share_id)
    
    print("\n" + "=" * 50)
    print("TESTS COMPLETED")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(run_tests()) 