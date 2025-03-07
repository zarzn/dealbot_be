import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal

from core.models.deal import DealSearch
from core.services.deal_search import DealSearchService
from core.models.enums import DealStatus

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
        "limit": 20
    }
    
    # Mock the DealService to return a valid response
    with patch('core.api.v1.deals.router.DealService') as MockDealService:
        # Configure the mock to return a valid response
        mock_service = MagicMock()
        mock_search = AsyncMock()
        
        # Configure the mock to return a valid response with sample deals
        mock_search.return_value = {
            "deals": [
                {
                    "id": "00000000-0000-0000-0000-000000000001",
                    "title": "Test Deal 1",
                    "description": "This is a test deal",
                    "price": 50.0,
                    "original_price": 100.0,
                    "currency": "USD",
                    "url": "https://example.com/deal1",
                    "image_url": "https://example.com/image1.jpg",
                    "source": "test",
                    "status": "active",
                    "created_at": "2023-01-01T00:00:00Z",
                    "updated_at": "2023-01-01T00:00:00Z"
                }
            ],
            "total": 1,
            "metadata": {
                "search_time": 0.1,
                "source": "database"
            }
        }
        
        # Set up the mock service
        mock_service.search_deals = mock_search
        MockDealService.return_value = mock_service
    
        # Send the request to the search endpoint
        response = await client.post("/api/v1/deals/search", json=search_data)
        
        # Check the response
        assert response.status_code == 200
        data = response.json()
        assert "deals" in data
        assert "total" in data
        
        # Verify the structure of the returned deals
        if data["deals"]:
            deal = data["deals"][0]
            assert "id" in deal
            assert "title" in deal
            assert "price" in deal

# Test the search service directly
@pytest.mark.asyncio
async def test_search_service(db_session: AsyncSession):
    """Test the search service directly."""
    # Create a search request
    search_params = DealSearch(
        query="test deal",
        category="electronics",
        min_price=10.0,
        max_price=100.0,
        sort_by="price",
        sort_order="asc",
        offset=0,
        limit=20
    )
    
    # Create the search service
    search_service = DealSearchService(db_session)
    
    # Call the search method
    deals = await search_service.search_deals(search_params)
    
    # Verify the results
    assert isinstance(deals, list)
    
    # If deals were found, check their structure
    for deal in deals:
        assert hasattr(deal, "id")
        assert hasattr(deal, "title")
        assert hasattr(deal, "price")
        assert deal.status == DealStatus.ACTIVE.value

# Test with mocked database to trace the query construction
@pytest.mark.asyncio
async def test_search_query_construction(db_session: AsyncSession):
    """Test the search query construction with various parameters."""
    # Mock the database execute method to capture the query
    with patch.object(db_session, 'execute', return_value=MagicMock()) as mock_execute:
        # Configure the mock to return an empty result
        mock_execute.return_value.scalars.return_value.all.return_value = []
        
        # Create the search service
        search_service = DealSearchService(db_session)
        
        # Test case 1: Basic text search
        search_params = DealSearch(query="test deal")
        await search_service.search_deals(search_params)
        
        # Test case 2: Price range filter
        search_params = DealSearch(min_price=10.0, max_price=100.0)
        await search_service.search_deals(search_params)
        
        # Test case 3: Category filter
        search_params = DealSearch(category="electronics")
        await search_service.search_deals(search_params)
        
        # Test case 4: Sorting
        search_params = DealSearch(sort_by="price", sort_order="asc")
        await search_service.search_deals(search_params)
        
        # Test case 5: Pagination
        search_params = DealSearch(offset=20, limit=10)
        await search_service.search_deals(search_params)
        
        # Verify that execute was called for each test case
        assert mock_execute.call_count == 5

# Test error handling in the search endpoint
@pytest.mark.asyncio
async def test_search_endpoint_error_handling(client: AsyncClient):
    """Test error handling in the search endpoint."""
    # Mock the rate limiter to bypass it
    with patch('core.api.v1.deals.router.check_rate_limit') as mock_rate_limit:
        # Configure the rate limiter to do nothing
        mock_rate_limit.return_value = None
        
        # Test case 1: Invalid search parameters
        invalid_search = {
            "min_price": -10.0,  # Invalid negative price
            "max_price": 5.0     # max_price < min_price
        }
        
        response = await client.post("/api/v1/deals/search", json=invalid_search)
        assert response.status_code in [400, 422]  # Either bad request or validation error
        
        # Test case 2: Simulate rate limiting
        with patch('core.api.v1.deals.router.check_rate_limit') as mock_rate_limit:
            # Configure the rate limiter to raise an exception
            from core.exceptions.api_exceptions import RateLimitExceededError
            mock_rate_limit.side_effect = RateLimitExceededError("Rate limit exceeded")
            
            # Make a request that should be rate limited
            response = await client.post("/api/v1/deals/search", json={"query": "test"})
            
            # Check if rate limited (should be 429 Too Many Requests)
            assert response.status_code == 429

# Test the complete search flow with tracing
@pytest.mark.asyncio
async def test_complete_search_flow(client: AsyncClient, db_session: AsyncSession):
    """Test the complete search flow with tracing."""
    # Create a search request
    search_data = {
        "query": "test deal",
        "category": "electronics",
        "min_price": 10.0,
        "max_price": 100.0,
        "sort_by": "price",
        "sort_order": "asc",
        "offset": 0,
        "limit": 20
    }
    
    # Use patching to trace the flow
    with patch('core.api.v1.deals.router.DealService') as MockDealService:
        # Configure the mock to return a valid response
        mock_service = MagicMock()
        mock_search = AsyncMock()
        
        # Configure the mock to return a valid response
        mock_search.return_value = {
            "deals": [],
            "total": 0,
            "metadata": {
                "search_time": 0.1,
                "source": "database"
            }
        }
        
        # Set up the mock service
        mock_service.search_deals = mock_search
        MockDealService.return_value = mock_service
        
        # Send the request to the search endpoint
        response = await client.post("/api/v1/deals/search", json=search_data)
        
        # Check the response
        assert response.status_code == 200
        data = response.json()
        
        # Verify the search service was called with the correct parameters
        mock_search.assert_called_once()
        
        # Extract the call arguments
        args, kwargs = mock_search.call_args
        search_params = args[0]
        
        # Verify the search parameters were correctly passed
        assert search_params.query == "test deal"
        assert search_params.category == "electronics"
        assert search_params.min_price == 10.0
        assert search_params.max_price == 100.0
        assert search_params.sort_by == "price"
        assert search_params.sort_order == "asc"
        assert search_params.offset == 0
        assert search_params.limit == 20 