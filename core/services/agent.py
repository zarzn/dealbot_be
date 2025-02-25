"""Agent service module."""

from typing import List, Dict, Any, Optional, Type
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import BackgroundTasks

from core.models.agent import Agent, AgentCreate, AgentUpdate, AgentType, AgentStatus
from core.repositories.agent import AgentRepository
from core.services.base import BaseService
from core.services.redis import get_redis_service
from core.exceptions import (
    AgentError,
    AgentNotFoundError,
    AgentValidationError,
    AgentCreationError,
    AgentUpdateError,
    AgentDeletionError,
    AgentStatusError,
    AgentProcessingError,
    AgentCommunicationError,
    AgentTimeoutError,
    AgentMemoryError,
    AgentDecisionError,
    AgentCoordinationError,
    DatabaseError
)

class AgentService(BaseService[Agent, AgentCreate, AgentUpdate]):
    """Service for managing agents."""

    def __init__(self, db: AsyncSession, background_tasks: Optional[BackgroundTasks] = None):
        """Initialize the service with database session and background tasks."""
        self.repository = AgentRepository(db)
        super().__init__(self.repository)
        self.db = db
        self._background_tasks = background_tasks
        self.redis = get_redis_service()

    @property
    def background_tasks(self) -> Optional[BackgroundTasks]:
        """Get background tasks."""
        return self._background_tasks

    @background_tasks.setter
    def background_tasks(self, value: Optional[BackgroundTasks]) -> None:
        """Set background tasks."""
        self._background_tasks = value

    def add_background_task(self, func: Any, *args: Any, **kwargs: Any) -> None:
        """Add a task to be executed in the background.
        
        Args:
            func: The function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Raises:
            ValueError: If background_tasks is not initialized
        """
        if self._background_tasks is None:
            raise ValueError("Background tasks not initialized")
        self._background_tasks.add_task(func, *args, **kwargs)

    async def create_goal_analyst(self, user_id: UUID, goal_id: UUID) -> Agent:
        """Create a goal analysis agent."""
        try:
            agent_data = AgentCreate(
                user_id=user_id,
                goal_id=goal_id,
                type=AgentType.GOAL_ANALYST,
                name="Goal Analyst",
                role="Analyze and understand user goals",
                backstory="I am an AI agent specialized in understanding and analyzing user goals.",
                agent_metadata={"specialization": "goal_analysis"}
            )
            return await self.create(agent_data)
        except Exception as e:
            raise AgentCreationError(f"Failed to create goal analyst: {str(e)}") from e

    async def create_deal_finder(self, user_id: UUID, goal_id: UUID) -> Agent:
        """Create a deal finder agent."""
        try:
            agent_data = AgentCreate(
                user_id=user_id,
                goal_id=goal_id,
                type=AgentType.DEAL_FINDER,
                name="Deal Finder",
                role="Search and identify potential deals",
                backstory="I am an AI agent specialized in finding the best deals that match user goals.",
                agent_metadata={"specialization": "deal_search"}
            )
            return await self.create(agent_data)
        except Exception as e:
            raise AgentCreationError(f"Failed to create deal finder: {str(e)}") from e

    async def create_price_analyst(self, user_id: UUID, goal_id: UUID) -> Agent:
        """Create a price analysis agent."""
        try:
            agent_data = AgentCreate(
                user_id=user_id,
                goal_id=goal_id,
                type=AgentType.PRICE_ANALYST,
                name="Price Analyst",
                role="Analyze prices and market trends",
                backstory="I am an AI agent specialized in analyzing prices and market trends.",
                agent_metadata={"specialization": "price_analysis"}
            )
            return await self.create(agent_data)
        except Exception as e:
            raise AgentCreationError(f"Failed to create price analyst: {str(e)}") from e

    async def create_notifier(self, user_id: UUID, goal_id: UUID) -> Agent:
        """Create a notification agent."""
        try:
            agent_data = AgentCreate(
                user_id=user_id,
                goal_id=goal_id,
                type=AgentType.NOTIFIER,
                name="Notifier",
                role="Manage notifications and user communication",
                backstory="I am an AI agent specialized in managing notifications and user communication.",
                agent_metadata={"specialization": "notifications"}
            )
            return await self.create(agent_data)
        except Exception as e:
            raise AgentCreationError(f"Failed to create notifier: {str(e)}") from e

    async def process_goal(self, goal_id: UUID) -> None:
        """Process a goal through the agent system."""
        try:
            # Get all agents for this goal
            agents = await self.repository.get_by_goal(goal_id)
            
            # Validate we have all required agents
            agent_types = {agent.type for agent in agents}
            required_types = {
                AgentType.GOAL_ANALYST,
                AgentType.DEAL_FINDER,
                AgentType.PRICE_ANALYST,
                AgentType.NOTIFIER
            }
            
            if missing_types := required_types - agent_types:
                raise AgentProcessingError(f"Missing required agents: {missing_types}")
            
            # Update agent statuses to BUSY
            for agent in agents:
                await self.repository.update_status(agent.id, AgentStatus.BUSY)
            
            try:
                # Process goal through each agent in sequence
                goal_analyst = next(a for a in agents if a.type == AgentType.GOAL_ANALYST)
                deal_finder = next(a for a in agents if a.type == AgentType.DEAL_FINDER)
                price_analyst = next(a for a in agents if a.type == AgentType.PRICE_ANALYST)
                notifier = next(a for a in agents if a.type == AgentType.NOTIFIER)
                
                # Process goal asynchronously
                await self._process_goal_async(
                    goal_analyst,
                    deal_finder,
                    price_analyst,
                    notifier
                )
                
            finally:
                # Reset agent statuses to IDLE
                for agent in agents:
                    await self.repository.update_status(agent.id, AgentStatus.IDLE)
                    
        except Exception as e:
            raise AgentProcessingError(f"Failed to process goal: {str(e)}") from e

    async def _process_goal_async(
        self,
        goal_analyst: Agent,
        deal_finder: Agent,
        price_analyst: Agent,
        notifier: Agent
    ) -> None:
        """Process goal asynchronously through all agents."""
        try:
            # Step 1: Goal Analysis
            await self._analyze_goal(goal_analyst)
            
            # Step 2: Deal Finding
            await self._find_deals(deal_finder)
            
            # Step 3: Price Analysis
            await self._analyze_prices(price_analyst)
            
            # Step 4: Notifications
            await self._send_notifications(notifier)
            
        except Exception as e:
            raise AgentProcessingError(f"Error in goal processing pipeline: {str(e)}") from e

    async def _analyze_goal(self, agent: Agent) -> None:
        """Analyze goal using goal analyst agent."""
        # Implementation
        pass

    async def _find_deals(self, agent: Agent) -> None:
        """Find deals using deal finder agent."""
        # Implementation
        pass

    async def _analyze_prices(self, agent: Agent) -> None:
        """Analyze prices using price analyst agent."""
        # Implementation
        pass

    async def _send_notifications(self, agent: Agent) -> None:
        """Send notifications using notifier agent."""
        # Implementation
        pass
