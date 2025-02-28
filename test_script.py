from fastapi.testclient import TestClient
from main import app
from backend_tests.utils.test_client import APITestClient
import pytest
import asyncio

async def test_api():
    client = TestClient(app)
    api_client = APITestClient(client)
    
    response = await api_client.aget('/api/v1/deals')
    print(f'Async GET Status: {response.status_code}')
    
    # Also test the route with a trailing slash
    response = await api_client.aget('/api/v1/deals/')
    print(f'Async GET Status (with trailing slash): {response.status_code}')
    
    # Get all available routes
    print("Available routes:")
    for route in app.routes:
        print(f"  {route.path}")
    
    pytest.exit('Test complete')

if __name__ == "__main__":
    asyncio.run(test_api()) 