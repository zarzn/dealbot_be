"""CrewAI integration layer.

This module provides integration between our custom agent system and CrewAI,
allowing seamless use of our tools and agents within the CrewAI framework.
"""

from typing import Dict, Any, List, Optional
from crewai import Agent, Task, Crew, Process
from langchain.tools import BaseTool
from pydantic import BaseModel

# Import our custom tools
from ..tools.goal_tools import (
    AnalyzeGoalTool, ValidateConstraintsTool, GenerateSearchParamsTool
)
from ..tools.market_tools import (
    MarketSearchTool, PriceAnalysisTool, DealValidationTool
)
from ..tools.conversation_tools import (
    QueryHandlerTool, ResponseGeneratorTool, ContextManagerTool
)
from ..tools.personalization_tools import (
    PreferenceLearningTool, RecommendationOptimizationTool,
    NotificationPriorityTool, FeedbackProcessingTool
)

class CrewAIAdapter:
    """Adapter for integrating our tools with CrewAI"""
    
    def __init__(self):
        """Initialize the adapter with all available tools"""
        self.tools = {
            # Goal Analysis Tools
            "analyze_goal": AnalyzeGoalTool(),
            "validate_constraints": ValidateConstraintsTool(),
            "generate_search_params": GenerateSearchParamsTool(),
            
            # Market Intelligence Tools
            "market_search": MarketSearchTool(),
            "price_analysis": PriceAnalysisTool(),
            "deal_validation": DealValidationTool(),
            
            # Conversation Tools
            "query_handler": QueryHandlerTool(),
            "response_generator": ResponseGeneratorTool(),
            "context_manager": ContextManagerTool(),
            
            # Personalization Tools
            "preference_learning": PreferenceLearningTool(),
            "recommendation_optimization": RecommendationOptimizationTool(),
            "notification_priority": NotificationPriorityTool(),
            "feedback_processing": FeedbackProcessingTool()
        }
        
    def create_goal_analysis_agent(self) -> Agent:
        """Create a CrewAI agent for goal analysis"""
        return Agent(
            role='Goal Analysis Expert',
            goal='Analyze and validate user goals for deal searching',
            backstory="""You are an expert at understanding user goals and 
            translating them into actionable search parameters.""",
            tools=[
                self.tools["analyze_goal"],
                self.tools["validate_constraints"],
                self.tools["generate_search_params"]
            ]
        )
        
    def create_market_intelligence_agent(self) -> Agent:
        """Create a CrewAI agent for market intelligence"""
        return Agent(
            role='Market Intelligence Expert',
            goal='Find and validate the best deals across marketplaces',
            backstory="""You are a market research expert who knows how to 
            find the best deals and validate their authenticity.""",
            tools=[
                self.tools["market_search"],
                self.tools["price_analysis"],
                self.tools["deal_validation"]
            ]
        )
        
    def create_conversation_agent(self) -> Agent:
        """Create a CrewAI agent for conversation handling"""
        return Agent(
            role='Conversation Expert',
            goal='Handle user interactions naturally and effectively',
            backstory="""You are an expert at understanding user queries and 
            providing helpful, contextual responses.""",
            tools=[
                self.tools["query_handler"],
                self.tools["response_generator"],
                self.tools["context_manager"]
            ]
        )
        
    def create_personalization_agent(self) -> Agent:
        """Create a CrewAI agent for personalization"""
        return Agent(
            role='Personalization Expert',
            goal='Optimize user experience through personalization',
            backstory="""You are an expert at understanding user preferences 
            and optimizing recommendations and notifications.""",
            tools=[
                self.tools["preference_learning"],
                self.tools["recommendation_optimization"],
                self.tools["notification_priority"],
                self.tools["feedback_processing"]
            ]
        )

class DealSearchCrew:
    """CrewAI crew for deal searching and analysis"""
    
    def __init__(self):
        """Initialize the deal search crew"""
        self.adapter = CrewAIAdapter()
        self.crew = self._create_crew()
        
    def _create_crew(self) -> Crew:
        """Create the CrewAI crew with all necessary agents"""
        return Crew(
            agents=[
                self.adapter.create_goal_analysis_agent(),
                self.adapter.create_market_intelligence_agent(),
                self.adapter.create_conversation_agent(),
                self.adapter.create_personalization_agent()
            ],
            process=Process.sequential  # or Process.hierarchical
        )
        
    def search_deals(self, user_query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a deal search using the crew"""
        # Create tasks for the crew
        tasks = [
            Task(
                description="""Analyze the user's query and extract structured goal
                information.""",
                agent=self.adapter.create_goal_analysis_agent()
            ),
            Task(
                description="""Search across marketplaces and validate potential
                deals.""",
                agent=self.adapter.create_market_intelligence_agent()
            ),
            Task(
                description="""Generate a personalized response based on the user's
                preferences.""",
                agent=self.adapter.create_personalization_agent()
            ),
            Task(
                description="""Format and deliver the response to the user.""",
                agent=self.adapter.create_conversation_agent()
            )
        ]
        
        # Execute the tasks
        result = self.crew.kickoff(
            tasks=tasks,
            context={
                "user_query": user_query,
                "user_context": context
            }
        )
        
        return result

class DealMonitoringCrew:
    """CrewAI crew for continuous deal monitoring"""
    
    def __init__(self):
        """Initialize the deal monitoring crew"""
        self.adapter = CrewAIAdapter()
        self.crew = self._create_crew()
        
    def _create_crew(self) -> Crew:
        """Create the CrewAI crew for monitoring"""
        return Crew(
            agents=[
                self.adapter.create_market_intelligence_agent(),
                self.adapter.create_personalization_agent()
            ],
            process=Process.sequential
        )
        
    def monitor_deals(self, goals: List[Dict[str, Any]], 
                     user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute continuous deal monitoring"""
        tasks = [
            Task(
                description="""Monitor marketplaces for deals matching user
                goals.""",
                agent=self.adapter.create_market_intelligence_agent()
            ),
            Task(
                description="""Evaluate deals and determine notification
                priority.""",
                agent=self.adapter.create_personalization_agent()
            )
        ]
        
        result = self.crew.kickoff(
            tasks=tasks,
            context={
                "goals": goals,
                "user_context": user_context
            }
        )
        
        return result

def create_crew_for_task(task_type: str) -> Crew:
    """Factory function to create appropriate crew for a task"""
    if task_type == "deal_search":
        return DealSearchCrew()
    elif task_type == "deal_monitoring":
        return DealMonitoringCrew()
    else:
        raise ValueError(f"Unknown task type: {task_type}") 