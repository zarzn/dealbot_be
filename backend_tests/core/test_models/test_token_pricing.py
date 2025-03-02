"""Tests for TokenPricing model.

This module contains tests for the TokenPricing model and related functionality.
"""

import pytest
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import select

from core.models.token_pricing import TokenPricing, ServiceType
from core.exceptions import ValidationError

# Mark all tests as asyncio tests and as core tests
pytestmark = [pytest.mark.asyncio, pytest.mark.core]


async def test_token_pricing_creation(db_session):
    """Test creating a token pricing entry."""
    now = datetime.utcnow()
    valid_from = now
    valid_to = now + timedelta(days=30)
    
    # Create a new token pricing
    token_pricing = await TokenPricing.create(
        db=db_session,
        service_type=ServiceType.CHAT.value,
        token_cost=Decimal('0.0001'),
        valid_from=valid_from,
        valid_to=valid_to,
        is_active=True
    )
    
    # Assert the token pricing was created
    assert token_pricing.id is not None
    assert token_pricing.service_type == ServiceType.CHAT.value
    assert token_pricing.token_cost == Decimal('0.0001')
    assert token_pricing.valid_from == valid_from
    assert token_pricing.valid_to == valid_to
    assert token_pricing.is_active is True
    assert token_pricing.created_at is not None
    
    # Check it exists in the database
    result = await db_session.execute(
        select(TokenPricing).where(TokenPricing.id == token_pricing.id)
    )
    db_token_pricing = result.scalars().first()
    assert db_token_pricing is not None
    assert db_token_pricing.id == token_pricing.id
    assert db_token_pricing.service_type == ServiceType.CHAT.value
    assert db_token_pricing.token_cost == Decimal('0.0001')


async def test_token_pricing_date_validation(db_session):
    """Test that token pricing validates dates correctly."""
    now = datetime.utcnow()
    
    # Test with valid_to before valid_from
    valid_from = now
    valid_to = now - timedelta(days=1)  # Before valid_from
    
    # Should raise ValidationError
    with pytest.raises(Exception) as excinfo:
        await TokenPricing.create(
            db=db_session,
            service_type=ServiceType.SEARCH.value,
            token_cost=Decimal('0.0002'),
            valid_from=valid_from,
            valid_to=valid_to,
            is_active=True
        )
    
    # Check that no pricing was created
    result = await db_session.execute(
        select(TokenPricing).where(TokenPricing.service_type == ServiceType.SEARCH.value)
    )
    assert result.scalars().first() is None


async def test_token_pricing_cost_validation(db_session):
    """Test that token pricing validates token cost correctly."""
    now = datetime.utcnow()
    valid_from = now
    valid_to = now + timedelta(days=30)
    
    # Test with negative token cost
    with pytest.raises(Exception) as excinfo:
        await TokenPricing.create(
            db=db_session,
            service_type=ServiceType.ANALYSIS.value,
            token_cost=Decimal('-0.0001'),  # Negative cost
            valid_from=valid_from,
            valid_to=valid_to,
            is_active=True
        )
    
    # Test with zero token cost
    with pytest.raises(Exception) as excinfo:
        await TokenPricing.create(
            db=db_session,
            service_type=ServiceType.ANALYSIS.value,
            token_cost=Decimal('0'),  # Zero cost
            valid_from=valid_from,
            valid_to=valid_to,
            is_active=True
        )
    
    # Check that no pricing was created
    result = await db_session.execute(
        select(TokenPricing).where(TokenPricing.service_type == ServiceType.ANALYSIS.value)
    )
    assert result.scalars().first() is None


async def test_get_active_pricing(db_session):
    """Test getting active pricing."""
    now = datetime.utcnow()
    
    # Create active pricing
    active_pricing = await TokenPricing.create(
        db=db_session,
        service_type=ServiceType.NOTIFICATION.value,
        token_cost=Decimal('0.0003'),
        valid_from=now - timedelta(days=1),
        valid_to=now + timedelta(days=30),
        is_active=True
    )
    
    # Create inactive pricing
    inactive_pricing = await TokenPricing.create(
        db=db_session,
        service_type=ServiceType.NOTIFICATION.value,
        token_cost=Decimal('0.0005'),
        valid_from=now - timedelta(days=1),
        valid_to=now + timedelta(days=30),
        is_active=False
    )
    
    # Get active pricing
    active_pricings = await TokenPricing.get_active_pricing(db=db_session)
    
    # Should only return active pricing
    assert len(active_pricings) >= 1
    assert any(p.id == active_pricing.id for p in active_pricings)
    assert not any(p.id == inactive_pricing.id for p in active_pricings)


async def test_get_by_service_type(db_session):
    """Test getting pricing by service type."""
    now = datetime.utcnow()
    
    # Create pricing for different service types
    chat_pricing = await TokenPricing.create(
        db=db_session,
        service_type=ServiceType.CHAT.value,
        token_cost=Decimal('0.0001'),
        valid_from=now - timedelta(days=1),
        valid_to=now + timedelta(days=30),
        is_active=True
    )
    
    search_pricing = await TokenPricing.create(
        db=db_session,
        service_type=ServiceType.SEARCH.value,
        token_cost=Decimal('0.0002'),
        valid_from=now - timedelta(days=1),
        valid_to=now + timedelta(days=30),
        is_active=True
    )
    
    # Get pricing by service type
    result_chat = await TokenPricing.get_by_service_type(
        db=db_session, 
        service_type=ServiceType.CHAT
    )
    
    result_search = await TokenPricing.get_by_service_type(
        db=db_session, 
        service_type=ServiceType.SEARCH
    )
    
    # Should return pricing for the specific service type
    assert result_chat is not None
    assert result_chat.service_type == ServiceType.CHAT.value
    assert result_chat.token_cost == Decimal('0.0001')
    
    assert result_search is not None
    assert result_search.service_type == ServiceType.SEARCH.value
    assert result_search.token_cost == Decimal('0.0002')


async def test_multiple_active_pricing_same_service(db_session):
    """Test behavior with multiple active pricing for the same service."""
    now = datetime.utcnow()
    
    # Create two active pricing entries for the same service
    # First one is valid now
    pricing1 = await TokenPricing.create(
        db=db_session,
        service_type=ServiceType.ANALYSIS.value,
        token_cost=Decimal('0.0004'),
        valid_from=now - timedelta(days=10),
        valid_to=now + timedelta(days=10),
        is_active=True
    )
    
    # Second one is valid in the future
    pricing2 = await TokenPricing.create(
        db=db_session,
        service_type=ServiceType.ANALYSIS.value,
        token_cost=Decimal('0.0006'),
        valid_from=now + timedelta(days=20),
        valid_to=now + timedelta(days=30),
        is_active=True
    )
    
    # Get pricing by service type
    result = await TokenPricing.get_by_service_type(
        db=db_session, 
        service_type=ServiceType.ANALYSIS
    )
    
    # Should return the currently valid pricing
    assert result is not None
    assert result.id == pricing1.id
    assert result.service_type == ServiceType.ANALYSIS.value
    assert result.token_cost == Decimal('0.0004')


async def test_update_token_pricing(db_session):
    """Test updating token pricing."""
    now = datetime.utcnow()
    
    # Create token pricing
    token_pricing = await TokenPricing.create(
        db=db_session,
        service_type=ServiceType.CHAT.value,
        token_cost=Decimal('0.0001'),
        valid_from=now,
        valid_to=now + timedelta(days=30),
        is_active=True
    )
    
    # Update token cost
    token_pricing.token_cost = Decimal('0.0002')
    db_session.add(token_pricing)
    await db_session.commit()
    await db_session.refresh(token_pricing)
    
    # Verify the update
    assert token_pricing.token_cost == Decimal('0.0002')
    
    # Update validity and status
    token_pricing.valid_to = now + timedelta(days=60)
    token_pricing.is_active = False
    db_session.add(token_pricing)
    await db_session.commit()
    await db_session.refresh(token_pricing)
    
    # Verify the updates
    assert token_pricing.valid_to == now + timedelta(days=60)
    assert token_pricing.is_active is False 