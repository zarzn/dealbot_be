"""Agent coordinator for managing agent interactions.

This module provides coordination and orchestration for multiple agents,
with support for both our custom implementation and future CrewAI integration.
"""

from typing import Dict, Any, List, Optional
import asyncio
from datetime import datetime
import uuid

from core.agents.base.agent_interface import (
    IAgentCoordinator,
    IAgentFactory,
    AgentTask,
    AgentResult,
    AgentContext,
    AgentCoordinationError
)
from core.agents.base.agent_adapter import AgentFactory
from core.agents.config.agent_config import PROCESSING_CONFIG
from core.utils.redis import get_redis_client
from core.utils.logger import get_logger

logger = get_logger(__name__)

class TaskStatus:
    """Task status constants"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class AgentCoordinator(IAgentCoordinator):
    """Coordinator for managing agent interactions"""

    def __init__(self):
        self.agent_factory = AgentFactory()
        self.redis_client = None
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.agent_pool: Dict[str, List[Any]] = {}
        self._initialize_metrics()

    async def initialize(self):
        """Initialize coordinator"""
        self.redis_client = await get_redis_client()
        await self._initialize_agent_pool()

    async def assign_task(self, task: AgentTask) -> str:
        """Assign task to most suitable agent"""
        try:
            # Check concurrent task limit
            if len(self.active_tasks) >= PROCESSING_CONFIG["max_concurrent_tasks"]:
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
        """Get status of a task"""
        try:
            # Check active tasks
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                if task.done():
                    try:
                        result = task.result()
                        status = TaskStatus.COMPLETED
                    except Exception as e:
                        result = {"error": str(e)}
                        status = TaskStatus.FAILED
                else:
                    result = None
                    status = TaskStatus.PROCESSING
            else:
                # Check Redis for completed task
                result = await self._get_task_result(task_id)
                status = TaskStatus.COMPLETED if result else TaskStatus.PENDING

            return {
                "task_id": task_id,
                "status": status,
                "result": result
            }

        except Exception as e:
            logger.error(f"Failed to get task status: {str(e)}")
            return {
                "task_id": task_id,
                "status": TaskStatus.FAILED,
                "error": str(e)
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
                    for _ in range(PROCESSING_CONFIG.get("min_instances", 3))
                ],
                "market": [
                    await self.agent_factory.create_agent("market")
                    for _ in range(PROCESSING_CONFIG.get("min_instances", 3))
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
            
            # Process task
            result = await agent.process_task(task)
            
            # Store result
            await self._store_task_result(task.task_id, result)
            
            # Update metrics
            await self._update_metrics("tasks_completed")
            
            return result

        except Exception as e:
            logger.error(f"Task processing failed: {str(e)}")
            await self._update_metrics("tasks_failed")
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

    async def _update_task_status(self, task_id: str, status: str):
        """Update task status in Redis"""
        if self.redis_client:
            key = f"task:status:{task_id}"
            await self.redis_client.set(key, status, ex=3600)  # 1 hour TTL

    async def _store_task_result(self, task_id: str, result: AgentResult):
        """Store task result in Redis"""
        if self.redis_client:
            key = f"task:result:{task_id}"
            await self.redis_client.set(
                key,
                result.json(),
                ex=3600  # 1 hour TTL
            )

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