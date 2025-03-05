"""Test module for UserPreferences model.

This module contains tests for the UserPreferences model, which stores user customization
and notification preferences in the AI Agentic Deals System.
"""

import pytest
from uuid import uuid4
from sqlalchemy import select
from datetime import datetime, time, timedelta
from enum import Enum

from core.models.user_preferences import (
    UserPreferences, 
    UserPreferencesResponse,
    UserPreferencesUpdate,
    UserPreferencesCreate,
    Theme,
    Language,
    NotificationFrequency,
    NotificationTimeWindow
)
from core.models.user import User
from core.models.notification import NotificationChannel, NotificationType


@pytest.mark.asyncio
@pytest.mark.core
async def test_user_preferences_creation(db_session):
    """Test creating a UserPreferences instance."""
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
    
    # Create preferences with minimal fields
    preferences = UserPreferences(
        user_id=user_id,
        theme=Theme.DARK.value,
        language=Language.EN.value
    )
    db_session.add(preferences)
    await db_session.commit()
    
    # Verify creation
    query = select(UserPreferences).where(UserPreferences.user_id == user_id)
    result = await db_session.execute(query)
    fetched_prefs = result.scalar_one()
    
    assert fetched_prefs.id is not None
    assert fetched_prefs.user_id == user_id
    assert fetched_prefs.theme == Theme.DARK.value
    assert fetched_prefs.language == Language.EN.value
    
    # Default values
    assert fetched_prefs.minimum_priority == "low"
    assert fetched_prefs.do_not_disturb is False
    assert fetched_prefs.push_enabled is True
    assert fetched_prefs.email_digest is True
    
    # Timestamps
    assert isinstance(fetched_prefs.created_at, datetime)
    assert isinstance(fetched_prefs.updated_at, datetime)


@pytest.mark.asyncio
@pytest.mark.core
async def test_user_preferences_relationship(db_session):
    """Test the relationship between user preferences and user."""
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
    
    # Create preferences
    preferences = UserPreferences(
        user_id=user_id,
        theme=Theme.LIGHT.value,
        language=Language.FR.value
    )
    db_session.add(preferences)
    await db_session.commit()
    
    # Test preferences -> user relationship
    query = select(UserPreferences).where(UserPreferences.user_id == user_id)
    result = await db_session.execute(query)
    fetched_prefs = result.scalar_one()
    
    # Explicitly refresh the object to load relationships
    await db_session.refresh(fetched_prefs, ["user"])
    
    assert fetched_prefs.user is not None
    assert fetched_prefs.user.id == user_id
    assert fetched_prefs.user.email == "test@example.com"
    
    # Test user -> preferences relationship
    query = select(User).where(User.id == user_id)
    result = await db_session.execute(query)
    fetched_user = result.scalar_one()
    
    # Explicitly refresh the object to load relationships
    await db_session.refresh(fetched_user, ["user_preferences"])
    
    assert fetched_user.user_preferences is not None
    # Check if it's a list or a single object
    if isinstance(fetched_user.user_preferences, list):
        assert len(fetched_user.user_preferences) == 1
        assert fetched_user.user_preferences[0].id == preferences.id
        assert fetched_user.user_preferences[0].theme == Theme.LIGHT.value
        assert fetched_user.user_preferences[0].language == Language.FR.value
    else:
        assert fetched_user.user_preferences.id == preferences.id
        assert fetched_user.user_preferences.theme == Theme.LIGHT.value
        assert fetched_user.user_preferences.language == Language.FR.value


@pytest.mark.asyncio
@pytest.mark.core
async def test_user_preferences_update(db_session):
    """Test updating user preferences."""
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
    
    # Create preferences
    preferences = UserPreferences(
        user_id=user_id,
        theme=Theme.SYSTEM.value,
        language=Language.EN.value,
        timezone="UTC"
    )
    db_session.add(preferences)
    await db_session.commit()
    
    # Update preferences
    preferences.theme = Theme.DARK.value
    preferences.language = Language.DE.value
    preferences.timezone = "Europe/Berlin"
    preferences.do_not_disturb = True
    preferences.enabled_channels = ["in_app"]  # Only in-app notifications
    preferences.minimum_priority = "medium"
    preferences.push_enabled = False
    
    # Update nested JSON structures
    preferences.deal_alert_settings = {
        "threshold": "high",
        "categories": ["crypto", "stocks"]
    }
    
    await db_session.commit()
    
    # Verify updates
    query = select(UserPreferences).where(UserPreferences.user_id == user_id)
    result = await db_session.execute(query)
    updated_prefs = result.scalar_one()
    
    assert updated_prefs.theme == Theme.DARK.value
    assert updated_prefs.language == Language.DE.value
    assert updated_prefs.timezone == "Europe/Berlin"
    assert updated_prefs.do_not_disturb is True
    assert updated_prefs.enabled_channels == ["in_app"]
    assert updated_prefs.minimum_priority == "medium"
    assert updated_prefs.push_enabled is False
    assert updated_prefs.deal_alert_settings["threshold"] == "high"
    assert "crypto" in updated_prefs.deal_alert_settings["categories"]


@pytest.mark.asyncio
@pytest.mark.core
async def test_user_preferences_notification_settings(db_session):
    """Test setting notification preferences."""
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
    await db_session.commit()
    
    # Create preferences with custom notification settings
    now = datetime.utcnow()
    muted_until = now + timedelta(hours=2)
    
    preferences = UserPreferences(
        user_id=user_id,
        enabled_channels=["in_app", "email", "push"],
        notification_frequency={
            "deal": {"type": "deal", "frequency": "hourly"},
            "goal": {"type": "goal", "frequency": "daily"},
            "price_alert": {"type": "price_alert", "frequency": "immediate"},
            "token": {"type": "token", "frequency": "weekly"},
            "security": {"type": "security", "frequency": "immediate"},
            "market": {"type": "market", "frequency": "daily"},
            "system": {"type": "system", "frequency": "immediate"}
        },
        time_windows={
            "in_app": {"start_time": "08:00", "end_time": "18:00", "timezone": "UTC"},
            "email": {"start_time": "09:00", "end_time": "17:00", "timezone": "UTC"},
            "push": {"start_time": "10:00", "end_time": "20:00", "timezone": "UTC"}
        },
        muted_until=muted_until,
        do_not_disturb=True,
        push_enabled=True,
        sms_enabled=True
    )
    db_session.add(preferences)
    await db_session.commit()
    
    # Verify notification settings
    query = select(UserPreferences).where(UserPreferences.user_id == user_id)
    result = await db_session.execute(query)
    fetched_prefs = result.scalar_one()
    
    assert "push" in fetched_prefs.enabled_channels
    assert "sms" not in fetched_prefs.enabled_channels  # sms_enabled=True doesn't automatically add to enabled_channels
    assert fetched_prefs.notification_frequency["deal"]["frequency"] == "hourly"
    assert fetched_prefs.notification_frequency["goal"]["frequency"] == "daily"
    assert fetched_prefs.notification_frequency["token"]["frequency"] == "weekly"
    
    # Time windows
    assert fetched_prefs.time_windows["in_app"]["start_time"] == "08:00"
    assert fetched_prefs.time_windows["in_app"]["end_time"] == "18:00"
    assert fetched_prefs.time_windows["email"]["start_time"] == "09:00"
    assert fetched_prefs.time_windows["push"]["timezone"] == "UTC"
    
    # Other notification settings
    assert fetched_prefs.muted_until is not None
    assert fetched_prefs.do_not_disturb is True
    assert fetched_prefs.push_enabled is True
    assert fetched_prefs.sms_enabled is True


@pytest.mark.asyncio
@pytest.mark.core
async def test_user_preferences_cascading_delete(db_session):
    """Test that deleting a user cascades to user preferences."""
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
    
    # Create preferences
    preferences = UserPreferences(
        user_id=user_id,
        theme=Theme.DARK.value
    )
    db_session.add(preferences)
    await db_session.commit()
    
    # Store preference ID for later verification
    preference_id = preferences.id
    
    # Delete the user
    await db_session.delete(user)
    await db_session.commit()
    
    # Verify user is deleted
    query = select(User).where(User.id == user_id)
    result = await db_session.execute(query)
    deleted_user = result.scalar_one_or_none()
    assert deleted_user is None
    
    # Verify cascade delete of preferences
    query = select(UserPreferences).where(UserPreferences.id == preference_id)
    result = await db_session.execute(query)
    deleted_preferences = result.scalar_one_or_none()
    assert deleted_preferences is None


@pytest.mark.asyncio
@pytest.mark.core
async def test_to_dict_method(db_session):
    """Test the to_dict method of UserPreferences."""
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
    
    # Create preferences
    preferences = UserPreferences(
        user_id=user_id,
        theme=Theme.DARK.value,
        language=Language.EN.value,
        timezone="UTC",
        minimum_priority="high"
    )
    db_session.add(preferences)
    await db_session.commit()
    
    # Test to_dict method
    prefs_dict = preferences.to_dict()
    
    assert prefs_dict["user_id"] == str(user_id)
    assert prefs_dict["theme"] == Theme.DARK.value
    assert prefs_dict["language"] == Language.EN.value
    assert prefs_dict["minimum_priority"] == "high"
    assert "created_at" in prefs_dict
    assert "updated_at" in prefs_dict


@pytest.mark.asyncio
@pytest.mark.core
async def test_pydantic_models(db_session):
    """Test UserPreferences pydantic models."""
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
    
    # Create preferences
    preferences = UserPreferences(
        user_id=user_id,
        theme=Theme.DARK.value,
        language=Language.EN.value,
        timezone="America/New_York",
        minimum_priority="high",
        enabled_channels=["email", "in_app"],
        notification_frequency={
            "deal": {"type": "deal", "frequency": "daily"}
        },
        time_windows={
            "email": {"start_time": "09:00", "end_time": "17:00", "timezone": "UTC"}
        },
        do_not_disturb=False,
        email_digest=True,
        push_enabled=False,
        sms_enabled=False,
        telegram_enabled=False,
        discord_enabled=False,
        deal_alert_settings={"min_score": 0.7},
        price_alert_settings={"percentage_change": 5},
        email_preferences={"format": "html"}
    )
    db_session.add(preferences)
    await db_session.commit()
    
    # Test Create model
    create_data = {
        "user_id": user_id,
        "theme": Theme.LIGHT.value,
        "language": Language.FR.value,
        "timezone": "Europe/Paris"
    }
    create_model = UserPreferencesCreate(**create_data)
    assert create_model.user_id == user_id
    assert create_model.theme == Theme.LIGHT.value
    
    # Test Update model
    update_data = {
        "theme": Theme.SYSTEM.value,
        "minimum_priority": "medium",
        "enabled_channels": ["push", "email"]
    }
    update_model = UserPreferencesUpdate(**update_data)
    assert update_model.theme == Theme.SYSTEM.value
    assert update_model.minimum_priority == "medium"
    
    # Test Response model
    response = UserPreferencesResponse.model_validate(preferences)
    assert response.user_id == user_id
    assert response.theme == Theme.DARK.value
    assert response.language == Language.EN.value
    assert response.timezone == "America/New_York"
    assert response.enabled_channels == ["email", "in_app"]
    assert response.email_digest is True


@pytest.mark.asyncio
@pytest.mark.core
async def test_notification_time_window(db_session):
    """Test time window calculations for notifications."""
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
    
    # Create preferences with time windows
    preferences = UserPreferences(
        user_id=user_id,
        time_windows={
            "email": {"start_time": "09:00", "end_time": "17:00", "timezone": "UTC"},
            "push": {"start_time": "08:00", "end_time": "20:00", "timezone": "UTC"},
            "sms": {"start_time": "10:00", "end_time": "18:00", "timezone": "UTC"}
        }
    )
    db_session.add(preferences)
    await db_session.commit()
    
    # Test is_in_time_window method at different times
    utc_now = datetime(2023, 1, 1, 12, 0, 0)  # Noon UTC
    
    # All channels should be in window at noon
    assert preferences.is_in_time_window("email", utc_now) is True
    assert preferences.is_in_time_window("push", utc_now) is True
    assert preferences.is_in_time_window("sms", utc_now) is True
    
    # Email should be outside window at 8am
    early_morning = datetime(2023, 1, 1, 8, 0, 0)  # 8 AM UTC
    assert preferences.is_in_time_window("email", early_morning) is False
    assert preferences.is_in_time_window("push", early_morning) is True
    assert preferences.is_in_time_window("sms", early_morning) is False
    
    # All channels should be outside window at midnight
    midnight = datetime(2023, 1, 1, 0, 0, 0)  # Midnight UTC
    assert preferences.is_in_time_window("email", midnight) is False
    assert preferences.is_in_time_window("push", midnight) is False
    assert preferences.is_in_time_window("sms", midnight) is False
    
    # Test with channel not in time_windows
    assert preferences.is_in_time_window("in_app", utc_now) is True  # Default to True
    
    # Test with different timezone
    preferences.time_windows["email"]["timezone"] = "America/New_York"  # UTC-5
    ny_business_hours = datetime(2023, 1, 1, 17, 30, 0)  # 5:30 PM UTC = 12:30 PM New York
    assert preferences.is_in_time_window("email", ny_business_hours) is True
    
    ny_evening = datetime(2023, 1, 1, 23, 0, 0)  # 11 PM UTC = 6 PM New York
    assert preferences.is_in_time_window("email", ny_evening) is False 