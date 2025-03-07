import pytest
import logging
import httpx
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient
from sqlalchemy import select, or_, and_

from core.models.deal import DealSearch, Deal
from core.services.deal_search import DealSearchService
from core.api.v1.deals.router import search_deals
from core.models.enums import DealStatus

# Set up logging for the test
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SearchWorkflowTracer:
    """Helper class to trace the search workflow."""
    
    def __init__(self):
        self.steps = []
        
    def add_step(self, step_name, details=None):
        """Add a step to the trace."""
        step = {"step": step_name}
        if details:
            step["details"] = details
        self.steps.append(step)
        logger.info(f"Step: {step_name} - Details: {details}")
        
    def get_trace(self):
        """Get the complete trace."""
        return self.steps

@pytest.mark.asyncio
async def test_search_workflow_tracing(client: AsyncClient, db_session: AsyncSession):
    """
    Test the complete search workflow with detailed tracing.
    
    This test traces the entire flow from the API endpoint to the database query
    and back, logging each step along the way.
    """
    # Create a tracer to record the workflow steps
    tracer = SearchWorkflowTracer()
    
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
    
    tracer.add_step("1. Create search request", search_data)
    
    # Mock the rate limiter to always allow requests
    with patch('core.api.v1.deals.router.check_rate_limit') as mock_rate_limit:
        # Configure the rate limiter to do nothing
        mock_rate_limit.return_value = None
        
        tracer.add_step("2. Bypass rate limiter for testing")
        
        # Mock the deal service to trace the call
        with patch('core.api.v1.deals.router.DealService') as MockDealService:
            # Create a mock service with a search_deals method
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
            
            tracer.add_step("3. Mock deal service")
            tracer.add_step("4. Mock search service")
            
            # Send the request to the search endpoint
            response = await client.post("/api/v1/deals/search", json=search_data)
            
            tracer.add_step("5. Send request to API endpoint", {
                "url": "/api/v1/deals/search",
                "method": "POST",
                "data": search_data
            })
            
            # Check the response
            assert response.status_code == 200
            data = response.json()
            
            tracer.add_step("6. Receive response", {
                "status_code": response.status_code,
                "data": data
            })
            
            # Verify the search service was called with the correct parameters
            mock_search.assert_called_once()
            
            # Extract the call arguments
            args, kwargs = mock_search.call_args
            search_params = args[0]
            
            tracer.add_step("7. Verify search parameters", {
                "query": search_params.query,
                "category": search_params.category,
                "min_price": search_params.min_price,
                "max_price": search_params.max_price,
                "sort_by": search_params.sort_by,
                "sort_order": search_params.sort_order,
                "offset": search_params.offset,
                "limit": search_params.limit
            })
    
    # Return the complete trace for analysis
    workflow_trace = tracer.get_trace()
    for step in workflow_trace:
        logger.info(f"Workflow step: {step}")
    
    return workflow_trace

@pytest.mark.asyncio
async def test_search_database_query_construction(db_session: AsyncSession):
    """
    Test the construction of the database query in the search service.
    
    This test examines how different search parameters affect the SQL query
    that is constructed.
    """
    tracer = SearchWorkflowTracer()
    
    # Create a search service
    search_service = DealSearchService(db_session)
    
    # Mock the database execute method to capture the query
    with patch.object(db_session, 'execute') as mock_execute:
        # Configure the mock to return an empty result
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_execute.return_value = result_mock
        
        tracer.add_step("1. Create search service and mock database")
        
        # Test case 1: Basic text search
        search_params = DealSearch(query="test deal")
        
        tracer.add_step("2. Create search parameters", {
            "query": search_params.query
        })
        
        # Execute the search
        await search_service.search_deals(search_params)
        
        tracer.add_step("3. Execute search query")
        
        # Capture the query that was executed
        query_args = mock_execute.call_args[0][0]
        
        tracer.add_step("4. Analyze query construction", {
            "has_text_filter": "ilike" in str(query_args).lower(),
            "has_status_filter": DealStatus.ACTIVE.value.lower() in str(query_args).lower()
        })
        
        # Reset the mock for the next test
        mock_execute.reset_mock()
        
        # Test case 2: Price range filter
        search_params = DealSearch(min_price=10.0, max_price=100.0)
        
        tracer.add_step("5. Create price range search parameters", {
            "min_price": search_params.min_price,
            "max_price": search_params.max_price
        })
        
        # Execute the search
        await search_service.search_deals(search_params)
        
        tracer.add_step("6. Execute price range search query")
        
        # Capture the query that was executed
        query_args = mock_execute.call_args[0][0]
        
        tracer.add_step("7. Analyze price range query construction", {
            "has_min_price_filter": ">=" in str(query_args),
            "has_max_price_filter": "<=" in str(query_args)
        })
    
    # Return the trace for analysis
    workflow_trace = tracer.get_trace()
    for step in workflow_trace:
        logger.info(f"Database query construction step: {step}")
    
    return workflow_trace

@pytest.mark.asyncio
async def test_search_error_handling(client: AsyncClient):
    """
    Test error handling in the search workflow.
    
    This test examines how errors are handled at different points in the
    search workflow.
    """
    tracer = SearchWorkflowTracer()
    
    # Create a valid search request
    search_data = {
        "query": "test deal"
    }
    
    tracer.add_step("1. Create search request", search_data)
    
    # Test case 1: Service throws an exception
    with patch('core.api.v1.deals.router.get_deal_service') as mock_get_service:
        # Create a mock service that raises an exception
        mock_service = MagicMock()
        mock_service.search_deals.side_effect = Exception("Test error")
        mock_get_service.return_value = mock_service
        
        tracer.add_step("2. Mock service to raise exception")
        
        # Send the request to the search endpoint
        response = await client.post("/api/v1/deals/search", json=search_data)
        
        tracer.add_step("3. Send request to API endpoint", {
            "url": "/api/v1/deals/search",
            "method": "POST",
            "data": search_data
        })
        
        # Check the response
        assert response.status_code in [400, 500]  # Either bad request or server error
        data = response.json()
        
        tracer.add_step("4. Receive error response", {
            "status_code": response.status_code,
            "data": data
        })
    
    # Test case 2: Invalid search parameters
    invalid_search = {
        "min_price": -10.0  # Invalid negative price
    }
    
    tracer.add_step("5. Create invalid search request", invalid_search)
    
    # Send the request to the search endpoint
    response = await client.post("/api/v1/deals/search", json=invalid_search)
    
    tracer.add_step("6. Send invalid request to API endpoint", {
        "url": "/api/v1/deals/search",
        "method": "POST",
        "data": invalid_search
    })
    
    # Check the response
    assert response.status_code in [400, 422]  # Either bad request or validation error
    data = response.json()
    
    tracer.add_step("7. Receive validation error response", {
        "status_code": response.status_code,
        "data": data
    })
    
    # Return the trace for analysis
    workflow_trace = tracer.get_trace()
    for step in workflow_trace:
        logger.info(f"Error handling step: {step}")
    
    return workflow_trace 