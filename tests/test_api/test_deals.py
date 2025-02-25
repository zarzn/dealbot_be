"""Test deal endpoints."""

import pytest
from typing import Dict
from httpx import AsyncClient
from decimal import Decimal
from uuid import UUID
from core.models.deal import Deal
from core.models.user import User
from core.services.deal import DealService
from core.services.token import TokenService
from redis.asyncio import Redis

@pytest.mark.asyncio
class TestDealEndpoints:
    """Test deal endpoints."""

    async def test_get_deals(self, async_client: AsyncClient, auth_headers: Dict[str, str], async_session, redis_client: Redis):
        """Test get deals endpoint."""
        # Initialize deal service
        deal_service = DealService(async_session)
        await deal_service.initialize()
        
        # Add tokens to user
        token_service = TokenService(async_session)
        user_id = UUID(auth_headers["user-id"])  # Convert string to UUID
        await token_service.add_reward(
            user_id=user_id,
            amount=Decimal("100.0"),
            reason="test_setup"
        )
        
        response = await async_client.get("/api/v1/deals/", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_get_deal_by_id(self, async_client: AsyncClient, auth_headers: Dict[str, str], test_deal: Deal, async_session, redis_client: Redis):
        """Test get deal by ID endpoint."""
        # Initialize deal service
        deal_service = DealService(async_session)
        await deal_service.initialize()
        
        # Add tokens to user
        token_service = TokenService(async_session)
        user_id = UUID(auth_headers["user-id"])  # Convert string to UUID
        await token_service.add_reward(
            user_id=user_id,
            amount=Decimal("100.0"),
            reason="test_setup"
        )
        
        response = await async_client.get(f"/api/v1/deals/{test_deal.id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["id"] == str(test_deal.id)

    async def test_get_deal_price_history(self, async_client: AsyncClient, auth_headers: Dict[str, str], test_deal: Deal, async_session, redis_client: Redis):
        """Test deal price history endpoint."""
        # Initialize deal service
        deal_service = DealService(async_session)
        await deal_service.initialize()
        
        # Add tokens to user
        token_service = TokenService(async_session)
        user_id = UUID(auth_headers["user-id"])  # Convert string to UUID
        await token_service.add_reward(
            user_id=user_id,
            amount=Decimal("100.0"),
            reason="test_setup"
        )
        
        response = await async_client.get(f"/api/v1/deals/{test_deal.id}/price-history", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), dict)

    async def test_track_deal(self, async_client: AsyncClient, auth_headers: Dict[str, str], test_deal: Deal, async_session, redis_client: Redis):
        """Test deal tracking endpoint."""
        # Initialize deal service
        deal_service = DealService(async_session)
        await deal_service.initialize()
        
        # Add tokens to user
        token_service = TokenService(async_session)
        user_id = UUID(auth_headers["user-id"])  # Convert string to UUID
        await token_service.add_reward(
            user_id=user_id,
            amount=Decimal("100.0"),
            reason="test_setup"
        )
        
        response = await async_client.post(f"/api/v1/deals/{test_deal.id}/track", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["message"] == "Deal tracking started successfully"

    async def test_untrack_deal(self, async_client: AsyncClient, auth_headers: Dict[str, str], test_deal: Deal, async_session, redis_client: Redis):
        """Test deal untracking endpoint."""
        # Initialize deal service
        deal_service = DealService(async_session)
        await deal_service.initialize()
        
        # Add tokens to user
        token_service = TokenService(async_session)
        user_id = UUID(auth_headers["user-id"])  # Convert string to UUID
        await token_service.add_reward(
            user_id=user_id,
            amount=Decimal("100.0"),
            reason="test_setup"
        )
        
        # First track the deal
        await async_client.post(f"/api/v1/deals/{test_deal.id}/track", headers=auth_headers)
        # Then untrack it
        response = await async_client.delete(f"/api/v1/deals/{test_deal.id}/track", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["message"] == "Deal tracking stopped successfully"

    async def test_get_deal_analysis(self, async_client: AsyncClient, auth_headers: Dict[str, str], test_deal: Deal, async_session, redis_client: Redis):
        """Test deal analysis endpoint."""
        # Initialize deal service
        deal_service = DealService(async_session)
        await deal_service.initialize()
        
        # Add tokens to user
        token_service = TokenService(async_session)
        user_id = UUID(auth_headers["user-id"])  # Convert string to UUID
        await token_service.add_reward(
            user_id=user_id,
            amount=Decimal("100.0"),
            reason="test_setup"
        )
        
        response = await async_client.get(f"/api/v1/deals/{test_deal.id}/analysis", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), dict)

    async def test_get_similar_deals(self, async_client: AsyncClient, auth_headers: Dict[str, str], test_deal: Deal, async_session, redis_client: Redis):
        """Test similar deals endpoint."""
        # Initialize deal service
        deal_service = DealService(async_session)
        await deal_service.initialize()
        
        # Add tokens to user
        token_service = TokenService(async_session)
        user_id = UUID(auth_headers["user-id"])  # Convert string to UUID
        await token_service.add_reward(
            user_id=user_id,
            amount=Decimal("100.0"),
            reason="test_setup"
        )
        
        response = await async_client.get(f"/api/v1/deals/{test_deal.id}/similar", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_get_deal_predictions(self, async_client: AsyncClient, auth_headers: Dict[str, str], test_deal: Deal, async_session, redis_client: Redis):
        """Test deal price predictions endpoint."""
        # Initialize deal service
        deal_service = DealService(async_session)
        await deal_service.initialize()
        
        # Add tokens to user
        token_service = TokenService(async_session)
        user_id = UUID(auth_headers["user-id"])  # Convert string to UUID
        await token_service.add_reward(
            user_id=user_id,
            amount=Decimal("100.0"),
            reason="test_setup"
        )
        
        response = await async_client.get(f"/api/v1/deals/{test_deal.id}/predictions", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_deal_validation(self, async_client: AsyncClient, auth_headers: Dict[str, str], test_deal: Deal, async_session, redis_client: Redis):
        """Test deal validation endpoint."""
        # Initialize deal service
        deal_service = DealService(async_session)
        await deal_service.initialize()
        
        # Add tokens to user
        token_service = TokenService(async_session)
        user_id = UUID(auth_headers["user-id"])  # Convert string to UUID
        await token_service.add_reward(
            user_id=user_id,
            amount=Decimal("100.0"),
            reason="test_setup"
        )
        
        validation_data = {
            "validation_type": "price",
            "criteria": {
                "max_price": 150.00,
                "min_discount": 0.1
            }
        }
        
        response = await async_client.post(
            f"/api/v1/deals/{test_deal.id}/validate",
            headers=auth_headers,
            json=validation_data
        )
        assert response.status_code == 200
        assert "validation_result" in response.json()

    async def test_deal_comparison(self, async_client: AsyncClient, auth_headers: Dict[str, str], test_deal: Deal, async_session, redis_client: Redis):
        """Test deal comparison endpoint."""
        # Initialize deal service
        deal_service = DealService(async_session)
        await deal_service.initialize()
        
        # Add tokens to user
        token_service = TokenService(async_session)
        user_id = UUID(auth_headers["user-id"])  # Convert string to UUID
        await token_service.add_reward(
            user_id=user_id,
            amount=Decimal("100.0"),
            reason="test_setup"
        )
        
        comparison_data = {
            "deal_ids": [str(test_deal.id)],
            "comparison_type": "price",
            "criteria": {
                "include_price_history": True,
                "include_market_analysis": True
            }
        }
        
        response = await async_client.post(
            "/api/v1/deals/compare",
            headers=auth_headers,
            json=comparison_data
        )
        assert response.status_code == 200
        assert "comparison_result" in response.json() 