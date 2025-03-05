"""Agent model module.

This module defines the agent-related models for the AI Agentic Deals System,
including agent types, statuses, and database models.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
import enum
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, Enum as SQLEnum, Index, Integer, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import expression, text
from pydantic import BaseModel, Field

from core.models.base import Base
from core.exceptions.agent_exceptions import AgentError

class AgentType(str, enum.Enum):
    """Agent type enumeration."""
    GOAL = "goal"
    MARKET = "market"
    PRICE = "price"
    CHAT = "chat"
    # Add the missing agent types needed for tests
    GOAL_ANALYST = "goal_analyst"
    DEAL_FINDER = "deal_finder"
    PRICE_ANALYST = "price_analyst"
    NOTIFIER = "notifier"
    MARKET_ANALYST = "market_analyst"
    DEAL_NEGOTIATOR = "deal_negotiator"
    RISK_ASSESSOR = "risk_assessor"

class AgentStatus(str, enum.Enum):
    """Agent status types."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    BUSY = "busy"
    ERROR = "error"
    IDLE = "idle"  # Add the IDLE status needed for tests
    PAUSED = "paused"  # Add the PAUSED status needed for tests

class Agent(Base):
    """Agent database model."""
    __tablename__ = "agents"
    __table_args__ = (
        Index('ix_agents_type', 'agent_type'),
        Index('ix_agents_status', 'status'),
        Index('ix_agents_user', 'user_id'),
        Index('ix_agents_goal', 'goal_id'),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    goal_id: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("goals.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    agent_type: Mapped[AgentType] = mapped_column(
        SQLEnum(AgentType, values_callable=lambda x: [e.value.lower() for e in x]),
        nullable=False
    )
    status: Mapped[AgentStatus] = mapped_column(
        SQLEnum(AgentStatus, values_callable=lambda x: [e.value.lower() for e in x]), 
        nullable=False,
        default=AgentStatus.INACTIVE
    )
    description: Mapped[Optional[str]] = mapped_column(Text)
    config: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    meta_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    last_active: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"), onupdate=text("CURRENT_TIMESTAMP"))

    # Relationships
    user = relationship("User", back_populates="agents")
    goal = relationship("Goal", back_populates="agents")

    def __repr__(self) -> str:
        """String representation of the agent."""
        return f"<Agent {self.name} ({self.agent_type})>"

    async def activate(self) -> None:
        """Activate the agent."""
        self.status = AgentStatus.ACTIVE
        self.last_active = datetime.utcnow()

    async def deactivate(self) -> None:
        """Deactivate the agent."""
        self.status = AgentStatus.INACTIVE

    async def mark_busy(self) -> None:
        """Mark agent as busy."""
        self.status = AgentStatus.BUSY
        self.last_active = datetime.utcnow()

    async def mark_error(self, error: str) -> None:
        """Mark agent as having an error."""
        self.status = AgentStatus.ERROR
        self.error_count += 1
        self.last_error = error

    async def reset_error(self) -> None:
        """Reset agent error state."""
        self.error_count = 0
        self.last_error = None
        self.status = AgentStatus.INACTIVE

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