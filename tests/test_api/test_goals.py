"""Test cases for goal endpoints."""

import pytest
from typing import Dict
from httpx import AsyncClient
from core.models.user import User
from core.models.enums import MarketCategory, GoalPriority

@pytest.mark.asyncio
class TestGoalEndpoints:
    """Test goal endpoints."""

    async def test_create_goal(self, async_client: AsyncClient, auth_headers: Dict[str, str]):
        """Test goal creation endpoint."""
        response = await async_client.post(
            "/api/v1/goals",
            headers=auth_headers,
            json={
                "title": "Find Gaming Laptop",
                "item_category": MarketCategory.ELECTRONICS.value,
                "constraints": {
                    "max_price": 1500,
                    "min_price": 800,
                    "brands": ["Lenovo", "ASUS", "MSI"],
                    "conditions": ["new", "refurbished"],
                    "keywords": ["gaming laptop", "RTX 3070", "16GB RAM"]
                },
                "deadline": None,
                "priority": GoalPriority.MEDIUM.value,
                "max_matches": 10,
                "notification_threshold": 0.8
            }
        )
        assert response.status_code == 201
        assert "id" in response.json()

    async def test_get_goals(self, async_client: AsyncClient, auth_headers: Dict[str, str]):
        """Test get goals endpoint."""
        # First create a goal
        await async_client.post(
            "/api/v1/goals",
            headers=auth_headers,
            json={
                "title": "Test Goal",
                "item_category": MarketCategory.ELECTRONICS.value,
                "constraints": {
                    "max_price": 1000,
                    "min_price": 500,
                    "brands": ["Brand"],
                    "conditions": ["new"],
                    "keywords": ["test"]
                }
            }
        )
        
        response = await async_client.get("/api/v1/goals", headers=auth_headers)
        assert response.status_code == 200
        assert "items" in response.json()

    async def test_update_goal(self, async_client: AsyncClient, auth_headers: Dict[str, str]):
        """Test goal update endpoint."""
        # First create a goal
        create_response = await async_client.post(
            "/api/v1/goals",
            headers=auth_headers,
            json={
                "title": "Update Test",
                "item_category": MarketCategory.ELECTRONICS.value,
                "constraints": {
                    "max_price": 1000,
                    "min_price": 500,
                    "brands": ["Brand"],
                    "conditions": ["new"],
                    "keywords": ["test"]
                }
            }
        )
        goal_id = create_response.json()["id"]
        
        response = await async_client.put(
            f"/api/v1/goals/{goal_id}",
            headers=auth_headers,
            json={
                "title": "Updated Goal",
                "constraints": {
                    "max_price": 1200,
                    "min_price": 600
                }
            }
        )
        assert response.status_code == 200
        assert response.json()["title"] == "Updated Goal"

    async def test_delete_goal(self, async_client: AsyncClient, auth_headers: Dict[str, str]):
        """Test goal deletion endpoint."""
        # First create a goal
        create_response = await async_client.post(
            "/api/v1/goals",
            headers=auth_headers,
            json={
                "title": "Delete Test",
                "item_category": MarketCategory.ELECTRONICS.value,
                "constraints": {
                    "max_price": 1000,
                    "min_price": 500,
                    "brands": ["Brand"],
                    "conditions": ["new"],
                    "keywords": ["test"]
                }
            }
        )
        goal_id = create_response.json()["id"]
        
        response = await async_client.delete(f"/api/v1/goals/{goal_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "success"

    async def test_goal_status_update(self, async_client: AsyncClient, auth_headers: Dict[str, str]):
        """Test goal status update endpoint."""
        # First create a goal
        create_response = await async_client.post(
            "/api/v1/goals",
            headers=auth_headers,
            json={
                "title": "Status Test",
                "item_category": MarketCategory.ELECTRONICS.value,
                "constraints": {
                    "max_price": 1000,
                    "min_price": 500,
                    "brands": ["Brand"],
                    "conditions": ["new"],
                    "keywords": ["test"]
                }
            }
        )
        goal_id = create_response.json()["id"]
        
        response = await async_client.post(
            f"/api/v1/goals/{goal_id}/pause",
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["status"] == "paused"

    async def test_goal_analytics(self, async_client: AsyncClient, auth_headers: Dict[str, str]):
        """Test goal analytics endpoint."""
        # First create a goal
        create_response = await async_client.post(
            "/api/v1/goals",
            headers=auth_headers,
            json={
                "title": "Analytics Test",
                "item_category": MarketCategory.ELECTRONICS.value,
                "constraints": {
                    "max_price": 1000,
                    "min_price": 500,
                    "brands": ["Brand"],
                    "conditions": ["new"],
                    "keywords": ["test"]
                }
            }
        )
        goal_id = create_response.json()["id"]
        
        response = await async_client.get(f"/api/v1/goals/{goal_id}/analytics", headers=auth_headers)
        assert response.status_code == 200
        assert "analytics" in response.json() 