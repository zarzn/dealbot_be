import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal
import time

from core.models.deal import DealSearch
from core.services.deal.base import DealService
from core.models.enums import DealStatus, MarketType

# Test the search endpoint directly
@pytest.mark.asyncio
async def test_search_endpoint(client: AsyncClient, db_session: AsyncSession):
    """Test the search endpoint directly."""
    # Create a search request
    search_data = {
        "query": "test deal",
        "category": "electronics",
        "min_price": 10.0,
        "max_price": 100.0,
        "sort_by": "price",
        "sort_order": "asc",
        "offset": 0,
        "limit": 20,
        "market_types": [MarketType.AMAZON.value, MarketType.EBAY.value]
    }
    
    # Mock the DealService to return a valid response
    with patch('core.api.v1.deals.router.DealService') as MockDealService:
        # Configure the mock to return a valid response
        mock_service = MagicMock()
        mock_service.search_deals = AsyncMock(return_value={
            "total": 2,
            "deals": [
                {
                    "id": "test-deal-1",
                    "title": "Test Deal 1",
                    "price": 25.99,
                    "description": "This is test deal 1",
                    "status": DealStatus.ACTIVE.value,
                    "seller": "Test Seller 1",
                    "market": MarketType.AMAZON.value,
                    "url": "https://example.com/deal1",
                    "created_at": "2023-01-01T12:00:00Z",
                    "updated_at": "2023-01-01T12:00:00Z"
                },
                {
                    "id": "test-deal-2",
                    "title": "Test Deal 2",
                    "price": 75.50,
                    "description": "This is test deal 2",
                    "status": DealStatus.ACTIVE.value,
                    "seller": "Test Seller 2",
                    "market": MarketType.EBAY.value,
                    "url": "https://example.com/deal2",
                    "created_at": "2023-01-02T12:00:00Z",
                    "updated_at": "2023-01-02T12:00:00Z"
                }
            ]
        })
        MockDealService.return_value = mock_service
        
        # Make request to the search endpoint
        response = await client.post("/api/v1/deals/search", json=search_data)
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["deals"]) == 2
        assert data["deals"][0]["id"] == "test-deal-1"
        assert data["deals"][1]["id"] == "test-deal-2"
        
        # Verify service was called correctly
        mock_service.search_deals.assert_called_once()
        call_kwargs = mock_service.search_deals.call_args.kwargs
        assert call_kwargs["query"] == search_data["query"]
        assert call_kwargs["min_price"] == search_data["min_price"]
        assert call_kwargs["max_price"] == search_data["max_price"]
        assert call_kwargs["market_types"] == search_data["market_types"]

# Test the search service directly
@pytest.mark.asyncio
async def test_search_service(db_session: AsyncSession):
    """Test the search service directly."""
    # Create a search request
    search = DealSearch(
        query="test query",
        offset=0,
        limit=10
    )
    
    # Mock the DealService methods
    with patch('core.services.deal.search.core_search.search_deals') as mock_search:
        # Configure mock to return a valid response
        mock_search.return_value = {
            "total": 1,
            "deals": [
                {
                    "id": "test-id",
                    "title": "Test Deal",
                    "price": 20.0
                }
            ]
        }
        
        # Create service and search
        service = DealService(db_session)
        result = await service.search_deals(search)
        
        # Assertions
        assert result is not None
        assert "deals" in result
        assert len(result["deals"]) == 1
        assert result["total"] == 1
        assert result["deals"][0]["title"] == "Test Deal"

# Test with mocked database to trace the query construction
@pytest.mark.asyncio
async def test_search_query_construction(db_session: AsyncSession):
    """Test the search query construction logic."""
    # Create service and access the query construction method directly
    service = DealService(db_session)
    
    # Mock parameters for query construction
    params = {
        "query": "bluetooth speaker",
        "category": "audio",
        "min_price": 20.0,
        "max_price": 200.0,
        "market_types": [MarketType.AMAZON.value, MarketType.EBAY.value],
        "status": DealStatus.ACTIVE.value
    }
    
    # Patch the execute method to avoid actually running the query
    with patch('sqlalchemy.ext.asyncio.AsyncSession.execute'):
        # Test that the search method properly constructs the query
        with patch('core.services.deal.search.query_formatter.construct_search_query') as mock_construct:
            # Use the public search method which will call construct_search_query internally
            await service.search_deals(DealSearch(**params))
            
            # Verify the internal method was called with the correct parameters
            mock_construct.assert_called_once()
            
            # Since we've patched the function, we won't test its internals here
            # Just verify that the search_deals method was called correctly

# Test error handling in the search endpoint
@pytest.mark.asyncio
async def test_search_endpoint_error_handling(client: AsyncClient):
    """Test error handling in the search endpoint."""
    # Test with invalid search parameters
    invalid_data = {
        "query": "",  # Empty query
        "min_price": 100.0,
        "max_price": 50.0,  # Invalid price range
        "limit": -10  # Invalid limit
    }
    
    # Make request with invalid data
    response = await client.post("/api/v1/deals/search", json=invalid_data)
    
    # Verify response indicates validation error
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    
    # Test with server error
    with patch('core.api.v1.deals.router.DealService') as MockDealService:
        # Configure mock to raise an exception
        mock_service = MagicMock()
        mock_service.search_deals = AsyncMock(side_effect=Exception("Database error"))
        MockDealService.return_value = mock_service
        
        # Make request that will trigger server error
        valid_data = {
            "query": "test",
            "min_price": 10.0,
            "max_price": 100.0
        }
        response = await client.post("/api/v1/deals/search", json=valid_data)
        
        # Verify response indicates server error
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data

# Test the complete search flow with tracing
@pytest.mark.asyncio
async def test_complete_search_flow(client: AsyncClient, db_session: AsyncSession):
    """Test the complete search flow from request to response."""
    
    # Create a search request
    search_data = {
        "query": "test product",
        "category": None,
        "min_price": 10,
        "max_price": 100,
        "page": 1,
        "page_size": 10
    }
    
    # Mock the search history functionality
    with patch('core.services.deal.DealService.search_deals',
               new_callable=AsyncMock) as mock_search:
        # Configure the mock to return a valid response
        mock_search.return_value = {
            "total": 2,
            "deals": [
                {
                    "id": "test-deal-1",
                    "title": "Test Deal 1",
                    "price": 25.99,
                    "description": "This is test deal 1",
                    "status": DealStatus.ACTIVE.value,
                    "created_at": "2023-01-01T12:00:00Z",
                    "updated_at": "2023-01-01T12:00:00Z",
                    "latest_score": 8.5,
                    "price_history": []
                },
                {
                    "id": "test-deal-2",
                    "title": "Test Deal 2",
                    "price": 75.50,
                    "description": "This is test deal 2",
                    "status": DealStatus.ACTIVE.value,
                    "created_at": "2023-01-01T12:00:00Z",
                    "updated_at": "2023-01-01T12:00:00Z",
                    "latest_score": 7.0,
                    "price_history": []
                }
            ],
            "metadata": {
                "search_time_ms": 15,
                "page": 1,
                "page_size": 10,
                "sort_by": "relevance",
                "sort_order": "desc"
            }
        }
    
        # Make the request
        response = await client.post(
            "/api/v1/deals/search",
            json=search_data
        )
        
        # Assertions
        assert response.status_code == 200
        assert "deals" in response.json()
        assert len(response.json()["deals"]) == 2
        assert "total" in response.json()
        assert response.json()["total"] == 2
        
        # Verify that the service was called with the expected parameters
        mock_search.assert_called_once()

# Test with token
@pytest.mark.asyncio
async def test_token_search(client: AsyncClient):
    """Test search functionality with token."""
    # Mock user ID for the search
    user_id = "test-user-123"
    
    # Test with token
    token = "test_token"
    with patch('core.services.auth.verify_token',
              return_value={"sub": str(user_id), "exp": time.time() + 3600}):
        response = client.get(f"/api/deals/search?keyword=test&token={token}")
        assert response.status_code == 200 