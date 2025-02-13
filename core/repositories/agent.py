"""Agent repository module."""

from typing import Optional, List, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.sql import and_

from core.models.agent import Agent, AgentStatus, AgentType
from core.repositories.base import BaseRepository
from core.exceptions import (
    AgentNotFoundError,
    AgentValidationError,
    AgentCreationError,
    AgentUpdateError,
    AgentDeletionError,
    DatabaseError
)

class AgentRepository(BaseRepository[Agent]):
    """Repository for managing agent data."""

    def __init__(self, db: AsyncSession):
        """Initialize the repository with a database session."""
        super().__init__(db, Agent)

    async def get_by_id(self, agent_id: UUID) -> Optional[Agent]:
        """Get an agent by ID."""
        try:
            agent = await super().get_by_id(agent_id)
            if not agent:
                raise AgentNotFoundError(f"Agent with ID {agent_id} not found")
            return agent
        except Exception as e:
            raise DatabaseError(f"Error getting agent by ID: {str(e)}") from e

    async def get_by_user(self, user_id: UUID) -> List[Agent]:
        """Get all agents for a user."""
        try:
            query = self.filter(Agent.user_id == user_id)
            result = await self.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            raise DatabaseError(f"Error getting agents for user: {str(e)}") from e

    async def update_status(self, agent_id: UUID, status: AgentStatus) -> Agent:
        """Update the status of an agent."""
        try:
            agent = await self.update(agent_id, status=status)
            if not agent:
                raise AgentNotFoundError(f"Agent with ID {agent_id} not found")
            return agent
        except Exception as e:
            raise AgentUpdateError(f"Error updating agent status: {str(e)}") from e

    async def update_agent_metadata(self, agent_id: UUID, agent_metadata: Dict[str, Any]) -> Agent:
        """Update the metadata of an agent."""
        try:
            agent = await self.update(agent_id, agent_metadata=agent_metadata)
            if not agent:
                raise AgentNotFoundError(f"Agent with ID {agent_id} not found")
            return agent
        except Exception as e:
            raise AgentUpdateError(f"Error updating agent metadata: {str(e)}") from e

    async def delete_by_id(self, agent_id: UUID) -> None:
        """Delete an agent by ID."""
        try:
            deleted = await self.delete(agent_id)
            if not deleted:
                raise AgentNotFoundError(f"Agent with ID {agent_id} not found")
        except Exception as e:
            raise AgentDeletionError(f"Error deleting agent: {str(e)}") from e

    async def get_active_agents(self) -> List[Agent]:
        """Get all active agents."""
        try:
            query = self.filter(Agent.status == AgentStatus.ACTIVE)
            result = await self.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            raise DatabaseError(f"Error getting active agents: {str(e)}") from e

    async def get_by_type(self, agent_type: AgentType) -> List[Agent]:
        """Get agents by type."""
        try:
            query = self.filter(Agent.type == agent_type)
            result = await self.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            raise DatabaseError(f"Error getting agents by type: {str(e)}") from e

    async def get_by_goal(self, goal_id: UUID) -> List[Agent]:
        """Get agents assigned to a goal."""
        try:
            query = self.filter(Agent.goal_id == goal_id)
            result = await self.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            raise DatabaseError(f"Error getting agents by goal: {str(e)}") from e 