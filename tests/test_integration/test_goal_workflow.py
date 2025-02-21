"""Test cases for complete goal workflow integration."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from core.models.goal import Goal, GoalStatus, GoalPriority
from core.models.market import MarketCategory
from core.models.deal import Deal
from core.agents.coordinator import AgentCoordinator

@pytest.mark.asyncio
class TestGoalWorkflow:
    """Test cases for complete goal workflow."""

    async def test_complete_goal_workflow(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        async_session: AsyncSession,
        coordinator: AgentCoordinator
    ):
        """Test complete goal workflow from creation to completion."""
        # 1. Create a goal
        goal_data = {
            "title": "Find Gaming Laptop",
            "item_category": MarketCategory.ELECTRONICS.value,
            "constraints": {
                "max_price": 1500,
                "min_price": 800,
                "brands": ["Lenovo", "ASUS", "MSI"],
                "conditions": ["new", "refurbished"],
                "keywords": ["gaming laptop", "RTX 3070", "16GB RAM"]
            },
            "priority": GoalPriority.HIGH.value,
            "max_matches": 10,
            "notification_threshold": 0.8
        }

        response = await async_client.post(
            "/api/v1/goals",
            headers=auth_headers,
            json=goal_data
        )
        assert response.status_code == 201
        goal_id = response.json()["id"]

        # 2. Verify goal creation triggered market search
        await coordinator.process_goal_with_market_search(goal_id)
        
        # Get goal status
        response = await async_client.get(
            f"/api/v1/goals/{goal_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        goal_data = response.json()
        assert goal_data["status"] == GoalStatus.ACTIVE.value

        # 3. Check for discovered deals
        response = await async_client.get(
            f"/api/v1/goals/{goal_id}/deals",
            headers=auth_headers
        )
        assert response.status_code == 200
        deals = response.json()
        assert isinstance(deals, list)

        if deals:
            deal = deals[0]
            # 4. Track a deal
            response = await async_client.post(
                f"/api/v1/deals/{deal['id']}/track",
                headers=auth_headers
            )
            assert response.status_code == 200

            # 5. Get deal analysis
            response = await async_client.get(
                f"/api/v1/deals/{deal['id']}/analysis",
                headers=auth_headers
            )
            assert response.status_code == 200
            analysis = response.json()
            assert "price_analysis" in analysis
            assert "recommendation" in analysis

            # 6. Get price predictions
            response = await async_client.get(
                f"/api/v1/deals/{deal['id']}/predictions",
                headers=auth_headers
            )
            assert response.status_code == 200
            predictions = response.json()
            assert "predictions" in predictions

        # 7. Get goal analytics
        response = await async_client.get(
            f"/api/v1/goals/{goal_id}/analytics",
            headers=auth_headers
        )
        assert response.status_code == 200
        analytics = response.json()
        assert "matches_found" in analytics
        assert "success_rate" in analytics

        # 8. Update goal status
        response = await async_client.patch(
            f"/api/v1/goals/{goal_id}/status",
            headers=auth_headers,
            json={"status": GoalStatus.COMPLETED.value}
        )
        assert response.status_code == 200
        assert response.json()["status"] == GoalStatus.COMPLETED.value

    async def test_goal_notification_workflow(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        async_session: AsyncSession,
        coordinator: AgentCoordinator
    ):
        """Test goal notification workflow."""
        # 1. Create a goal with notifications enabled
        goal_data = {
            "title": "Monitor Laptop Prices",
            "item_category": MarketCategory.ELECTRONICS.value,
            "constraints": {
                "max_price": 1200,
                "min_price": 700,
                "brands": ["Dell", "HP"],
                "conditions": ["new"],
                "keywords": ["laptop", "i7"]
            },
            "notification_threshold": 0.7
        }

        response = await async_client.post(
            "/api/v1/goals",
            headers=auth_headers,
            json=goal_data
        )
        assert response.status_code == 201
        goal_id = response.json()["id"]

        # 2. Get initial notifications
        response = await async_client.get(
            "/api/v1/notifications",
            headers=auth_headers
        )
        assert response.status_code == 200
        initial_notifications = response.json()

        # 3. Simulate a price drop event
        deal = Deal(
            goal_id=goal_id,
            title="Test Deal",
            price=699.99,  # Below min_price to trigger notification
            original_price=1299.99,
            url="https://example.com",
            source="test"
        )
        async_session.add(deal)
        await async_session.commit()

        # 4. Check for new notifications
        response = await async_client.get(
            "/api/v1/notifications",
            headers=auth_headers
        )
        assert response.status_code == 200
        new_notifications = response.json()
        assert len(new_notifications) > len(initial_notifications)

        # 5. Mark notification as read
        notification_id = new_notifications[0]["id"]
        response = await async_client.put(
            f"/api/v1/notifications/{notification_id}/read",
            headers=auth_headers
        )
        assert response.status_code == 200

        # 6. Verify notification status
        response = await async_client.get(
            f"/api/v1/notifications/{notification_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["read_at"] is not None

    async def test_goal_token_workflow(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        async_session: AsyncSession,
        coordinator: AgentCoordinator
    ):
        """Test goal token usage workflow."""
        # 1. Get initial token balance
        response = await async_client.get(
            "/api/v1/token/balance",
            headers=auth_headers
        )
        assert response.status_code == 200
        initial_balance = response.json()["balance"]

        # 2. Create a goal (should deduct tokens)
        goal_data = {
            "title": "Token Test Goal",
            "item_category": MarketCategory.ELECTRONICS.value,
            "constraints": {
                "max_price": 1000,
                "min_price": 500,
                "brands": ["Test"],
                "conditions": ["new"],
                "keywords": ["test"]
            }
        }

        response = await async_client.post(
            "/api/v1/goals",
            headers=auth_headers,
            json=goal_data
        )
        assert response.status_code == 201
        goal_id = response.json()["id"]

        # 3. Check updated balance
        response = await async_client.get(
            "/api/v1/token/balance",
            headers=auth_headers
        )
        assert response.status_code == 200
        new_balance = response.json()["balance"]
        assert new_balance < initial_balance

        # 4. Get token transaction history
        response = await async_client.get(
            "/api/v1/token/transactions",
            headers=auth_headers
        )
        assert response.status_code == 200
        transactions = response.json()
        assert len(transactions) > 0
        assert any(t["goal_id"] == goal_id for t in transactions)

        # 5. Check goal token usage
        response = await async_client.get(
            f"/api/v1/goals/{goal_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        goal_data = response.json()
        assert goal_data["tokens_spent"] > 0 