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
from core.models.enums import DealStatus, MarketType, GoalStatus, MarketCategory, MarketStatus
from core.exceptions import ValidationError
from core.models.market import Market


@pytest.mark.asyncio
@pytest.mark.core
async def test_deal_score_creation(db_session):
    """Test creating a deal score in the database."""
    # Create a test user first
    user_id = uuid4()
    user = User(
        id=user_id, 
        email="test@example.com", 
        name="testuser",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    
    # Create a test market
    market_id = uuid4()
    market = Market(
        id=market_id,
        name="Test Market",
        type=MarketType.TEST.value.lower(),
        user_id=user_id
    )
    db_session.add(market)
    await db_session.commit()
    
    # Create a test deal
    deal_id = uuid4()
    deal = Deal(
        id=deal_id,
        title="Test Deal",
        description="A test deal for scoring",
        url="https://example.com/test-deal",
        price=Decimal("99.99"),
        currency="USD",
        status=DealStatus.ACTIVE.value.lower(),
        category=MarketCategory.ELECTRONICS.value,
        user_id=user_id,
        market_id=market_id
    )
    db_session.add(deal)
    await db_session.commit()
    
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
    db_session.add(score)
    await db_session.commit()
    
    # Retrieve the score
    query = select(DealScore).where(DealScore.deal_id == deal_id)
    result = await db_session.execute(query)
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
async def test_deal_score_relationships(db_session):
    """Test the relationships between deal scores, deals, and users."""
    # Create a test user first
    user_id = uuid4()
    user = User(
        id=user_id, 
        email="test_rel@example.com", 
        name="reluser",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    
    # Create a test market
    market_id = uuid4()
    market = Market(
        id=market_id,
        name="Relationship Test Market",
        type=MarketType.TEST.value.lower(),
        user_id=user_id
    )
    db_session.add(market)
    await db_session.commit()
    
    # Create a test deal
    deal_id = uuid4()
    deal = Deal(
        id=deal_id,
        title="Relationship Test Deal",
        description="A test deal for relationship testing",
        url="https://example.com/rel-test-deal",
        price=Decimal("129.99"),
        currency="USD",
        status=DealStatus.ACTIVE.value.lower(),
        category=MarketCategory.ELECTRONICS.value,
        user_id=user_id,
        market_id=market_id
    )
    db_session.add(deal)
    await db_session.commit()
    
    # Create multiple scores for the deal
    ai_score = DealScore(
        deal_id=deal_id,
        user_id=user_id,
        score=0.8,
        confidence=0.9,
        score_type=ScoreType.AI.value
    )
    
    user_score = DealScore(
        deal_id=deal_id,
        user_id=user_id,
        score=0.7,
        confidence=1.0,
        score_type=ScoreType.USER.value
    )
    
    db_session.add_all([ai_score, user_score])
    await db_session.commit()
    
    # Test deal -> scores relationship
    query = select(Deal).where(Deal.id == deal_id)
    result = await db_session.execute(query)
    fetched_deal = result.scalar_one()
    
    # Explicitly refresh the object to load relationships
    await db_session.refresh(fetched_deal, ["scores"])
    
    assert len(fetched_deal.scores) == 2
    assert any(score.score_type == ScoreType.AI.value for score in fetched_deal.scores)
    assert any(score.score_type == ScoreType.USER.value for score in fetched_deal.scores)


@pytest.mark.asyncio
@pytest.mark.core
async def test_deal_score_validation(db_session):
    """Test deal score validation rules."""
    # Create a test user
    user_id = uuid4()
    user = User(
        id=user_id, 
        email="validation@example.com", 
        name="validuser",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    
    # Create a test market
    market_id = uuid4()
    market = Market(
        id=market_id,
        name="Validation Test Market",
        type=MarketType.TEST.value.lower(),
        user_id=user_id
    )
    db_session.add(market)
    await db_session.commit()
    
    # Create a test deal
    deal_id = uuid4()
    deal = Deal(
        id=deal_id,
        title="Validation Test Deal",
        description="A test deal for validation testing",
        url="https://example.com/validation-test-deal",
        price=Decimal("79.99"),
        currency="USD",
        status=DealStatus.ACTIVE.value.lower(),
        category=MarketCategory.ELECTRONICS.value,
        user_id=user_id,
        market_id=market_id
    )
    db_session.add(deal)
    await db_session.commit()
    
    # Test invalid score (greater than 1)
    with pytest.raises(ValidationError):
        await DealScore.create_score(
            db=db_session,
            deal_id=deal.id,
            user_id=user_id,
            score=1.5,  # Invalid: > 1
            confidence=0.8
        )
    
    # Test invalid score (negative)
    with pytest.raises(ValidationError):
        await DealScore.create_score(
            db=db_session,
            deal_id=deal.id,
            user_id=user_id,
            score=-0.5,  # Invalid: < 0
            confidence=0.8
        )
    
    # Test invalid confidence (greater than 1)
    with pytest.raises(ValidationError):
        await DealScore.create_score(
            db=db_session,
            deal_id=deal.id,
            user_id=user_id,
            score=0.7,
            confidence=1.2  # Invalid: > 1
        )
    
    # Create a valid score
    valid_score = await DealScore.create_score(
        db=db_session,
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
async def test_create_score_method(db_session):
    """Test the create_score method of DealScore."""
    # Create a test user
    user_id = uuid4()
    user = User(
        id=user_id, 
        email="create_method@example.com", 
        name="methoduser",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    
    # Create a test market
    market_id = uuid4()
    market = Market(
        id=market_id,
        name="Method Test Market",
        type=MarketType.TEST.value.lower(),
        user_id=user_id
    )
    db_session.add(market)
    await db_session.commit()
    
    # Create a test deal
    deal = Deal(
        title="Create Method Test Deal",
        description="Testing the create_score method",
        url="https://example.com/create-method-test",
        price=Decimal("59.99"),
        currency="USD",
        status=DealStatus.ACTIVE.value.lower(),
        category=MarketCategory.ELECTRONICS.value,
        user_id=user_id,
        market_id=market_id
    )
    db_session.add(deal)
    await db_session.commit()
    
    # Create a score using the create_score method
    factors = {
        "price": 0.9,
        "quality": 0.8,
        "reviews": 0.7
    }
    
    score = await DealScore.create_score(
        db=db_session,
        deal_id=deal.id,
        user_id=user_id,
        score=0.85,
        confidence=0.9,
        factors=factors
    )
    
    # Verify it was saved in the database
    query = select(DealScore).where(DealScore.id == score.id)
    result = await db_session.execute(query)
    db_score = result.scalar_one()
    
    assert db_score.score == 0.85
    assert db_score.confidence == 0.9
    assert db_score.score_type == ScoreType.AI.value
    assert db_score.factors["price"] == 0.9
    assert db_score.factors["quality"] == 0.8
    assert db_score.factors["reviews"] == 0.7


@pytest.mark.asyncio
@pytest.mark.core
async def test_update_metrics(db_session):
    """Test updating metrics for a deal score."""
    # Create a test user
    user_id = uuid4()
    user = User(
        id=user_id, 
        email="test@example.com", 
        name="testuser",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    
    # Create a test market
    market_id = uuid4()
    market = Market(
        id=market_id,
        name="Metrics Test Market",
        type=MarketType.TEST.value.lower(),
        user_id=user_id
    )
    db_session.add(market)
    await db_session.commit()
    
    # Create a test deal
    deal = Deal(
        title="Metrics Update Test Deal",
        description="Testing deal score metrics updates",
        status=DealStatus.ACTIVE.value,
        market_type=MarketType.TEST.value,
        user_id=user_id,
        market_id=market_id,
        url="https://example.com/metrics-test",
        price=Decimal("99.99"),
        currency="USD",
        category=MarketCategory.ELECTRONICS.value
    )
    db_session.add(deal)
    await db_session.commit()
    
    # Create a score with initial metrics
    initial_factors = {
        "profitability": 0.6,
        "risk": 0.4
    }
    
    score = await DealScore.create_score(
        db=db_session,
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
        db=db_session,
        metrics=updated_metrics
    )
    
    # Verify metrics were updated
    query = select(DealScore).where(DealScore.id == score.id)
    result = await db_session.execute(query)
    updated_score = result.scalar_one()
    
    assert updated_score.factors == updated_metrics
    assert updated_score.factors["profitability"] == 0.8
    assert updated_score.factors["volatility"] == 0.5


@pytest.mark.asyncio
@pytest.mark.core
async def test_to_json(db_session):
    """Test the to_json method of DealScore."""
    # Create a test user
    user_id = uuid4()
    user = User(
        id=user_id, 
        email="json@example.com", 
        name="jsonuser",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    
    # Create a test market
    market_id = uuid4()
    market = Market(
        id=market_id,
        name="JSON Test Market",
        type=MarketType.TEST.value.lower(),
        user_id=user_id
    )
    db_session.add(market)
    await db_session.commit()
    
    # Create a test deal
    deal = Deal(
        title="JSON Test Deal",
        description="Testing the to_json method",
        url="https://example.com/json-test",
        price=Decimal("149.99"),
        currency="USD",
        status=DealStatus.ACTIVE.value.lower(),
        category=MarketCategory.ELECTRONICS.value,
        user_id=user_id,
        market_id=market_id
    )
    db_session.add(deal)
    await db_session.commit()
    
    # Create a score
    now = datetime.utcnow()
    factors = {
        "price": 0.8,
        "quality": 0.7,
        "reviews": 0.85
    }
    
    score = DealScore(
        deal_id=deal.id,
        user_id=user_id,
        score=0.78,
        confidence=0.92,
        score_type=ScoreType.AI.value,
        factors=factors
    )
    db_session.add(score)
    await db_session.commit()
    
    # Test to_json method
    json_data = score.to_json()
    import json
    data = json.loads(json_data)
    
    assert data["id"] == str(score.id)
    assert data["deal_id"] == str(deal.id)
    assert data["user_id"] == str(user_id)
    assert data["score"] == 0.78
    assert data["confidence"] == 0.92
    assert data["score_type"] == ScoreType.AI.value
    assert "factors" in data
    assert data["factors"]["price"] == 0.8
    assert data["factors"]["quality"] == 0.7
    assert data["factors"]["reviews"] == 0.85


@pytest.mark.asyncio
@pytest.mark.core
async def test_deal_match_creation(db_session):
    """Test creating a DealMatch in the database."""
    # Create a test user
    user_id = uuid4()
    user = User(
        id=user_id, 
        email="test@example.com", 
        name="testuser",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    
    # Create a test market
    market_id = uuid4()
    market = Market(
        id=market_id,
        name="Test Market",
        description="Market for testing",
        category=MarketCategory.ELECTRONICS.value,
        type=MarketType.TEST.value.lower(),
        status=MarketStatus.ACTIVE.value
    )
    db_session.add(market)
    
    # Create a test deal
    deal = Deal(
        title="Match Test Deal",
        description="Deal for testing match functionality",
        status=DealStatus.ACTIVE.value,
        market_type=MarketType.TEST.value,
        user_id=user_id,
        market_id=market_id
    )
    
    # Create a test goal
    goal = Goal(
        title="Test Goal",
        description="Goal for testing matches",
        status=GoalStatus.ACTIVE.value,
        user_id=user_id
    )
    
    db_session.add_all([deal, goal])
    await db_session.commit()
    
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
    
    db_session.add(match)
    await db_session.commit()
    
    # Retrieve the match
    query = select(DealMatch).where(
        (DealMatch.goal_id == goal.id) & (DealMatch.deal_id == deal.id)
    )
    result = await db_session.execute(query)
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
async def test_deal_match_relationships(db_session):
    """Test the relationships between deal matches, deals, and goals."""
    # Create a test user
    user_id = uuid4()
    user = User(
        id=user_id, 
        email="test@example.com", 
        name="testuser",
        password="hashed_password_value",
        status="active",
        email_verified=True
    )
    db_session.add(user)
    
    # Create a test market
    market_id = uuid4()
    market = Market(
        id=market_id,
        name="Test Market",
        description="Market for testing",
        category=MarketCategory.ELECTRONICS.value,
        type=MarketType.TEST.value.lower(),
        status=MarketStatus.ACTIVE.value
    )
    db_session.add(market)
    
    # Create multiple deals and goals
    deal1 = Deal(
        title="First Match Test Deal",
        description="First deal for testing matches",
        status=DealStatus.ACTIVE.value,
        market_type=MarketType.TEST.value,
        user_id=user_id,
        market_id=market_id
    )
    
    deal2 = Deal(
        title="Second Match Test Deal",
        description="Second deal for testing matches",
        status=DealStatus.ACTIVE.value,
        market_type=MarketType.TEST.value,
        user_id=user_id,
        market_id=market_id
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
    
    db_session.add_all([deal1, deal2, goal1, goal2])
    await db_session.commit()
    
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
    
    db_session.add_all([match1, match2, match3])
    await db_session.commit()
    
    # Test goal -> matched_deals relationship
    query = select(Goal).where(Goal.id == goal1.id)
    result = await db_session.execute(query)
    fetched_goal = result.scalar_one()
    
    # Refresh the goal to load the relationships
    await db_session.refresh(fetched_goal, ["matched_deals"])
    
    assert len(fetched_goal.matched_deals) == 2
    assert any(match.deal_id == deal1.id for match in fetched_goal.matched_deals)
    assert any(match.deal_id == deal2.id for match in fetched_goal.matched_deals)
    
    # Test deal -> goal_matches relationship
    query = select(Deal).where(Deal.id == deal1.id)
    result = await db_session.execute(query)
    fetched_deal = result.scalar_one()
    
    # Refresh the deal to load the relationships
    await db_session.refresh(fetched_deal, ["goal_matches"])
    
    assert len(fetched_deal.goal_matches) == 2
    assert any(match.goal_id == goal1.id for match in fetched_deal.goal_matches)
    assert any(match.goal_id == goal2.id for match in fetched_deal.goal_matches)
    
    # Test specific match relationships
    query = select(DealMatch).where(
        (DealMatch.goal_id == goal1.id) & (DealMatch.deal_id == deal1.id)
    )
    result = await db_session.execute(query)
    fetched_match = result.scalar_one()
    
    # Refresh the match to load the relationships
    await db_session.refresh(fetched_match, ["goal", "deal"])
    
    assert fetched_match.goal.id == goal1.id
    assert fetched_match.deal.id == deal1.id 