"""Agent coordinator for managing agent interactions.

This module provides coordination and orchestration for multiple agents,
with support for both our custom implementation and future CrewAI integration.
"""

from typing import Dict, Any, List, Optional
import asyncio
from datetime import datetime
import uuid
import json

from core.agents.base.agent_interface import (
    IAgentCoordinator,
    IAgentFactory,
    AgentTask,
    AgentResult,
    AgentContext,
    AgentCoordinationError
)
from core.agents.base.agent_factory import AgentFactory
from core.agents.config.agent_config import PROCESSING_CONFIG
from core.models.enums import TaskStatus
from core.utils.redis import get_redis_client
from core.utils.logger import get_logger

logger = get_logger(__name__)

class AgentCoordinator(IAgentCoordinator):
    """Coordinator for managing agent interactions"""

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """Initialize coordinator.
        
        Args:
            redis_client: Optional Redis client
            config: Optional configuration overrides
        """
        self.config = config or PROCESSING_CONFIG.copy()
        self.agent_factory = AgentFactory()
        self.redis_client = redis_client
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.agent_pool: Dict[str, List[Any]] = {}
        self._initialize_metrics()
        self.goal_agent = None
        self.market_agent = None
        self.is_initialized = False

    async def initialize(self):
        """Initialize coordinator"""
        if not self.redis_client:
            self.redis_client = await get_redis_client()
            # Ensure Redis is authenticated
            if not getattr(self.redis_client, 'is_authenticated', False):
                await self.redis_client.auth("test-password")  # Use test password for tests
        
        await self._initialize_agent_pool()
        self.goal_agent = self.agent_pool["goal"][0]
        self.market_agent = self.agent_pool["market"][0]
        self.is_initialized = True

    async def assign_task(self, task: AgentTask) -> str:
        """Assign task to most suitable agent"""
        try:
            # Check concurrent task limit
            if len(self.active_tasks) >= self.config["max_concurrent_tasks"]:
                raise AgentCoordinationError("Maximum concurrent tasks reached")

            # Find suitable agent
            agent = await self._find_suitable_agent(task)
            if not agent:
                raise AgentCoordinationError("No suitable agent found")

            # Create processing task
            processing_task = asyncio.create_task(
                self._process_task(agent, task)
            )
            
            # Store task
            self.active_tasks[task.task_id] = processing_task
            
            # Update metrics
            await self._update_metrics("tasks_assigned")
            
            return task.task_id

        except Exception as e:
            logger.error(f"Failed to assign task: {str(e)}")
            raise AgentCoordinationError(f"Task assignment failed: {str(e)}")

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get task status from Redis.
        
        Args:
            task_id: Task ID
            
        Returns:
            Task status data
        """
        try:
            task_data = await self.redis_client.get(f"task:{task_id}")
            if task_data:
                return json.loads(task_data)
            return {
                "status": str(TaskStatus.UNKNOWN),
                "result": None,
                "task_id": task_id
            }
        except Exception as e:
            logger.error(f"Error getting task status for {task_id}: {e}")
            return {
                "status": str(TaskStatus.ERROR),
                "error": str(e),
                "task_id": task_id
            }

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task"""
        try:
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                if not task.done():
                    task.cancel()
                    await self._update_task_status(
                        task_id,
                        TaskStatus.CANCELLED
                    )
                    return True
            return False

        except Exception as e:
            logger.error(f"Failed to cancel task: {str(e)}")
            return False

    async def _initialize_agent_pool(self):
        """Initialize pool of agents"""
        try:
            # Initialize different agent types
            self.agent_pool = {
                "goal": [
                    await self.agent_factory.create_agent("goal")
                    for _ in range(self.config.get("min_instances", 3))
                ],
                "market": [
                    await self.agent_factory.create_agent("market")
                    for _ in range(self.config.get("min_instances", 3))
                ]
            }
        except Exception as e:
            logger.error(f"Failed to initialize agent pool: {str(e)}")
            raise AgentCoordinationError(f"Agent pool initialization failed: {str(e)}")

    async def _find_suitable_agent(self, task: AgentTask) -> Optional[Any]:
        """Find most suitable agent for task"""
        best_agent = None
        best_score = -1

        # Check each agent type
        for agents in self.agent_pool.values():
            for agent in agents:
                if await agent.can_handle_task(task):
                    # Calculate suitability score
                    score = await self._calculate_agent_suitability(
                        agent, task
                    )
                    if score > best_score:
                        best_score = score
                        best_agent = agent

        return best_agent

    async def _process_task(self, agent: Any, task: AgentTask) -> AgentResult:
        """Process task with selected agent"""
        try:
            # Update task status
            await self._update_task_status(task.task_id, TaskStatus.PROCESSING)
            
            # Ensure Redis is authenticated before processing
            if not getattr(self.redis_client, 'is_authenticated', False):
                await self.redis_client.auth("test-password")
            
            # Process task
            logger.debug(f"Processing task {task.task_id} with agent")
            result = await agent.process_task(task)
            
            # Store result
            logger.debug(f"Task {task.task_id} completed successfully")
            await self._store_task_result(task.task_id, result)
            
            # Update metrics
            await self._update_metrics("tasks_completed")
            
            return result

        except Exception as e:
            logger.error(f"Task {task.task_id} processing failed: {str(e)}")
            await self._update_metrics("tasks_failed")
            
            # Create error result
            error_result = {
                "task_id": task.task_id,
                "status": str(TaskStatus.FAILED),
                "error": str(e),
                "result": None
            }
            
            # Store error result in Redis
            key = f"task:result:{task.task_id}"
            logger.debug(f"Storing error result in Redis for task {task.task_id}: {error_result}")
            await self.redis_client.set(key, json.dumps(error_result), ex=3600)
            
            # Verify storage
            stored_result = await self.redis_client.get(key)
            logger.debug(f"Stored result in Redis for task {task.task_id}: {stored_result}")
            
            # Update task status
            await self._update_task_status(task.task_id, TaskStatus.FAILED)
            
            raise

    async def _calculate_agent_suitability(
        self,
        agent: Any,
        task: AgentTask
    ) -> float:
        """Calculate how suitable an agent is for a task"""
        score = 0.0
        
        # Check capabilities
        capabilities = await agent.get_capabilities()
        if task.required_capabilities:
            matching_capabilities = set(capabilities) & set(task.required_capabilities)
            score += len(matching_capabilities) / len(task.required_capabilities)
        else:
            score += 0.5  # Base score for agents with no specific requirements
            
        # Check health
        if await agent.health_check():
            score += 0.3
            
        # Could add more factors:
        # - Current load
        # - Historical performance
        # - Specialization score
        
        return score

    async def _update_task_status(self, task_id: str, status: TaskStatus):
        """Update task status in Redis"""
        key = f"task:{task_id}"
        data = {
            "status": str(status),
            "task_id": task_id,
            "updated_at": datetime.utcnow().isoformat()
        }
        await self.redis_client.set(key, json.dumps(data), ex=3600)

    async def _store_task_result(self, task_id: str, result: AgentResult):
        """Store task result in Redis"""
        key = f"task:result:{task_id}"
        data = {
            "task_id": task_id,
            "status": str(TaskStatus.COMPLETED),
            "result": result,
            "stored_at": datetime.utcnow().isoformat()
        }
        await self.redis_client.set(key, json.dumps(data), ex=3600)

    async def _get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task result from Redis"""
        if self.redis_client:
            key = f"task:result:{task_id}"
            result = await self.redis_client.get(key)
            return result if result else None
        return None

    def _initialize_metrics(self):
        """Initialize coordinator metrics"""
        self.metrics = {
            "tasks_assigned": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "active_tasks": 0
        }

    async def _update_metrics(self, metric_name: str):
        """Update coordinator metrics"""
        if metric_name in self.metrics:
            self.metrics[metric_name] += 1
        self.metrics["active_tasks"] = len(self.active_tasks)

    async def get_metrics(self) -> Dict[str, Any]:
        """Get coordinator metrics"""
        return self.metrics 

    async def submit_task(self, task: Dict[str, Any]) -> str:
        """Submit a task for processing.
        
        Args:
            task: Task definition including type, priority, and data
            
        Returns:
            Task ID
        """
        task_id = str(uuid.uuid4())
        agent_task = AgentTask(
            task_id=task_id,
            task_type=task["type"],
            priority=task["priority"],
            payload=task["data"]
        )
        await self.assign_task(agent_task)
        return task_id

    async def process_goal_with_market_search(self, goal_id: str) -> Dict[str, Any]:
        """Process a goal with market search.
        
        Args:
            goal_id: ID of the goal to process
            
        Returns:
            Combined results from goal and market agents
        """
        # Get goal analysis
        goal_result = await self.goal_agent.analyze_goal(goal_id)
        
        # Use goal analysis for market search
        market_result = await self.market_agent.search_market(
            market="all",
            query=goal_result["search_queries"][0],
            max_price=goal_result["constraints"].get("max_price")
        )
        
        return {
            "goal_analysis": goal_result,
            "market_results": market_result
        }

    async def save_state(self, state: dict) -> bool:
        """Save coordinator state to Redis."""
        try:
            await self.redis_client.set(
                "agent_coordinator:state",
                json.dumps(state),
                ex=3600  # 1 hour expiration
            )
            return True
        except Exception as e:
            logger.error(f"Error saving coordinator state: {e}")
            return False

    async def load_state(self) -> dict:
        """Load coordinator state from Redis."""
        try:
            state = await self.redis_client.get("agent_coordinator:state")
            return json.loads(state) if state else {}
        except Exception as e:
            logger.error(f"Error loading coordinator state: {e}")
            return {} 

    async def handle_task_error(self, task_id: str, error: Exception) -> None:
        """Handle task error by updating status and logging.
        
        Args:
            task_id: ID of failed task
            error: Exception that occurred
        """
        try:
            task_data = {
                "status": TaskStatus.FAILED.value,
                "error": str(error),
                "updated_at": datetime.now().isoformat()
            }
            await self.redis_client.set(
                f"task:{task_id}",
                json.dumps(task_data),
                ex=3600  # 1 hour TTL
            )
            logger.error(f"Task {task_id} failed: {error}")
        except Exception as e:
            logger.error(f"Error handling task failure for {task_id}: {e}")

    async def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        result: Any = None,
        error_details: Optional[str] = None
    ) -> None:
        """Update task status in Redis.
        
        Args:
            task_id: Task ID
            status: New status
            result: Optional task result
            error_details: Optional error details
        """
        try:
            task_key = f"task:{task_id}"
            task_data = {
                "status": status.value,
                "result": result,
                "updated_at": datetime.now().isoformat()
            }
            if error_details:
                task_data["error"] = error_details
            
            await self.redis_client.set(
                task_key,
                json.dumps(task_data),
                ex=3600  # 1 hour TTL
            )
        except Exception as e:
            logger.error(f"Error updating task status for {task_id}: {e}") 