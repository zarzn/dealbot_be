"""Test module for UserPreferences model.

This module contains tests for the UserPreferences model, which stores user customization
and notification preferences in the AI Agentic Deals System.
"""

import pytest
from uuid import uuid4
from sqlalchemy import select
from datetime import datetime, time, timedelta

from core.models.user_preferences import (
    UserPreferences, 
    UserPreferencesResponse,
    UserPreferencesUpdate,
    Theme,
    Language,
    NotificationFrequency,
    NotificationTimeWindow
)
from core.models.user import User
from core.models.notification import NotificationChannel, NotificationType


@pytest.mark.asyncio
@pytest.mark.core
async def test_user_preferences_creation(async_session):
    """Test creating user preferences in the database."""
    # Create a test user first
    user_id = uuid4()
    user = User(id=user_id, email="test@example.com", username="testuser")
    async_session.add(user)
    await async_session.commit()
    
    # Create user preferences
    preferences = UserPreferences(
        user_id=user_id,
        theme=Theme.DARK.value,
        language=Language.EN.value,
        timezone="America/New_York"
    )
    async_session.add(preferences)
    await async_session.commit()
    
    # Retrieve the preferences
    query = select(UserPreferences).where(UserPreferences.user_id == user_id)
    result = await async_session.execute(query)
    fetched_prefs = result.scalar_one()
    
    # Assertions
    assert fetched_prefs is not None
    assert fetched_prefs.id is not None
    assert fetched_prefs.user_id == user_id
    assert fetched_prefs.theme == Theme.DARK.value
    assert fetched_prefs.language == Language.EN.value
    assert fetched_prefs.timezone == "America/New_York"
    
    # Default values should be set
    assert len(fetched_prefs.enabled_channels) == 2
    assert "in_app" in fetched_prefs.enabled_channels
    assert "email" in fetched_prefs.enabled_channels
    assert fetched_prefs.notification_frequency is not None
    assert fetched_prefs.time_windows is not None
    assert fetched_prefs.do_not_disturb is False
    assert fetched_prefs.email_digest is True
    assert fetched_prefs.minimum_priority == "low"
    assert isinstance(fetched_prefs.created_at, datetime)
    assert isinstance(fetched_prefs.updated_at, datetime)


@pytest.mark.asyncio
@pytest.mark.core
async def test_user_preferences_relationship(async_session):
    """Test the relationship between user preferences and user."""
    # Create a test user
    user_id = uuid4()
    user = User(id=user_id, email="test@example.com", username="testuser")
    async_session.add(user)
    
    # Create preferences
    preferences = UserPreferences(
        user_id=user_id,
        theme=Theme.LIGHT.value,
        language=Language.FR.value
    )
    async_session.add(preferences)
    await async_session.commit()
    
    # Test preferences -> user relationship
    query = select(UserPreferences).where(UserPreferences.user_id == user_id)
    result = await async_session.execute(query)
    fetched_prefs = result.scalar_one()
    
    assert fetched_prefs.user is not None
    assert fetched_prefs.user.id == user_id
    assert fetched_prefs.user.email == "test@example.com"
    
    # Test user -> preferences relationship
    query = select(User).where(User.id == user_id)
    result = await async_session.execute(query)
    fetched_user = result.scalar_one()
    
    assert fetched_user.user_preferences is not None
    assert fetched_user.user_preferences.id == preferences.id
    assert fetched_user.user_preferences.theme == Theme.LIGHT.value
    assert fetched_user.user_preferences.language == Language.FR.value


@pytest.mark.asyncio
@pytest.mark.core
async def test_user_preferences_update(async_session):
    """Test updating user preferences."""
    # Create a test user
    user_id = uuid4()
    user = User(id=user_id, email="test@example.com", username="testuser")
    async_session.add(user)
    
    # Create preferences
    preferences = UserPreferences(
        user_id=user_id,
        theme=Theme.SYSTEM.value,
        language=Language.EN.value,
        timezone="UTC"
    )
    async_session.add(preferences)
    await async_session.commit()
    
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
    
    await async_session.commit()
    
    # Verify updates
    query = select(UserPreferences).where(UserPreferences.user_id == user_id)
    result = await async_session.execute(query)
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
async def test_user_preferences_notification_settings(async_session):
    """Test setting notification preferences."""
    # Create a test user
    user_id = uuid4()
    user = User(id=user_id, email="test@example.com", username="testuser")
    async_session.add(user)
    await async_session.commit()
    
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
    async_session.add(preferences)
    await async_session.commit()
    
    # Verify notification settings
    query = select(UserPreferences).where(UserPreferences.user_id == user_id)
    result = await async_session.execute(query)
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
async def test_user_preferences_cascading_delete(async_session):
    """Test that deleting a user cascades to user preferences."""
    # Create a test user
    user_id = uuid4()
    user = User(id=user_id, email="test@example.com", username="testuser")
    async_session.add(user)
    
    # Create preferences
    preferences = UserPreferences(
        user_id=user_id,
        theme=Theme.DARK.value
    )
    async_session.add(preferences)
    await async_session.commit()
    
    # Store preference ID for later verification
    preference_id = preferences.id
    
    # Delete the user
    await async_session.delete(user)
    await async_session.commit()
    
    # Verify user is deleted
    query = select(User).where(User.id == user_id)
    result = await async_session.execute(query)
    deleted_user = result.scalar_one_or_none()
    assert deleted_user is None
    
    # Verify cascade delete of preferences
    query = select(UserPreferences).where(UserPreferences.id == preference_id)
    result = await async_session.execute(query)
    deleted_preferences = result.scalar_one_or_none()
    assert deleted_preferences is None


@pytest.mark.asyncio
@pytest.mark.core
async def test_to_dict_method(async_session):
    """Test the to_dict method of UserPreferences."""
    # Create a test user
    user_id = uuid4()
    user = User(id=user_id, email="test@example.com", username="testuser")
    async_session.add(user)
    
    # Create preferences
    preferences = UserPreferences(
        user_id=user_id,
        theme=Theme.DARK.value,
        language=Language.EN.value,
        timezone="UTC",
        minimum_priority="high"
    )
    async_session.add(preferences)
    await async_session.commit()
    
    # Test to_dict method
    prefs_dict = preferences.to_dict()
    
    assert prefs_dict["id"] == str(preferences.id)
    assert prefs_dict["user_id"] == str(user_id)
    assert prefs_dict["theme"] == Theme.DARK.value
    assert prefs_dict["language"] == Language.EN.value
    assert prefs_dict["timezone"] == "UTC"
    assert prefs_dict["minimum_priority"] == "high"
    assert prefs_dict["enabled_channels"] == preferences.enabled_channels
    assert prefs_dict["created_at"] == preferences.created_at.isoformat()
    assert prefs_dict["updated_at"] == preferences.updated_at.isoformat()
    
    # Convert to json and back
    import json
    json_str = json.dumps(prefs_dict)
    loaded_dict = json.loads(json_str)
    
    assert loaded_dict["id"] == str(preferences.id)
    assert loaded_dict["theme"] == Theme.DARK.value


@pytest.mark.asyncio
@pytest.mark.core
async def test_pydantic_models(async_session):
    """Test the Pydantic models associated with UserPreferences."""
    # Create a test user
    user_id = uuid4()
    user = User(id=user_id, email="test@example.com", username="testuser")
    async_session.add(user)
    
    # Create preferences
    preferences = UserPreferences(
        user_id=user_id,
        theme=Theme.LIGHT.value,
        language=Language.EN.value,
        timezone="UTC",
        minimum_priority="medium"
    )
    async_session.add(preferences)
    await async_session.commit()
    
    # Test UserPreferencesResponse
    response = UserPreferencesResponse.model_validate(preferences)
    
    assert response.id == preferences.id
    assert response.user_id == user_id
    assert response.theme == Theme.LIGHT
    assert response.language == Language.EN
    assert response.timezone == "UTC"
    assert response.minimum_priority == "medium"
    assert NotificationChannel.IN_APP in response.enabled_channels
    assert NotificationChannel.EMAIL in response.enabled_channels
    
    # Create UserPreferencesUpdate
    update = UserPreferencesUpdate(
        theme=Theme.DARK,
        language=Language.FR,
        timezone="Europe/Paris",
        enabled_channels=[NotificationChannel.IN_APP, NotificationChannel.EMAIL, NotificationChannel.PUSH],
        notification_frequency={
            NotificationType.DEAL: NotificationFrequency.DAILY,
            NotificationType.GOAL: NotificationFrequency.WEEKLY
        },
        do_not_disturb=True,
        minimum_priority="high"
    )
    
    assert update.theme == Theme.DARK
    assert update.language == Language.FR
    assert update.timezone == "Europe/Paris"
    assert len(update.enabled_channels) == 3
    assert update.notification_frequency[NotificationType.DEAL] == NotificationFrequency.DAILY
    assert update.do_not_disturb is True
    assert update.minimum_priority == "high"
    
    # Update preferences with the update model
    for field, value in update.model_dump(exclude_unset=True).items():
        if field == "enabled_channels":
            preferences.enabled_channels = [channel.value for channel in value]
        elif field == "notification_frequency":
            # Convert the enum keys/values to string format for storage
            new_frequency = {}
            for notification_type, frequency in value.items():
                new_frequency[notification_type.value] = {
                    "type": notification_type.value,
                    "frequency": frequency.value
                }
            preferences.notification_frequency = new_frequency
        else:
            setattr(preferences, field, value.value if isinstance(value, Enum) else value)
    
    await async_session.commit()
    
    # Verify updates
    query = select(UserPreferences).where(UserPreferences.id == preferences.id)
    result = await async_session.execute(query)
    updated_prefs = result.scalar_one()
    
    assert updated_prefs.theme == Theme.DARK.value
    assert updated_prefs.language == Language.FR.value
    assert updated_prefs.timezone == "Europe/Paris"
    assert "push" in updated_prefs.enabled_channels
    assert updated_prefs.notification_frequency["deal"]["frequency"] == "daily"
    assert updated_prefs.notification_frequency["goal"]["frequency"] == "weekly"
    assert updated_prefs.do_not_disturb is True
    assert updated_prefs.minimum_priority == "high"


@pytest.mark.asyncio
@pytest.mark.core
async def test_notification_time_window(async_session):
    """Test NotificationTimeWindow with time objects."""
    # Create a time window
    window = NotificationTimeWindow(
        start_time=time(8, 30),
        end_time=time(17, 45),
        timezone="Europe/London"
    )
    
    assert window.start_time == time(8, 30)
    assert window.end_time == time(17, 45)
    assert window.timezone == "Europe/London"
    
    # Serialize and deserialize
    window_dict = window.model_dump()
    assert window_dict["start_time"].hour == 8
    assert window_dict["start_time"].minute == 30
    assert window_dict["end_time"].hour == 17
    assert window_dict["end_time"].minute == 45
    
    # Create from dict with string times for storage in DB
    db_format = {
        "start_time": "08:30",
        "end_time": "17:45",
        "timezone": "Europe/London"
    }
    
    # This would happen during application logic when converting from DB to model
    # Here we're just verifying it works as expected
    start_time_parts = db_format["start_time"].split(":")
    end_time_parts = db_format["end_time"].split(":")
    
    parsed_window = NotificationTimeWindow(
        start_time=time(int(start_time_parts[0]), int(start_time_parts[1])),
        end_time=time(int(end_time_parts[0]), int(end_time_parts[1])),
        timezone=db_format["timezone"]
    )
    
    assert parsed_window.start_time == time(8, 30)
    assert parsed_window.end_time == time(17, 45)
    assert parsed_window.timezone == "Europe/London" 