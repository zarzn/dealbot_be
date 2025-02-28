"""Debug script to test the deals endpoint."""

from fastapi.testclient import TestClient
from main import app
from backend_tests.utils.test_client import APITestClient

def test_endpoint_direct():
    """Test the endpoint directly with TestClient."""
    client = TestClient(app)
    
    # Test with direct TestClient
    response = client.get('/api/v1/deals')
    print(f"Direct TestClient - Status: {response.status_code}")
    
    # Test with direct TestClient - trailing slash
    response = client.get('/api/v1/deals/')
    print(f"Direct TestClient (trailing slash) - Status: {response.status_code}")
    
    # Test the /deals endpoint
    response = client.get('/deals')
    print(f"Direct TestClient (/deals) - Status: {response.status_code}")
    
def test_endpoint_api_client():
    """Test the endpoint with APITestClient."""
    client = TestClient(app)
    api_client = APITestClient(client)
    
    # Test with APITestClient
    response = api_client.get('/api/v1/deals')
    print(f"APITestClient (/api/v1/deals) - Status: {response.status_code}")
    
    # Test with APITestClient - alternate format
    response = api_client.get('deals')
    print(f"APITestClient (deals) - Status: {response.status_code}")
    
    # Test with trailing slash
    response = api_client.get('/api/v1/deals/')
    print(f"APITestClient (/api/v1/deals/) - Status: {response.status_code}")
    
    # Print all available routes
    print("\nAvailable routes:")
    for route in app.routes:
        print(f"  {route.path}")

if __name__ == "__main__":
    print("Testing deals endpoint directly...")
    test_endpoint_direct()
    
    print("\nTesting deals endpoint with APITestClient...")
    test_endpoint_api_client() 