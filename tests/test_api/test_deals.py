"""Test deal endpoints."""

import pytest
from typing import Dict, AsyncGenerator
from httpx import AsyncClient
from core.models.deal import Deal
from core.models.user import User

@pytest.mark.asyncio
class TestDealEndpoints:
    """Test deal endpoints."""

    async def test_get_deals(self, async_client: AsyncGenerator[AsyncClient, None], auth_headers: Dict[str, str]):
        """Test get deals endpoint."""
        client = await anext(async_client)
        response = await client.get("/api/v1/deals", headers=auth_headers)
        assert response.status_code == 200
        assert "items" in response.json()

    async def test_get_deal_by_id(self, async_client: AsyncGenerator[AsyncClient, None], auth_headers: Dict[str, str], test_deal: Deal):
        """Test get deal by ID endpoint."""
        client = await anext(async_client)
        response = await client.get(f"/api/v1/deals/{test_deal.id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["id"] == str(test_deal.id)

    async def test_get_deal_price_history(self, async_client: AsyncGenerator[AsyncClient, None], auth_headers: Dict[str, str], test_deal: Deal):
        """Test deal price history endpoint."""
        client = await anext(async_client)
        response = await client.get(f"/api/v1/deals/{test_deal.id}/price-history", headers=auth_headers)
        assert response.status_code == 200
        assert "history" in response.json()

    async def test_track_deal(self, async_client: AsyncGenerator[AsyncClient, None], auth_headers: Dict[str, str], test_deal: Deal):
        """Test deal tracking endpoint."""
        client = await anext(async_client)
        response = await client.post(f"/api/v1/deals/{test_deal.id}/track", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "success"

    async def test_untrack_deal(self, async_client: AsyncGenerator[AsyncClient, None], auth_headers: Dict[str, str], test_deal: Deal):
        """Test deal untracking endpoint."""
        client = await anext(async_client)
        # First track the deal
        await client.post(f"/api/v1/deals/{test_deal.id}/track", headers=auth_headers)
        # Then untrack it
        response = await client.delete(f"/api/v1/deals/{test_deal.id}/track", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "success"

    async def test_get_deal_analysis(self, async_client: AsyncGenerator[AsyncClient, None], auth_headers: Dict[str, str], test_deal: Deal):
        """Test deal analysis endpoint."""
        client = await anext(async_client)
        response = await client.get(f"/api/v1/deals/{test_deal.id}/analysis", headers=auth_headers)
        assert response.status_code == 200
        assert "analysis" in response.json()

    async def test_get_similar_deals(self, async_client: AsyncGenerator[AsyncClient, None], auth_headers: Dict[str, str], test_deal: Deal):
        """Test similar deals endpoint."""
        client = await anext(async_client)
        response = await client.get(f"/api/v1/deals/{test_deal.id}/similar", headers=auth_headers)
        assert response.status_code == 200
        assert "similar_deals" in response.json()

    async def test_get_deal_predictions(self, async_client: AsyncGenerator[AsyncClient, None], auth_headers: Dict[str, str], test_deal: Deal):
        """Test deal price predictions endpoint."""
        client = await anext(async_client)
        response = await client.get(f"/api/v1/deals/{test_deal.id}/predictions", headers=auth_headers)
        assert response.status_code == 200
        assert "predictions" in response.json()

    async def test_deal_validation(self, async_client: AsyncGenerator[AsyncClient, None], auth_headers: Dict[str, str], test_deal: Deal):
        """Test deal validation endpoint."""
        client = await anext(async_client)
        response = await client.post(
            f"/api/v1/deals/{test_deal.id}/validate",
            headers=auth_headers,
            json={"validation_type": "price"}
        )
        assert response.status_code == 200
        assert "validation_result" in response.json()

    async def test_deal_comparison(self, async_client: AsyncGenerator[AsyncClient, None], auth_headers: Dict[str, str], test_deal: Deal):
        """Test deal comparison endpoint."""
        client = await anext(async_client)
        response = await client.post(
            "/api/v1/deals/compare",
            headers=auth_headers,
            json={
                "deal_ids": [str(test_deal.id)],
                "comparison_type": "price"
            }
        )
        assert response.status_code == 200
        assert "comparison_result" in response.json() 