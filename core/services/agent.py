from crewai import Agent, Task, Crew
from typing import List, Dict, Any
from pydantic import BaseModel
from backend.core.services.base import BaseService
from backend.core.models import Goal, Deal
from backend.core.utils.redis import RedisClient
from backend.core.exceptions import AgentError

class AgentService(BaseService):
    def __init__(self):
        self.redis = RedisClient()
        self.crew = Crew()

    async def create_goal_analysis_agent(self) -> Agent:
        """Create goal analysis agent"""
        return Agent(
            role='Goal Analyst',
            goal='Analyze and interpret user goals to extract search parameters',
            backstory='Expert in understanding user needs and translating them into actionable search criteria',
            verbose=True,
            memory=True
        )

    async def create_deal_search_agent(self) -> Agent:
        """Create deal search agent"""
        return Agent(
            role='Deal Finder',
            goal='Search for deals matching user goals across multiple platforms',
            backstory='Skilled in navigating e-commerce platforms and finding the best deals',
            verbose=True,
            memory=True
        )

    async def create_price_analysis_agent(self) -> Agent:
        """Create price analysis agent"""
        return Agent(
            role='Price Analyst',
            goal='Analyze price history and trends to evaluate deal quality',
            backstory='Expert in price analysis and trend detection with deep knowledge of market dynamics',
            verbose=True,
            memory=True
        )

    async def create_notification_agent(self) -> Agent:
        """Create notification agent"""
        return Agent(
            role='Notifier',
            goal='Generate and send notifications about relevant deals to users',
            backstory='Specialist in crafting clear and actionable notifications for users',
            verbose=True,
            memory=True
        )

    async def setup_crew(self) -> None:
        """Setup crew with all agents"""
        goal_agent = await self.create_goal_analysis_agent()
        deal_agent = await self.create_deal_search_agent()
        price_agent = await self.create_price_analysis_agent()
        notify_agent = await self.create_notification_agent()
        
        self.crew.agents = [goal_agent, deal_agent, price_agent, notify_agent]

    async def process_goal(self, goal: Goal) -> List[Deal]:
        """Process a user goal through the agent system"""
        try:
            await self.setup_crew()
            
            # Create tasks for each agent
            goal_task = Task(
                description=f"Analyze goal: {goal.title}",
                agent=self.crew.agents[0]
            )
            
            search_task = Task(
                description="Find deals matching the analyzed goal",
                agent=self.crew.agents[1],
                context=[goal_task]
            )
            
            analysis_task = Task(
                description="Analyze found deals for quality and relevance",
                agent=self.crew.agents[2],
                context=[search_task]
            )
            
            notify_task = Task(
                description="Generate notifications for relevant deals",
                agent=self.crew.agents[3],
                context=[analysis_task]
            )
            
            # Execute the crew
            result = await self.crew.kickoff()
            
            # Cache results in Redis
            await self.redis.set(f"goal:{goal.id}:results", result)
            
            return result
            
        except Exception as e:
            raise AgentError(f"Error processing goal: {str(e)}")
