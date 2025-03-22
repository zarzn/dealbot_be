"""Test script for the share functionality.

This script tests:
1. Authentication through the /api/v1/deals/share/auth-test endpoint
2. Fetching a real deal ID from the database or API
3. Sharing a deal with the retrieved ID
"""

import asyncio
import httpx
import json
import psycopg2
from uuid import UUID

# Base API URL
BASE_URL = 'http://localhost:8000'

# Test token for authentication
TEST_TOKEN = 'test_token'

async def get_deal_id_via_api():
    """Get a real deal ID by checking various API endpoints."""
    client = httpx.AsyncClient(base_url=BASE_URL)
    headers = {'Authorization': f'Bearer {TEST_TOKEN}'}
    
    try:
        # Try deals endpoint
        print("Attempting to get a deal ID from the deals endpoint...")
        deals_response = await client.get('/api/v1/deals', headers=headers)
        if deals_response.status_code == 200:
            deals_data = deals_response.json()
            if deals_data and len(deals_data) > 0:
                deal_id = deals_data[0].get('id')
                print(f"Found deal ID: {deal_id}")
                return deal_id
        
        # Try search endpoint
        print("Attempting to get a deal ID from the search endpoint...")
        search_payload = {"keywords": "", "offset": 0, "limit": 10}
        search_response = await client.post('/api/v1/deals/search', json=search_payload, headers=headers)
        if search_response.status_code == 200:
            search_data = search_response.json()
            if search_data and 'deals' in search_data and len(search_data['deals']) > 0:
                deal_id = search_data['deals'][0].get('id')
                print(f"Found deal ID: {deal_id}")
                return deal_id
        
        print("Could not find a deal ID via API endpoints")
        return None
    
    except Exception as e:
        print(f"Error getting deal ID via API: {str(e)}")
        return None
    finally:
        await client.aclose()

def get_deal_id_via_db():
    """Get a real deal ID by directly querying the database."""
    try:
        print("Attempting to get a deal ID directly from the database...")
        conn = psycopg2.connect(
            dbname="agentic_deals",
            user="postgres",
            password="12345678",
            host="postgres"
        )
        cur = conn.cursor()
        cur.execute("SELECT id FROM deals LIMIT 1")
        row = cur.fetchone()
        
        if row and row[0]:
            deal_id = str(row[0])
            print(f"Found deal ID from database: {deal_id}")
            return deal_id
        
        print("No deals found in the database")
        return None
    
    except Exception as e:
        print(f"Error getting deal ID from database: {str(e)}")
        return None
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

async def get_deal_id():
    """Get a real deal ID using available methods."""
    # Try API first
    deal_id = await get_deal_id_via_api()
    if deal_id:
        return deal_id
    
    # Try direct database query if API fails
    return get_deal_id_via_db()

async def test_auth():
    """Test authentication by making a request to the auth-test endpoint."""
    client = httpx.AsyncClient(base_url=BASE_URL)
    headers = {'Authorization': f'Bearer {TEST_TOKEN}'}
    
    try:
        print("\n===== Testing Authentication =====")
        print("Making request to auth-test endpoint...")
        response = await client.get('/api/v1/deals/share/auth-test', headers=headers)
        
        print(f'Response status: {response.status_code}')
        print(f'Response body: {response.text}')
        
        if response.status_code == 200:
            print("✅ Authentication test successful")
        else:
            print("❌ Authentication test failed")
            
    except Exception as e:
        print(f"Error testing authentication: {str(e)}")
    finally:
        await client.aclose()

async def test_share(deal_id=None):
    """Test the share endpoint with a real deal ID."""
    if not deal_id:
        print("No deal ID provided, trying to get one...")
        deal_id = await get_deal_id()
    
    if not deal_id:
        print("Could not get a deal ID to test with.")
        return
    
    client = httpx.AsyncClient(base_url=BASE_URL)
    headers = {'Authorization': f'Bearer {TEST_TOKEN}'}
    
    try:
        print("\n===== Testing Share Functionality =====")
        print(f"Testing share endpoint with deal ID: {deal_id}")
        
        data = {
            "content_type": "deal",
            "content_id": deal_id,
            "title": "Test Share",
            "description": "Testing the share functionality",
            "expiration_days": 7,
            "visibility": "public",
            "include_personal_notes": False
        }
        
        response = await client.post('/api/v1/deals/share', json=data, headers=headers)
        print(f'Response status: {response.status_code}')
        print(f'Response body: {response.text}')
        
        if response.status_code == 201:
            print("✅ Share test successful")
            response_data = response.json()
            share_id = response_data.get('share_id')
            
            if share_id:
                print(f"Share ID: {share_id}")
                print("\nTesting get shared content endpoint (authenticated)...")
                content_response = await client.get(f'/api/v1/deals/share/content/{share_id}', headers=headers)
                print(f'Authenticated get content response status: {content_response.status_code}')
                print(f'Authenticated get content response body: {content_response.text[:500]}...' if len(content_response.text) > 500 else content_response.text)
                
                # Also test the public endpoint
                print("\nTesting public shared content endpoint...")
                async with httpx.AsyncClient(base_url=BASE_URL) as public_client:
                    public_response = await public_client.get(f'/api/v1/shared/{share_id}')
                    print(f'Public get content response status: {public_response.status_code}')
                    print(f'Public get content response body: {public_response.text[:500]}...' if len(public_response.text) > 500 else public_response.text)
        else:
            print("❌ Share test failed")
            
    except Exception as e:
        print(f"Error testing share endpoint: {str(e)}")
    finally:
        await client.aclose()

async def test_search_share():
    """Test sharing search results."""
    client = httpx.AsyncClient(base_url=BASE_URL)
    headers = {'Authorization': f'Bearer {TEST_TOKEN}'}
    
    try:
        print("\n===== Testing Search Share Functionality =====")
        data = {
            "content_type": "search_results",
            "search_params": {
                "keywords": "test",
                "categories": ["electronics"],
                "min_price": 10,
                "max_price": 1000,
                "sort_by": "price_asc"
            },
            "title": "Test Search Share",
            "description": "Testing the search share functionality",
            "expiration_days": 7,
            "visibility": "public"
        }
        
        response = await client.post('/api/v1/deals/share', json=data, headers=headers)
        print(f'Response status: {response.status_code}')
        print(f'Response body: {response.text}')
        
        if response.status_code == 201:
            print("✅ Search share test successful")
        else:
            print("❌ Search share test failed")
            
    except Exception as e:
        print(f"Error testing search share endpoint: {str(e)}")
    finally:
        await client.aclose()

async def run_tests():
    """Run all tests in sequence."""
    # Test authentication
    await test_auth()
    
    # Get a real deal ID
    deal_id = await get_deal_id()
    
    # Test share functionality
    await test_share(deal_id)
    
    # Test search share functionality
    await test_search_share()

if __name__ == "__main__":
    asyncio.run(run_tests()) 