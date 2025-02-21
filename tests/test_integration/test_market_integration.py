"""Test cases for market integration."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.market import MarketCategory
from core.integrations.scraper_api import ScraperAPIService
from core.services.market_search import MarketSearchService
from core.agents.market_agent import MarketAgent

@pytest.mark.asyncio
class TestMarketIntegration:
    """Test cases for market integration."""

    async def test_amazon_search(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        scraper_service: ScraperAPIService
    ):
        """Test Amazon market search integration."""
        # Search for products
        response = await scraper_service.search_amazon(
            query="gaming laptop RTX 3070",
            max_price=1500
        )
        assert isinstance(response, list)
        if response:
            product = response[0]
            assert "title" in product
            assert "price" in product
            assert "url" in product
            assert product["source"] == "amazon"

    async def test_walmart_search(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        scraper_service: ScraperAPIService
    ):
        """Test Walmart market search integration."""
        # Search for products
        response = await scraper_service.search_walmart(
            query="gaming laptop RTX 3070",
            max_price=1500
        )
        assert isinstance(response, list)
        if response:
            product = response[0]
            assert "title" in product
            assert "price" in product
            assert "url" in product
            assert product["source"] == "walmart"

    async def test_price_tracking(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        scraper_service: ScraperAPIService
    ):
        """Test price tracking integration."""
        # First get a product URL
        products = await scraper_service.search_amazon(
            query="gaming laptop RTX 3070",
            max_price=1500
        )
        if products:
            product_url = products[0]["url"]
            
            # Track price
            response = await async_client.post(
                "/api/v1/price-tracking/trackers",
                headers=auth_headers,
                json={
                    "url": product_url,
                    "target_price": 1200,
                    "check_interval": 3600  # 1 hour
                }
            )
            assert response.status_code == 201
            tracker_id = response.json()["id"]

            # Get tracker status
            response = await async_client.get(
                f"/api/v1/price-tracking/trackers/{tracker_id}",
                headers=auth_headers
            )
            assert response.status_code == 200
            tracker = response.json()
            assert tracker["url"] == product_url
            assert "last_price" in tracker
            assert "last_checked_at" in tracker

    async def test_market_agent_integration(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        market_agent: MarketAgent
    ):
        """Test market agent integration."""
        # Search across markets
        results = await market_agent.search_market(
            market="all",
            query="gaming laptop RTX 3070",
            max_price=1500
        )
        assert isinstance(results, dict)
        assert "matches" in results
        assert isinstance(results["matches"], list)

        if results["matches"]:
            deal = results["matches"][0]
            # Analyze deal
            analysis = await market_agent.analyze_deal(deal)
            assert "price_analysis" in analysis
            assert "market_analysis" in analysis
            assert "recommendation" in analysis

            # Get price predictions
            predictions = await market_agent.analyze_price_history(
                deal=deal,
                history=deal.get("price_history", [])
            )
            assert "trend" in predictions
            assert "predictions" in predictions

    async def test_market_data_caching(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        scraper_service: ScraperAPIService
    ):
        """Test market data caching."""
        # First search
        start_time = await scraper_service.get_request_time()
        results1 = await scraper_service.search_amazon(
            query="gaming laptop RTX 3070",
            max_price=1500
        )
        first_request_time = await scraper_service.get_request_time() - start_time

        # Second search (should use cache)
        start_time = await scraper_service.get_request_time()
        results2 = await scraper_service.search_amazon(
            query="gaming laptop RTX 3070",
            max_price=1500
        )
        second_request_time = await scraper_service.get_request_time() - start_time

        # Cached request should be faster
        assert second_request_time < first_request_time
        # Results should be the same
        assert len(results1) == len(results2)

    async def test_error_handling(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        scraper_service: ScraperAPIService
    ):
        """Test market integration error handling."""
        # Test with invalid URL
        response = await async_client.post(
            "/api/v1/price-tracking/trackers",
            headers=auth_headers,
            json={
                "url": "not-a-valid-url",
                "target_price": 1200
            }
        )
        assert response.status_code == 400

        # Test with non-existent product URL
        response = await async_client.post(
            "/api/v1/price-tracking/trackers",
            headers=auth_headers,
            json={
                "url": "https://amazon.com/non-existent-product",
                "target_price": 1200
            }
        )
        assert response.status_code == 404

        # Test rate limiting
        for _ in range(10):  # Exceed rate limit
            await scraper_service.search_amazon(
                query="test",
                max_price=100
            )
        
        response = await async_client.get(
            "/api/v1/markets/search",
            headers=auth_headers,
            params={"query": "test", "max_price": 100}
        )
        assert response.status_code == 429  # Too Many Requests 