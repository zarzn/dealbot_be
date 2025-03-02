"""Test module for DealScore and DealMatch models.

This module contains tests for the DealScore and DealMatch models, which handle
scoring and matching deals in the AI Agentic Deals System.
"""

import pytest
from uuid import uuid4
from decimal import Decimal
from sqlalchemy import select
from datetime import datetime

from core.models.deal_score import (
    DealScore,
    DealMatch,
    ScoreType
)
from core.models.deal import Deal
from core.models.goal import Goal
from core.models.user import User
from core.models.enums import DealStatus, MarketType, GoalStatus
from core.exceptions import ValidationError


@pytest.mark.asyncio
@pytest.mark.core
async def test_deal_score_creation(async_session):
    """Test creating a deal score in the database."""
    # Create a test user first
    user_id = uuid4()
    user = User(id=user_id, email="test@example.com", username="testuser")
    async_session.add(user)
    
    # Create a test deal
    deal_id = uuid4()
    deal = Deal(
        id=deal_id,
        title="Test Deal",
        description="A test deal for scoring",
        status=DealStatus.ACTIVE.value,
        market_type=MarketType.CRYPTO.value,
        user_id=user_id
    )
    async_session.add(deal)
    await async_session.commit()
    
    # Create a deal score
    score = DealScore(
        deal_id=deal_id,
        user_id=user_id,
        score=0.75,
        confidence=0.85,
        score_type=ScoreType.AI.value,
        factors={
            "profitability": 0.8,
            "risk": 0.3,
            "time_horizon": 0.6
        }
    )
    async_session.add(score)
    await async_session.commit()
    
    # Retrieve the score
    query = select(DealScore).where(DealScore.deal_id == deal_id)
    result = await async_session.execute(query)
    fetched_score = result.scalar_one()
    
    # Assertions
    assert fetched_score is not None
    assert fetched_score.id is not None
    assert fetched_score.deal_id == deal_id
    assert fetched_score.user_id == user_id
    assert fetched_score.score == 0.75
    assert fetched_score.confidence == 0.85
    assert fetched_score.score_type == ScoreType.AI.value
    assert fetched_score.factors["profitability"] == 0.8
    assert fetched_score.factors["risk"] == 0.3
    assert isinstance(fetched_score.created_at, datetime)
    assert isinstance(fetched_score.updated_at, datetime)


@pytest.mark.asyncio
@pytest.mark.core
async def test_deal_score_relationships(async_session):
    """Test the relationships between deal scores and deals."""
    # Create a test user
    user_id = uuid4()
    user = User(id=user_id, email="test@example.com", username="testuser")
    async_session.add(user)
    
    # Create a test deal
    deal = Deal(
        title="Relationship Test Deal",
        description="Testing deal score relationships",
        status=DealStatus.ACTIVE.value,
        market_type=MarketType.CRYPTO.value,
        user_id=user_id
    )
    async_session.add(deal)
    await async_session.commit()
    
    # Create multiple scores for the deal
    ai_score = DealScore(
        deal_id=deal.id,
        user_id=user_id,
        score=0.8,
        confidence=0.9,
        score_type=ScoreType.AI.value
    )
    
    user_score = DealScore(
        deal_id=deal.id,
        user_id=user_id,
        score=0.7,
        confidence=1.0,
        score_type=ScoreType.USER.value
    )
    
    async_session.add_all([ai_score, user_score])
    await async_session.commit()
    
    # Test deal -> scores relationship
    query = select(Deal).where(Deal.id == deal.id)
    result = await async_session.execute(query)
    fetched_deal = result.scalar_one()
    
    assert len(fetched_deal.scores) == 2
    assert any(score.score_type == ScoreType.AI.value for score in fetched_deal.scores)
    assert any(score.score_type == ScoreType.USER.value for score in fetched_deal.scores)


@pytest.mark.asyncio
@pytest.mark.core
async def test_deal_score_validation(async_session):
    """Test validation for deal scores."""
    # Create a test user
    user_id = uuid4()
    user = User(id=user_id, email="test@example.com", username="testuser")
    async_session.add(user)
    
    # Create a test deal
    deal = Deal(
        title="Validation Test Deal",
        description="Testing deal score validation",
        status=DealStatus.ACTIVE.value,
        market_type=MarketType.CRYPTO.value,
        user_id=user_id
    )
    async_session.add(deal)
    await async_session.commit()
    
    # Test invalid score (greater than 1)
    with pytest.raises(ValidationError):
        await DealScore.create_score(
            db=async_session,
            deal_id=deal.id,
            user_id=user_id,
            score=1.5,  # Invalid: > 1
            confidence=0.8
        )
    
    # Test invalid score (negative)
    with pytest.raises(ValidationError):
        await DealScore.create_score(
            db=async_session,
            deal_id=deal.id,
            user_id=user_id,
            score=-0.5,  # Invalid: < 0
            confidence=0.8
        )
    
    # Test invalid confidence (greater than 1)
    with pytest.raises(ValidationError):
        await DealScore.create_score(
            db=async_session,
            deal_id=deal.id,
            user_id=user_id,
            score=0.7,
            confidence=1.2  # Invalid: > 1
        )
    
    # Create a valid score
    valid_score = await DealScore.create_score(
        db=async_session,
        deal_id=deal.id,
        user_id=user_id,
        score=0.5,
        confidence=0.8,
        factors={"quality": 0.6}
    )
    
    assert valid_score is not None
    assert valid_score.score == 0.5
    assert valid_score.confidence == 0.8
    assert valid_score.factors["quality"] == 0.6


@pytest.mark.asyncio
@pytest.mark.core
async def test_create_score_method(async_session):
    """Test the create_score method of DealScore."""
    # Create a test user
    user_id = uuid4()
    user = User(id=user_id, email="test@example.com", username="testuser")
    async_session.add(user)
    
    # Create a test deal
    deal = Deal(
        title="Create Method Test Deal",
        description="Testing deal score create method",
        status=DealStatus.ACTIVE.value,
        market_type=MarketType.CRYPTO.value,
        user_id=user_id
    )
    async_session.add(deal)
    await async_session.commit()
    
    # Create a score using the create_score method
    factors = {
        "profitability": 0.9,
        "risk": 0.2,
        "market_trend": 0.7
    }
    
    score = await DealScore.create_score(
        db=async_session,
        deal_id=deal.id,
        user_id=user_id,
        score=0.65,
        confidence=0.75,
        factors=factors
    )
    
    # Verify score was created properly
    assert score.deal_id == deal.id
    assert score.user_id == user_id
    assert score.score == 0.65
    assert score.confidence == 0.75
    assert score.factors == factors
    
    # Verify it was saved in the database
    query = select(DealScore).where(DealScore.id == score.id)
    result = await async_session.execute(query)
    db_score = result.scalar_one()
    
    assert db_score is not None
    assert db_score.id == score.id
    assert db_score.factors["profitability"] == 0.9


@pytest.mark.asyncio
@pytest.mark.core
async def test_update_metrics(async_session):
    """Test updating metrics for a deal score."""
    # Create a test user
    user_id = uuid4()
    user = User(id=user_id, email="test@example.com", username="testuser")
    async_session.add(user)
    
    # Create a test deal
    deal = Deal(
        title="Metrics Update Test Deal",
        description="Testing deal score metrics updates",
        status=DealStatus.ACTIVE.value,
        market_type=MarketType.CRYPTO.value,
        user_id=user_id
    )
    async_session.add(deal)
    await async_session.commit()
    
    # Create a score with initial metrics
    initial_factors = {
        "profitability": 0.6,
        "risk": 0.4
    }
    
    score = await DealScore.create_score(
        db=async_session,
        deal_id=deal.id,
        user_id=user_id,
        score=0.5,
        confidence=0.6,
        factors=initial_factors
    )
    
    # Update metrics
    updated_metrics = {
        "profitability": 0.8,
        "risk": 0.3,
        "volatility": 0.5  # New metric
    }
    
    await score.update_metrics(
        db=async_session,
        metrics=updated_metrics
    )
    
    # Verify metrics were updated
    query = select(DealScore).where(DealScore.id == score.id)
    result = await async_session.execute(query)
    updated_score = result.scalar_one()
    
    assert updated_score.factors == updated_metrics
    assert updated_score.factors["profitability"] == 0.8
    assert updated_score.factors["volatility"] == 0.5


@pytest.mark.asyncio
@pytest.mark.core
async def test_to_json(async_session):
    """Test the to_json method of DealScore."""
    # Create a test user
    user_id = uuid4()
    user = User(id=user_id, email="test@example.com", username="testuser")
    async_session.add(user)
    
    # Create a test deal
    deal = Deal(
        title="JSON Test Deal",
        description="Testing deal score to_json method",
        status=DealStatus.ACTIVE.value,
        market_type=MarketType.CRYPTO.value,
        user_id=user_id
    )
    async_session.add(deal)
    await async_session.commit()
    
    # Create a score
    factors = {
        "quality": 0.75,
        "timeline": 0.6
    }
    
    score = DealScore(
        deal_id=deal.id,
        user_id=user_id,
        score=0.7,
        confidence=0.8,
        score_type=ScoreType.AI.value,
        factors=factors
    )
    async_session.add(score)
    await async_session.commit()
    
    # Test to_json method
    json_str = score.to_json()
    
    # Import json to parse the string
    import json
    json_obj = json.loads(json_str)
    
    # Verify JSON data
    assert json_obj["id"] == str(score.id)
    assert json_obj["deal_id"] == str(deal.id)
    assert json_obj["user_id"] == str(user_id)
    assert json_obj["score"] == 0.7
    assert json_obj["confidence"] == 0.8
    assert json_obj["factors"]["quality"] == 0.75
    assert json_obj["factors"]["timeline"] == 0.6
    assert "created_at" in json_obj
    assert "timestamp" in json_obj


@pytest.mark.asyncio
@pytest.mark.core
async def test_deal_match_creation(async_session):
    """Test creating a DealMatch in the database."""
    # Create a test user
    user_id = uuid4()
    user = User(id=user_id, email="test@example.com", username="testuser")
    async_session.add(user)
    
    # Create a test deal
    deal = Deal(
        title="Match Test Deal",
        description="Deal for testing match functionality",
        status=DealStatus.ACTIVE.value,
        market_type=MarketType.CRYPTO.value,
        user_id=user_id
    )
    
    # Create a test goal
    goal = Goal(
        title="Test Goal",
        description="Goal for testing matches",
        status=GoalStatus.ACTIVE.value,
        user_id=user_id
    )
    
    async_session.add_all([deal, goal])
    await async_session.commit()
    
    # Create a deal match
    match = DealMatch(
        goal_id=goal.id,
        deal_id=deal.id,
        match_score=0.85,
        match_criteria={
            "keyword_match": 0.9,
            "category_match": 0.7,
            "value_alignment": 0.8
        }
    )
    
    async_session.add(match)
    await async_session.commit()
    
    # Retrieve the match
    query = select(DealMatch).where(
        (DealMatch.goal_id == goal.id) & (DealMatch.deal_id == deal.id)
    )
    result = await async_session.execute(query)
    fetched_match = result.scalar_one()
    
    # Assertions
    assert fetched_match is not None
    assert fetched_match.goal_id == goal.id
    assert fetched_match.deal_id == deal.id
    assert fetched_match.match_score == 0.85
    assert fetched_match.match_criteria["keyword_match"] == 0.9
    assert fetched_match.match_criteria["value_alignment"] == 0.8
    assert isinstance(fetched_match.created_at, datetime)
    assert isinstance(fetched_match.updated_at, datetime)


@pytest.mark.asyncio
@pytest.mark.core
async def test_deal_match_relationships(async_session):
    """Test the relationships between deal matches, deals, and goals."""
    # Create a test user
    user_id = uuid4()
    user = User(id=user_id, email="test@example.com", username="testuser")
    async_session.add(user)
    
    # Create multiple deals and goals
    deal1 = Deal(
        title="First Match Test Deal",
        description="First deal for testing matches",
        status=DealStatus.ACTIVE.value,
        market_type=MarketType.CRYPTO.value,
        user_id=user_id
    )
    
    deal2 = Deal(
        title="Second Match Test Deal",
        description="Second deal for testing matches",
        status=DealStatus.ACTIVE.value,
        market_type=MarketType.CRYPTO.value,
        user_id=user_id
    )
    
    goal1 = Goal(
        title="First Test Goal",
        description="First goal for testing matches",
        status=GoalStatus.ACTIVE.value,
        user_id=user_id
    )
    
    goal2 = Goal(
        title="Second Test Goal",
        description="Second goal for testing matches",
        status=GoalStatus.ACTIVE.value,
        user_id=user_id
    )
    
    async_session.add_all([deal1, deal2, goal1, goal2])
    await async_session.commit()
    
    # Create matches
    match1 = DealMatch(
        goal_id=goal1.id,
        deal_id=deal1.id,
        match_score=0.9,
        match_criteria={"overall": 0.9}
    )
    
    match2 = DealMatch(
        goal_id=goal1.id,
        deal_id=deal2.id,
        match_score=0.7,
        match_criteria={"overall": 0.7}
    )
    
    match3 = DealMatch(
        goal_id=goal2.id,
        deal_id=deal1.id,
        match_score=0.8,
        match_criteria={"overall": 0.8}
    )
    
    async_session.add_all([match1, match2, match3])
    await async_session.commit()
    
    # Test goal -> matched_deals relationship
    query = select(Goal).where(Goal.id == goal1.id)
    result = await async_session.execute(query)
    fetched_goal = result.scalar_one()
    
    assert len(fetched_goal.matched_deals) == 2
    assert any(match.deal_id == deal1.id for match in fetched_goal.matched_deals)
    assert any(match.deal_id == deal2.id for match in fetched_goal.matched_deals)
    
    # Test deal -> goal_matches relationship
    query = select(Deal).where(Deal.id == deal1.id)
    result = await async_session.execute(query)
    fetched_deal = result.scalar_one()
    
    assert len(fetched_deal.goal_matches) == 2
    assert any(match.goal_id == goal1.id for match in fetched_deal.goal_matches)
    assert any(match.goal_id == goal2.id for match in fetched_deal.goal_matches)
    
    # Test specific match relationships
    query = select(DealMatch).where(
        (DealMatch.goal_id == goal1.id) & (DealMatch.deal_id == deal1.id)
    )
    result = await async_session.execute(query)
    fetched_match = result.scalar_one()
    
    assert fetched_match.goal.id == goal1.id
    assert fetched_match.deal.id == deal1.id 