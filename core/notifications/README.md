# Templated Notification System

This module provides a standardized, template-based notification system for the AI Agentic Deals platform.

## Key Benefits

- **Standardized Notifications**: All notifications use consistent formatting and styling
- **Centralized Templates**: Single source of truth for notification content
- **Easy to Update**: Change notification texts in one place
- **Type-Safe**: Template parameters are fully typed
- **Separation of Concerns**: Business logic separated from notification content

## Architecture

The notification system is composed of three main components:

1. **Templates**: Defined in `templates.py`, these contain the content and configuration for all notifications
2. **Factory**: The `NotificationFactory` in `factory.py` creates notification parameters from templates
3. **Service**: The `TemplatedNotificationService` in `service.py` provides a high-level API for sending notifications

## Usage Examples

### Basic Usage

```python
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from core.notifications import TemplatedNotificationService

async def send_welcome_notification(db: AsyncSession, user_id: UUID):
    notification_service = TemplatedNotificationService(db)
    
    # Send a notification using a template
    await notification_service.send_notification(
        template_id="sys_registration_confirmation",
        user_id=user_id
    )
```

### Using Template Parameters

```python
async def notify_price_drop(db: AsyncSession, user_id: UUID, item_name: str, target_price: float, alert_id: UUID):
    notification_service = TemplatedNotificationService(db)
    
    # Send a notification with template parameters
    await notification_service.send_notification(
        template_id="price_drop_alert",
        user_id=user_id,
        template_params={
            "item_name": item_name,
            "target_price": f"${target_price:.2f}"
        },
        action_url=f"/price-alerts/{alert_id}"
    )
```

### Using Convenience Methods

```python
async def notify_new_device_login(db: AsyncSession, user_id: UUID, device_type: str, location: str):
    notification_service = TemplatedNotificationService(db)
    
    # Use a specialized method for security notifications
    await notification_service.send_new_device_login_notification(
        user_id=user_id,
        device_type=device_type,
        location=location
    )
```

## Adding New Templates

To add a new notification template:

1. Add the template definition to `templates.py`
2. Add the template to the `NOTIFICATION_TEMPLATES` dictionary
3. (Optional) Add a convenience method to `TemplatedNotificationService`

Example of adding a new template:

```python
# In templates.py
NEW_FEATURE_NOTIFICATION = NotificationTemplate(
    template_id="sys_new_feature",
    notification_type=NotificationType.SYSTEM,
    title="New Feature Available",
    message="We've added {feature_name} to the platform! {description}",
    default_channels=[NotificationChannel.IN_APP],
    priority=NotificationPriority.MEDIUM,
    action_required=False,
    default_metadata={"event": "new_feature"}
)

# Add to the templates dictionary
NOTIFICATION_TEMPLATES["sys_new_feature"] = NEW_FEATURE_NOTIFICATION

# In service.py
async def send_new_feature_notification(
    self,
    user_id: UUID,
    feature_name: str,
    description: str,
    **kwargs
) -> UUID:
    """Send a notification about a new feature."""
    return await self.send_system_notification(
        user_id=user_id,
        template_id="sys_new_feature",
        template_params={
            "feature_name": feature_name,
            "description": description
        },
        **kwargs
    )
```

## Best Practices

1. **Use Template IDs**: Always use the predefined template IDs
2. **Provide All Parameters**: Ensure all required template parameters are provided
3. **Use Specialized Methods**: Use convenience methods when available
4. **Add Context**: Include relevant IDs (goal_id, deal_id) when appropriate
5. **Handle Errors**: The service has built-in error handling, but check return values

## Integration with Existing Code

This system integrates with the existing `NotificationService` and uses the same database models. It provides a higher-level abstraction that makes sending notifications simpler and more consistent. 