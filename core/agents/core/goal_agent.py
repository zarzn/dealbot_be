"""Goal Analysis & Discovery Agent.

This agent is responsible for interpreting user goals, managing deal discovery,
and validating deals against user goals.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import json
from pydantic import BaseModel

from core.agents.base.base_agent import BaseAgent, AgentRequest, AgentResponse
from core.agents.utils.llm_manager import LLMManager, LLMRequest
from core.agents.config.agent_config import PriorityLevel, LLMProvider
from core.utils.logger import get_logger

logger = get_logger(__name__)

class GoalConstraints(BaseModel):
    """Model for goal constraints"""
    max_price: Optional[float]
    min_price: Optional[float]
    brands: Optional[List[str]]
    conditions: Optional[List[str]]
    keywords: Optional[List[str]]

class GoalAgent(BaseAgent):
    """Agent for goal analysis and deal discovery"""

    def __init__(self):
        super().__init__("goal_agent")
        self.llm_manager = None

    async def _setup_agent(self):
        """Setup goal agent"""
        self.llm_manager = LLMManager()
        await self.llm_manager.initialize()

    async def _process_request(self, request: AgentRequest) -> Dict[str, Any]:
        """Process goal-related request"""
        action = request.payload.get("action")
        
        if action == "analyze_goal":
            return await self._analyze_goal(request)
        elif action == "validate_deal":
            return await self._validate_deal(request)
        elif action == "discover_deals":
            return await self._discover_deals(request)
        else:
            raise ValueError(f"Unknown action: {action}")

    async def _analyze_goal(self, request: AgentRequest) -> Dict[str, Any]:
        """Analyze and structure user goal"""
        goal_description = request.payload.get("goal_description")
        if not goal_description:
            raise ValueError("Goal description is required")

        # Generate prompt for goal analysis
        prompt = self._generate_goal_analysis_prompt(goal_description)
        
        # Get LLM response
        llm_response = await self.llm_manager.generate(
            LLMRequest(
                prompt=prompt,
                temperature=0.3  # Lower temperature for more focused response
            )
        )

        # Parse and validate constraints
        try:
            constraints = self._parse_goal_constraints(llm_response.text)
            return {
                "structured_goal": constraints.dict(),
                "confidence_score": self._calculate_confidence(constraints),
                "suggested_improvements": self._suggest_improvements(constraints)
            }
        except Exception as e:
            logger.error(f"Error parsing goal constraints: {str(e)}")
            raise ValueError("Failed to parse goal constraints")

    async def _validate_deal(self, request: AgentRequest) -> Dict[str, Any]:
        """Validate deal against goal constraints"""
        deal = request.payload.get("deal")
        constraints = request.payload.get("constraints")
        
        if not deal or not constraints:
            raise ValueError("Deal and constraints are required")

        # Convert constraints to model
        goal_constraints = GoalConstraints(**constraints)
        
        # Perform validation
        validation_result = self._validate_deal_against_constraints(
            deal, goal_constraints
        )
        
        return {
            "is_valid": validation_result["is_valid"],
            "match_score": validation_result["match_score"],
            "reasons": validation_result["reasons"]
        }

    async def _discover_deals(self, request: AgentRequest) -> Dict[str, Any]:
        """Discover deals based on goal constraints"""
        constraints = request.payload.get("constraints")
        if not constraints:
            raise ValueError("Constraints are required")

        # Convert constraints to model
        goal_constraints = GoalConstraints(**constraints)
        
        # Generate search parameters
        search_params = self._generate_search_parameters(goal_constraints)
        
        # This would typically call market search service
        # For MVP, we'll return the search parameters
        return {
            "search_parameters": search_params,
            "priority_score": self._calculate_priority(goal_constraints)
        }

    def _generate_goal_analysis_prompt(self, goal_description: str) -> str:
        """Generate prompt for goal analysis"""
        return f"""Analyze the following goal description and extract structured constraints:

Goal: {goal_description}

Please provide a JSON response with the following structure:
{{
    "max_price": float or null,
    "min_price": float or null,
    "brands": list of strings or null,
    "conditions": list of strings or null,
    "keywords": list of strings or null
}}

Only include fields if they are clearly specified or can be reasonably inferred from the goal description."""

    def _parse_goal_constraints(self, llm_response: str) -> GoalConstraints:
        """Parse LLM response into goal constraints"""
        try:
            # Extract JSON from response
            response_json = json.loads(llm_response)
            return GoalConstraints(**response_json)
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON in LLM response")
        except Exception as e:
            raise ValueError(f"Error parsing constraints: {str(e)}")

    def _validate_deal_against_constraints(
        self,
        deal: Dict[str, Any],
        constraints: GoalConstraints
    ) -> Dict[str, Any]:
        """Validate deal against constraints"""
        reasons = []
        match_score = 0.0
        
        # Price validation
        if constraints.max_price and deal["price"] > constraints.max_price:
            reasons.append("Price exceeds maximum")
        elif constraints.min_price and deal["price"] < constraints.min_price:
            reasons.append("Price below minimum")
        else:
            match_score += 0.4

        # Brand validation
        if constraints.brands:
            if deal["brand"] in constraints.brands:
                match_score += 0.2
            else:
                reasons.append("Brand not in preferred list")

        # Condition validation
        if constraints.conditions:
            if deal["condition"] in constraints.conditions:
                match_score += 0.2
            else:
                reasons.append("Condition not acceptable")

        # Keyword validation
        if constraints.keywords:
            title_words = set(deal["title"].lower().split())
            matching_keywords = [
                k for k in constraints.keywords 
                if k.lower() in title_words
            ]
            if matching_keywords:
                match_score += 0.2
            else:
                reasons.append("No matching keywords found")

        return {
            "is_valid": len(reasons) == 0,
            "match_score": match_score,
            "reasons": reasons
        }

    def _generate_search_parameters(
        self,
        constraints: GoalConstraints
    ) -> Dict[str, Any]:
        """Generate search parameters from constraints"""
        return {
            "price_range": {
                "min": constraints.min_price,
                "max": constraints.max_price
            },
            "brands": constraints.brands,
            "conditions": constraints.conditions,
            "keywords": constraints.keywords,
            "sort_by": "price_asc" if constraints.max_price else "best_match"
        }

    def _calculate_confidence(self, constraints: GoalConstraints) -> float:
        """Calculate confidence score for parsed constraints"""
        score = 0.0
        total_fields = 0
        
        if constraints.max_price is not None:
            score += 1.0
            total_fields += 1
        if constraints.min_price is not None:
            score += 1.0
            total_fields += 1
        if constraints.brands:
            score += 1.0
            total_fields += 1
        if constraints.conditions:
            score += 1.0
            total_fields += 1
        if constraints.keywords:
            score += 1.0
            total_fields += 1
            
        return score / max(total_fields, 1)

    def _suggest_improvements(self, constraints: GoalConstraints) -> List[str]:
        """Suggest improvements for goal constraints"""
        suggestions = []
        
        if not constraints.max_price:
            suggestions.append("Consider adding a maximum price")
        if not constraints.brands and not constraints.keywords:
            suggestions.append("Add brand preferences or specific keywords")
        if not constraints.conditions:
            suggestions.append("Specify acceptable item conditions")
            
        return suggestions

    def _calculate_priority(self, constraints: GoalConstraints) -> float:
        """Calculate priority score for deal discovery"""
        score = 0.0
        
        # Price range specificity
        if constraints.max_price and constraints.min_price:
            score += 0.4
        elif constraints.max_price or constraints.min_price:
            score += 0.2
            
        # Brand specificity
        if constraints.brands:
            score += 0.2
            
        # Condition specificity
        if constraints.conditions:
            score += 0.2
            
        # Keyword specificity
        if constraints.keywords:
            score += 0.2
            
        return score 