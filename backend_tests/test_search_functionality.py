import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal
import time

from core.models.deal import DealSearch
from core.services.deal_search import DealSearchService
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
    """Test the DealSearchService directly."""
    # Create mock search parameters
    search_params = {
        "query": "gaming laptop",
        "category": "computers",
        "min_price": 500.0,
        "max_price": 2000.0,
        "sort_by": "price",
        "sort_order": "asc",
        "offset": 0,
        "limit": 10,
        "market_types": [MarketType.AMAZON.value, MarketType.NEWEGG.value]
    }
    
    # Create mock deals to return
    mock_deals = [
        {
            "id": "deal-1",
            "title": "Gaming Laptop XYZ",
            "price": 799.99,
            "market": MarketType.AMAZON.value
        },
        {
            "id": "deal-2",
            "title": "Pro Gaming Laptop ABC",
            "price": 1299.99,
            "market": MarketType.NEWEGG.value
        }
    ]
    
    # Mock the database query and execution
    with patch('core.services.deal_search.DealSearchService._execute_search_query', 
               new_callable=AsyncMock) as mock_execute:
        mock_execute.return_value = (mock_deals, 2)
        
        # Create service and call search
        service = DealSearchService(db_session)
        results = await service.search(**search_params)
        
        # Verify results
        assert results["total"] == 2
        assert len(results["deals"]) == 2
        assert results["deals"][0]["id"] == "deal-1"
        assert results["deals"][1]["id"] == "deal-2"
        
        # Verify query execution was called with correct parameters
        mock_execute.assert_called_once()
        # Verify query construction logic worked correctly
        call_args = mock_execute.call_args
        assert "query" in call_args[0][0]  # First arg is the query object
        assert call_args[1]["offset"] == 0
        assert call_args[1]["limit"] == 10

# Test with mocked database to trace the query construction
@pytest.mark.asyncio
async def test_search_query_construction(db_session: AsyncSession):
    """Test the search query construction logic."""
    # Create service and access the query construction method directly
    service = DealSearchService(db_session)
    
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
        with patch.object(service, '_construct_search_query', wraps=service._construct_search_query) as mock_construct:
            # Use the public search method which will call _construct_search_query internally
            await service.search(**params)
            
            # Verify the internal method was called with the correct parameters
            mock_construct.assert_called_once_with(**params)
            
            # Get the query directly for assertions
            query, query_params = service._construct_search_query(**params)
            
            # Verify query parameters
            assert "bluetooth speaker" in str(query)
            assert "audio" in str(query)
            assert str(20.0) in str(query_params) or "20.0" in str(query_params)
            assert str(200.0) in str(query_params) or "200.0" in str(query_params)
            assert MarketType.AMAZON.value in str(query)
            assert MarketType.EBAY.value in str(query)
            assert DealStatus.ACTIVE.value in str(query)

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
    """Test a complete search flow including storing search history."""
    # Mock user ID for the search
    user_id = "test-user-123"
    
    # Create search request
    search_data = {
        "query": "wireless earbuds",
        "category": "audio",
        "min_price": 50.0,
        "max_price": 300.0,
        "market_types": [MarketType.AMAZON.value, MarketType.BESTBUY.value],
        "sort_by": "relevance",
        "sort_order": "desc",
        "offset": 0,
        "limit": 5
    }
    
    # Mock authentication to include user ID
    auth_header = {"Authorization": f"Bearer test-token-{user_id}"}
    
    # Mock JWT verification to return our test user
    with patch('core.services.auth.JWTService.verify_token', 
               return_value={"sub": user_id, "user_id": user_id}):
        
        # Mock the deal service search method
        with patch('core.services.deal.DealService.search_deals',
                   new_callable=AsyncMock) as mock_search:
            mock_search.return_value = {
                "total": 3,
                "deals": [
                    {"id": "earbud-1", "title": "Premium Wireless Earbuds", "price": 199.99},
                    {"id": "earbud-2", "title": "Budget Wireless Earbuds", "price": 79.99},
                    {"id": "earbud-3", "title": "Mid-range Wireless Earbuds", "price": 129.99}
                ]
            }
            
            # Mock saving search history
            with patch('core.services.deal_search.DealSearchService.save_search_history',
                       new_callable=AsyncMock) as mock_save_history:
                
                # Make search request with auth header
                response = await client.post(
                    "/api/v1/deals/search", 
                    json=search_data,
                    headers=auth_header
                )
                
                # Verify response
                assert response.status_code == 200
                data = response.json()
                assert data["total"] == 3
                assert len(data["deals"]) == 3
                
                # Verify search was called with correct parameters
                mock_search.assert_called_once()
                call_kwargs = mock_search.call_args.kwargs
                assert call_kwargs["query"] == search_data["query"]
                assert call_kwargs["category"] == search_data["category"]
                assert call_kwargs["min_price"] == search_data["min_price"]
                assert call_kwargs["max_price"] == search_data["max_price"]
                assert call_kwargs["market_types"] == search_data["market_types"]
                
                # Verify search history was saved
                mock_save_history.assert_called_once()
                history_kwargs = mock_save_history.call_args.kwargs
                assert history_kwargs["user_id"] == user_id
                assert history_kwargs["query"] == search_data["query"]

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