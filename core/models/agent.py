"""Agent model module."""

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
import enum
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column
from pydantic import BaseModel, Field

from core.models.base import Base

class AgentStatus(str, enum.Enum):
    """Agent status types."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    BUSY = "busy"
    ERROR = "error"

class AgentType(str, enum.Enum):
    """Agent types."""
    GOAL_ANALYST = "goal_analyst"
    DEAL_FINDER = "deal_finder"
    PRICE_ANALYST = "price_analyst"
    NOTIFIER = "notifier"

class Agent(Base):
    """Agent database model."""
    __tablename__ = "agents"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    goal_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("goals.id", ondelete="SET NULL"), nullable=True)
    type: Mapped[str] = mapped_column(SQLEnum(AgentType), nullable=False)
    status: Mapped[str] = mapped_column(SQLEnum(AgentStatus), default=AgentStatus.ACTIVE)
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(255))
    backstory: Mapped[str] = mapped_column(String(1000))
    agent_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    last_active: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="agents")
    goal = relationship("Goal", back_populates="agents")

    def __repr__(self) -> str:
        """String representation of the agent."""
        return f"<Agent {self.name} ({self.type})>"

class AgentCreate(BaseModel):
    """Model for creating a new agent."""
    user_id: UUID
    goal_id: Optional[UUID] = None
    type: AgentType
    name: str = Field(..., min_length=1, max_length=255)
    role: str = Field(..., min_length=1, max_length=255)
    backstory: str = Field(..., min_length=1, max_length=1000)
    agent_metadata: Optional[Dict[str, Any]] = None

class AgentUpdate(BaseModel):
    """Model for updating an agent."""
    goal_id: Optional[UUID] = None
    status: Optional[AgentStatus] = None
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    role: Optional[str] = Field(None, min_length=1, max_length=255)
    backstory: Optional[str] = Field(None, min_length=1, max_length=1000)
    agent_metadata: Optional[Dict[str, Any]] = None

class AgentResponse(BaseModel):
    """Response model for Agent."""
    id: UUID
    user_id: UUID
    goal_id: Optional[UUID]
    type: AgentType
    status: AgentStatus
    name: str
    role: str
    backstory: str
    agent_metadata: Optional[Dict[str, Any]]
    last_active: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        """Pydantic model configuration."""
        from_attributes = True 