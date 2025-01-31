"""Notification model module.

This module defines the notification-related models for the AI Agentic Deals System,
including notification types, delivery methods, and database models.
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, Optional, List
from uuid import UUID, uuid4
import json
import logging
from pydantic import BaseModel, Field, validator, HttpUrl
from sqlalchemy import (
    Column, String, DateTime, Boolean, ForeignKey, Text,
    Index, CheckConstraint, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import expression

from backend.core.models.base import Base
from backend.core.exceptions import NotificationError

logger = logging.getLogger(__name__)

class NotificationType(str, Enum):
    """Notification types"""
    DEAL_MATCH = "deal_match"
    GOAL_COMPLETED = "goal_completed"
    GOAL_EXPIRED = "goal_expired"
    PRICE_DROP = "price_drop"
    TOKEN_LOW = "token_low"
    SYSTEM = "system"
    CUSTOM = "custom"

class NotificationChannel(str, Enum):
    """Notification delivery channels"""
    IN_APP = "in_app"
    EMAIL = "email"
    PUSH = "push"
    SMS = "sms"
    TELEGRAM = "telegram"
    DISCORD = "discord"

class NotificationPriority(str, Enum):
    """Notification priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class NotificationStatus(str, Enum):
    """Notification status types"""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    CANCELLED = "cancelled"

class NotificationBase(BaseModel):
    """Base notification model"""
    title: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1, max_length=5000)
    type: NotificationType
    channels: List[NotificationChannel] = Field(default=[NotificationChannel.IN_APP])
    priority: NotificationPriority = Field(default=NotificationPriority.MEDIUM)
    data: Optional[Dict[str, Any]] = Field(default=None)
    metadata: Optional[Dict[str, Any]] = Field(default=None)
    action_url: Optional[HttpUrl] = None
    expires_at: Optional[datetime] = None

    @validator('channels')
    def validate_channels(cls, v: List[NotificationChannel]) -> List[NotificationChannel]:
        """Validate notification channels."""
        if not v:
            raise ValueError("At least one notification channel is required")
        return list(set(v))  # Remove duplicates

    @validator('expires_at')
    def validate_expiry(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Validate expiry date is in the future."""
        if v is not None and v <= datetime.utcnow():
            raise ValueError("Expiry date must be in the future")
        return v

class NotificationCreate(NotificationBase):
    """Schema for creating a notification"""
    user_id: UUID
    goal_id: Optional[UUID] = None
    deal_id: Optional[UUID] = None
    schedule_for: Optional[datetime] = None

class NotificationUpdate(BaseModel):
    """Schema for updating a notification"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    message: Optional[str] = Field(None, min_length=1, max_length=5000)
    channels: Optional[List[NotificationChannel]] = None
    priority: Optional[NotificationPriority] = None
    data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    action_url: Optional[HttpUrl] = None
    status: Optional[NotificationStatus] = None
    error: Optional[str] = None

class NotificationResponse(NotificationBase):
    """Schema for notification response"""
    id: UUID
    user_id: UUID
    goal_id: Optional[UUID]
    deal_id: Optional[UUID]
    status: NotificationStatus
    created_at: datetime
    schedule_for: Optional[datetime]
    sent_at: Optional[datetime]
    delivered_at: Optional[datetime]
    read_at: Optional[datetime]
    error: Optional[str]

    class Config:
        """Pydantic model configuration."""
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v),
            NotificationType: lambda v: v.value,
            NotificationChannel: lambda v: v.value,
            NotificationPriority: lambda v: v.value,
            NotificationStatus: lambda v: v.value
        }

class Notification(Base):
    """Notification database model"""
    __tablename__ = "notifications"
    __table_args__ = (
        Index('ix_notifications_user_status', 'user_id', 'status'),
        Index('ix_notifications_goal', 'goal_id'),
        Index('ix_notifications_deal', 'deal_id'),
        Index('ix_notifications_schedule', 'schedule_for', 'status'),
        CheckConstraint(
            "(sent_at IS NULL) OR (sent_at >= created_at)",
            name="ch_sent_after_created"
        ),
        CheckConstraint(
            "(delivered_at IS NULL) OR (delivered_at >= sent_at)",
            name="ch_delivered_after_sent"
        ),
        CheckConstraint(
            "(read_at IS NULL) OR (read_at >= delivered_at)",
            name="ch_read_after_delivered"
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    goal_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("goals.id", ondelete="SET NULL"))
    deal_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("deals.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[NotificationType] = mapped_column(SQLEnum(NotificationType), nullable=False)
    channels: Mapped[List[NotificationChannel]] = mapped_column(JSONB, nullable=False, default=[NotificationChannel.IN_APP.value])
    priority: Mapped[NotificationPriority] = mapped_column(
        SQLEnum(NotificationPriority),
        nullable=False,
        default=NotificationPriority.MEDIUM
    )
    status: Mapped[NotificationStatus] = mapped_column(
        SQLEnum(NotificationStatus),
        nullable=False,
        default=NotificationStatus.PENDING,
        server_default=NotificationStatus.PENDING.value
    )
    data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    action_url: Mapped[Optional[str]] = mapped_column(Text)
    schedule_for: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=expression.func.now()
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    user = relationship("User", back_populates="notifications")
    goal = relationship("Goal", back_populates="notifications")
    deal = relationship("Deal", back_populates="notifications")

    def __repr__(self) -> str:
        """String representation of the notification."""
        return f"<Notification {self.type.value}: {self.title}>"

    def to_json(self) -> str:
        """Convert notification to JSON string."""
        return json.dumps({
            'id': str(self.id),
            'user_id': str(self.user_id),
            'goal_id': str(self.goal_id) if self.goal_id else None,
            'deal_id': str(self.deal_id) if self.deal_id else None,
            'title': self.title,
            'message': self.message,
            'type': self.type.value,
            'channels': [ch.value for ch in self.channels],
            'priority': self.priority.value,
            'status': self.status.value,
            'data': self.data,
            'metadata': self.metadata,
            'action_url': str(self.action_url) if self.action_url else None,
            'schedule_for': self.schedule_for.isoformat() if self.schedule_for else None,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'delivered_at': self.delivered_at.isoformat() if self.delivered_at else None,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'error': self.error
        })

    async def mark_sent(self, error: Optional[str] = None) -> None:
        """Mark notification as sent."""
        self.sent_at = datetime.utcnow()
        self.status = NotificationStatus.SENT if not error else NotificationStatus.FAILED
        self.error = error

    async def mark_delivered(self) -> None:
        """Mark notification as delivered."""
        self.delivered_at = datetime.utcnow()
        self.status = NotificationStatus.DELIVERED

    async def mark_read(self) -> None:
        """Mark notification as read."""
        self.read_at = datetime.utcnow()
        self.status = NotificationStatus.READ

    async def process_delivery(
        self,
        db,
        channel: NotificationChannel,
        delivery_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Process notification delivery for a specific channel."""
        try:
            if channel not in self.channels:
                raise NotificationError(f"Channel {channel.value} not enabled for this notification")

            if self.status not in [NotificationStatus.PENDING, NotificationStatus.SENT]:
                raise NotificationError(f"Cannot process delivery in {self.status.value} status")

            if self.expires_at and self.expires_at <= datetime.utcnow():
                self.status = NotificationStatus.CANCELLED
                self.error = "Notification expired"
                await db.commit()
                logger.warning(
                    f"Notification expired",
                    extra={
                        'id': str(self.id),
                        'channel': channel.value,
                        'expires_at': self.expires_at.isoformat()
                    }
                )
                return

            # Update delivery data
            if delivery_data:
                if not self.data:
                    self.data = {}
                self.data[f"{channel.value}_delivery"] = delivery_data

            # Update status
            await self.mark_sent()
            await db.commit()

            logger.info(
                f"Processed notification delivery",
                extra={
                    'id': str(self.id),
                    'channel': channel.value,
                    'user_id': str(self.user_id)
                }
            )

        except Exception as e:
            await db.rollback()
            self.error = str(e)
            self.status = NotificationStatus.FAILED
            await db.commit()

            logger.error(
                f"Failed to process notification delivery",
                extra={
                    'id': str(self.id),
                    'channel': channel.value,
                    'error': str(e)
                }
            )
            raise NotificationError(f"Delivery failed: {str(e)}")

    async def retry_delivery(self, db) -> None:
        """Retry failed notification delivery."""
        try:
            if self.status != NotificationStatus.FAILED:
                raise NotificationError("Can only retry failed notifications")

            self.status = NotificationStatus.PENDING
            self.error = None
            await db.commit()

            logger.info(
                f"Reset notification for retry",
                extra={
                    'id': str(self.id),
                    'user_id': str(self.user_id)
                }
            )

        except Exception as e:
            await db.rollback()
            logger.error(
                f"Failed to reset notification for retry",
                extra={
                    'id': str(self.id),
                    'error': str(e)
                }
            )
            raise NotificationError(f"Failed to reset notification: {str(e)}")

    @classmethod
    async def create_notification(
        cls,
        db,
        user_id: UUID,
        title: str,
        message: str,
        type: NotificationType,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        channels: Optional[List[NotificationChannel]] = None,
        goal_id: Optional[UUID] = None,
        deal_id: Optional[UUID] = None,
        data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        action_url: Optional[str] = None,
        schedule_for: Optional[datetime] = None,
        expires_at: Optional[datetime] = None
    ) -> 'Notification':
        """Create a new notification with proper validation."""
        try:
            # Set default channels if none provided
            if not channels:
                channels = [NotificationChannel.IN_APP]

            # Validate expiry and schedule times
            now = datetime.utcnow()
            if expires_at and expires_at <= now:
                raise NotificationError("Expiry time must be in the future")
            if schedule_for and schedule_for <= now:
                raise NotificationError("Schedule time must be in the future")

            notification = cls(
                user_id=user_id,
                title=title,
                message=message,
                type=type,
                priority=priority,
                channels=channels,
                goal_id=goal_id,
                deal_id=deal_id,
                data=data,
                metadata=metadata,
                action_url=action_url,
                schedule_for=schedule_for,
                expires_at=expires_at
            )
            db.add(notification)
            await db.commit()
            await db.refresh(notification)

            logger.info(
                f"Created new notification",
                extra={
                    'id': str(notification.id),
                    'user_id': str(user_id),
                    'type': type.value,
                    'priority': priority.value
                }
            )
            return notification

        except Exception as e:
            await db.rollback()
            logger.error(
                f"Failed to create notification",
                extra={
                    'user_id': str(user_id),
                    'type': type.value,
                    'error': str(e)
                }
            )
            if isinstance(e, NotificationError):
                raise
            raise NotificationError(f"Failed to create notification: {str(e)}")

    @classmethod
    async def get_pending_notifications(
        cls,
        db,
        user_id: Optional[UUID] = None,
        channel: Optional[NotificationChannel] = None,
        limit: int = 100
    ) -> List['Notification']:
        """Get pending notifications with optional filtering."""
        try:
            query = db.query(cls).filter(cls.status == NotificationStatus.PENDING)

            if user_id:
                query = query.filter(cls.user_id == user_id)
            if channel:
                query = query.filter(cls.channels.contains([channel]))

            query = query.order_by(cls.priority.desc(), cls.created_at.asc()).limit(limit)
            return await query.all()

        except Exception as e:
            logger.error(
                f"Failed to get pending notifications",
                extra={
                    'user_id': str(user_id) if user_id else None,
                    'channel': channel.value if channel else None,
                    'error': str(e)
                }
            )
            raise NotificationError(f"Failed to get pending notifications: {str(e)}")

    @classmethod
    async def aggregate_notifications(
        cls,
        db,
        user_id: UUID,
        type: NotificationType,
        time_window: timedelta,
        max_count: int = 5
    ) -> Optional['Notification']:
        """Aggregate similar notifications within a time window."""
        try:
            # Get recent notifications of the same type
            cutoff_time = datetime.utcnow() - time_window
            recent_notifications = await db.query(cls).filter(
                cls.user_id == user_id,
                cls.type == type,
                cls.created_at >= cutoff_time,
                cls.status.in_([NotificationStatus.PENDING, NotificationStatus.SENT])
            ).order_by(cls.created_at.desc()).all()

            if not recent_notifications:
                return None

            if len(recent_notifications) <= 1:
                return recent_notifications[0]

            # Create aggregated notification
            count = len(recent_notifications)
            if count > max_count:
                title = f"{count} New {type.value.replace('_', ' ').title()} Notifications"
                message = f"You have {count} new notifications of type {type.value.replace('_', ' ')}."
            else:
                title = recent_notifications[0].title
                message = "\n".join(n.message for n in recent_notifications[:max_count])

            # Combine data and metadata
            combined_data = {}
            combined_metadata = {}
            notification_ids = []
            for n in recent_notifications:
                if n.data:
                    combined_data.update(n.data)
                if n.metadata:
                    combined_metadata.update(n.metadata)
                notification_ids.append(str(n.id))

            # Create new aggregated notification
            aggregated = await cls.create_notification(
                db=db,
                user_id=user_id,
                title=title,
                message=message,
                type=type,
                priority=max(n.priority for n in recent_notifications),
                channels=list(set().union(*[n.channels for n in recent_notifications])),
                data={
                    "aggregated": True,
                    "count": count,
                    "notification_ids": notification_ids,
                    **combined_data
                },
                metadata={
                    "aggregated": True,
                    "original_notifications": notification_ids,
                    **combined_metadata
                }
            )

            # Mark original notifications as delivered
            for notification in recent_notifications:
                notification.status = NotificationStatus.DELIVERED
                notification.delivered_at = datetime.utcnow()
                notification.metadata = {
                    **(notification.metadata or {}),
                    "aggregated_into": str(aggregated.id)
                }

            await db.commit()
            logger.info(
                f"Aggregated {count} notifications",
                extra={
                    'user_id': str(user_id),
                    'type': type.value,
                    'aggregated_id': str(aggregated.id)
                }
            )
            return aggregated

        except Exception as e:
            await db.rollback()
            logger.error(
                f"Failed to aggregate notifications",
                extra={
                    'user_id': str(user_id),
                    'type': type.value,
                    'error': str(e)
                }
            )
            raise NotificationError(f"Failed to aggregate notifications: {str(e)}")

    @classmethod
    async def batch_create(
        cls,
        db,
        notifications: List[Dict[str, Any]]
    ) -> List['Notification']:
        """Create multiple notifications in a batch."""
        try:
            created = []
            for data in notifications:
                try:
                    notification = await cls.create_notification(db=db, **data)
                    created.append(notification)
                except Exception as e:
                    logger.error(
                        f"Failed to create notification in batch",
                        extra={
                            'data': data,
                            'error': str(e)
                        }
                    )
                    continue

            logger.info(
                f"Created {len(created)} notifications in batch",
                extra={'total_attempted': len(notifications)}
            )
            return created

        except Exception as e:
            await db.rollback()
            logger.error(
                f"Failed to process notification batch",
                extra={'error': str(e)}
            )
            raise NotificationError(f"Failed to process notification batch: {str(e)}")

    @classmethod
    async def batch_process(
        cls,
        db,
        notifications: List['Notification'],
        channel: NotificationChannel,
        delivery_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, int]:
        """Process multiple notifications for delivery in a batch."""
        try:
            results = {
                'success': 0,
                'failed': 0,
                'skipped': 0
            }

            for notification in notifications:
                try:
                    if notification.status not in [NotificationStatus.PENDING, NotificationStatus.SENT]:
                        results['skipped'] += 1
                        continue

                    await notification.process_delivery(db, channel, delivery_data)
                    results['success'] += 1

                except Exception as e:
                    results['failed'] += 1
                    logger.error(
                        f"Failed to process notification in batch",
                        extra={
                            'id': str(notification.id),
                            'error': str(e)
                        }
                    )
                    continue

            logger.info(
                f"Processed batch of notifications",
                extra={
                    'channel': channel.value,
                    'results': results
                }
            )
            return results

        except Exception as e:
            await db.rollback()
            logger.error(
                f"Failed to process notification batch",
                extra={
                    'channel': channel.value,
                    'error': str(e)
                }
            )
            raise NotificationError(f"Failed to process notification batch: {str(e)}") 