"""CrewAI adapter for integrating CrewAI with our agent system.

This module provides a bridge between CrewAI and our custom agent system,
allowing us to use CrewAI agents while maintaining our performance optimizations.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from crewai import Agent as CrewAgent, Task as CrewTask, Crew, Process
from langchain.tools import BaseTool

from core.agents.base.agent_interface import (
    IAgent,
    AgentTask,
    AgentResult,
    AgentContext,
    AgentException
)
from core.agents.config.agent_config import (
    PROCESSING_CONFIG,
    LLM_CONFIGS,
    LLMProvider
)
from core.utils.logger import get_logger
from core.utils.redis import get_redis_client

logger = get_logger(__name__)

class CrewAIAdapter(IAgent):
    """Adapter for CrewAI integration"""

    def __init__(self, agent_type: str, config: Optional[Dict[str, Any]] = None):
        self.agent_type = agent_type
        self.config = config or {}
        self.crew_agent = None
        self.tools: List[BaseTool] = []
        self.redis_client = None

    async def initialize(self) -> None:
        """Initialize CrewAI agent"""
        try:
            self.redis_client = await get_redis_client()
            
            # Initialize tools
            self.tools = self._initialize_tools()
            
            # Create CrewAI agent
            self.crew_agent = CrewAgent(
                role=self._get_agent_role(),
                goal=self._get_agent_goal(),
                backstory=self._get_agent_backstory(),
                tools=self.tools,
                llm=self._get_llm_config()
            )
            
        except Exception as e:
            logger.error(f"Failed to initialize CrewAI agent: {str(e)}")
            raise AgentException(f"CrewAI initialization failed: {str(e)}")

    async def process_task(self, task: AgentTask) -> AgentResult:
        """Process task using CrewAI"""
        start_time = datetime.utcnow()
        
        try:
            # Check cache first
            cache_key = f"crew:task:{task.task_id}"
            cached_result = await self._get_cached_result(cache_key)
            if cached_result:
                return AgentResult(
                    task_id=task.task_id,
                    status="success",
                    result=cached_result,
                    processing_time=0.0,
                    metadata={"cache_hit": True}
                )

            # Convert to CrewAI task
            crew_task = self._create_crew_task(task)
            
            # Create single-agent crew for MVP
            crew = Crew(
                agents=[self.crew_agent],
                tasks=[crew_task]
            )
            
            # Execute task
            result = await self._execute_crew_task(crew)
            
            # Cache result
            await self._cache_result(cache_key, result)
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            return AgentResult(
                task_id=task.task_id,
                status="success",
                result=result,
                processing_time=processing_time,
                metadata={
                    "cache_hit": False,
                    "agent_type": "crew_ai"
                }
            )
            
        except Exception as e:
            logger.error(f"CrewAI task processing failed: {str(e)}")
            return AgentResult(
                task_id=task.task_id,
                status="error",
                error=str(e),
                processing_time=(datetime.utcnow() - start_time).total_seconds(),
                metadata={"agent_type": "crew_ai"}
            )

    async def can_handle_task(self, task: AgentTask) -> bool:
        """Check if CrewAI agent can handle task"""
        # For MVP, we'll handle tasks based on agent type
        return task.task_type == self.agent_type

    async def get_capabilities(self) -> list[str]:
        """Get CrewAI agent capabilities"""
        return [
            f"{self.agent_type}.{tool.name}"
            for tool in self.tools
        ]

    async def health_check(self) -> bool:
        """Check CrewAI agent health"""
        return self.crew_agent is not None

    def _initialize_tools(self) -> List[BaseTool]:
        """Initialize tools based on agent type"""
        if self.agent_type == "goal":
            return self._get_goal_tools()
        elif self.agent_type == "market":
            return self._get_market_tools()
        return []

    def _get_goal_tools(self) -> List[BaseTool]:
        """Get tools for goal analysis agent"""
        from core.tools.goal_tools import (
            AnalyzeGoalTool,
            ValidateConstraintsTool,
            GenerateSearchParamsTool
        )
        return [
            AnalyzeGoalTool(),
            ValidateConstraintsTool(),
            GenerateSearchParamsTool()
        ]

    def _get_market_tools(self) -> List[BaseTool]:
        """Get tools for market intelligence agent"""
        from core.tools.market_tools import (
            AnalyzePriceTool,
            ValidateSourceTool,
            OptimizeSearchTool
        )
        return [
            AnalyzePriceTool(),
            ValidateSourceTool(),
            OptimizeSearchTool()
        ]

    def _get_agent_role(self) -> str:
        """Get agent role based on type"""
        roles = {
            "goal": "Goal Analysis Expert",
            "market": "Market Intelligence Analyst"
        }
        return roles.get(self.agent_type, "General Assistant")

    def _get_agent_goal(self) -> str:
        """Get agent goal based on type"""
        goals = {
            "goal": "Analyze and optimize user goals for deal discovery",
            "market": "Analyze market conditions and validate deals"
        }
        return goals.get(self.agent_type, "Assist with general tasks")

    def _get_agent_backstory(self) -> str:
        """Get agent backstory based on type"""
        backstories = {
            "goal": "Expert in understanding user goals and optimizing search strategies",
            "market": "Expert in market analysis and deal validation"
        }
        return backstories.get(self.agent_type, "General purpose assistant")

    def _get_llm_config(self) -> Dict[str, Any]:
        """Get LLM configuration"""
        # Use Gemini for development
        if LLM_CONFIGS[LLMProvider.GEMINI].is_development:
            return {
                "model": "gemini-2.0-flash",
                "api_key": LLM_CONFIGS[LLMProvider.GEMINI].api_key,
                "temperature": 0.7
            }
        # Use DeepSeek for production
        return {
            "model": LLM_CONFIGS[LLMProvider.DEEPSEEK].model,
            "api_key": LLM_CONFIGS[LLMProvider.DEEPSEEK].api_key,
            "temperature": 0.7
        }

    def _create_crew_task(self, task: AgentTask) -> CrewTask:
        """Convert our task to CrewAI task"""
        return CrewTask(
            description=self._generate_task_description(task),
            agent=self.crew_agent
        )

    def _generate_task_description(self, task: AgentTask) -> str:
        """Generate detailed task description for CrewAI"""
        return f"""
        Task Type: {task.task_type}
        Priority: {task.priority}
        
        Payload:
        {task.payload}
        
        Required Capabilities:
        {', '.join(task.required_capabilities) if task.required_capabilities else 'None'}
        
        Please analyze and process this task according to your expertise.
        """

    async def _execute_crew_task(self, crew: Crew) -> Dict[str, Any]:
        """Execute CrewAI task with our optimizations"""
        try:
            # Execute with timeout based on priority
            timeout = PROCESSING_CONFIG["timeout"]
            async with asyncio.timeout(timeout):
                result = await crew.kickoff()
                return self._parse_crew_result(result)
        except asyncio.TimeoutError:
            raise AgentException("Task execution timed out")

    def _parse_crew_result(self, result: Any) -> Dict[str, Any]:
        """Parse CrewAI result into our format"""
        if isinstance(result, dict):
            return result
        return {"output": str(result)}

    async def _get_cached_result(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached result"""
        if self.redis_client:
            return await self.redis_client.get(key)
        return None

    async def _cache_result(self, key: str, result: Dict[str, Any]):
        """Cache task result"""
        if self.redis_client:
            await self.redis_client.set(
                key,
                result,
                ex=3600  # 1 hour TTL
            ) 