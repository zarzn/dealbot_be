"""Tools for goal analysis agent.

This module provides tools for analyzing user goals, validating constraints,
and generating search parameters.
"""

from typing import Dict, Any, List, Optional
from langchain_community.tools import BaseTool
from pydantic import BaseModel, Field

class GoalInput(BaseModel):
    """Input model for goal analysis"""
    description: str = Field(..., description="User's goal description")
    max_price: Optional[float] = Field(None, description="Maximum price constraint")
    min_price: Optional[float] = Field(None, description="Minimum price constraint")
    brands: Optional[list[str]] = Field(None, description="Preferred brands")
    conditions: Optional[list[str]] = Field(None, description="Acceptable conditions")
    keywords: Optional[list[str]] = Field(None, description="Search keywords")

class AnalyzeGoalTool(BaseTool):
    """Tool for analyzing user goals"""
    name = "analyze_goal"
    description = "Analyze user's goal description and extract structured constraints"
    args_schema = GoalInput

    def _run(self, description: str, **kwargs) -> Dict[str, Any]:
        """Run goal analysis"""
        # For MVP, we'll use simple rule-based analysis
        # This would be replaced with more sophisticated analysis in production
        analysis = {
            "structured_goal": {
                "max_price": kwargs.get("max_price"),
                "min_price": kwargs.get("min_price"),
                "brands": kwargs.get("brands", []),
                "conditions": kwargs.get("conditions", []),
                "keywords": kwargs.get("keywords", [])
            },
            "confidence_score": 0.8,  # Placeholder
            "suggested_improvements": []
        }
        
        # Add suggestions based on missing information
        if not analysis["structured_goal"]["max_price"]:
            analysis["suggested_improvements"].append(
                "Consider adding a maximum price"
            )
        if not analysis["structured_goal"]["brands"]:
            analysis["suggested_improvements"].append(
                "Add preferred brands for better results"
            )
            
        return analysis

    async def _arun(self, description: str, **kwargs) -> Dict[str, Any]:
        """Async run goal analysis"""
        return self._run(description, **kwargs)

class ValidateConstraintsTool(BaseTool):
    """Tool for validating goal constraints"""
    name = "validate_constraints"
    description = "Validate goal constraints against system rules"

    def _run(self, constraints: Dict[str, Any]) -> Dict[str, Any]:
        """Run constraint validation"""
        validation = {
            "is_valid": True,
            "issues": [],
            "suggestions": []
        }
        
        # Validate price constraints
        if constraints.get("max_price") and constraints.get("min_price"):
            if constraints["max_price"] < constraints["min_price"]:
                validation["is_valid"] = False
                validation["issues"].append(
                    "Maximum price cannot be less than minimum price"
                )
                
        # Validate brands
        brands = constraints.get("brands", [])
        if len(brands) > 10:
            validation["suggestions"].append(
                "Consider reducing number of brands for better results"
            )
            
        # Validate conditions
        valid_conditions = {"new", "used", "refurbished"}
        conditions = set(constraints.get("conditions", []))
        invalid_conditions = conditions - valid_conditions
        if invalid_conditions:
            validation["issues"].append(
                f"Invalid conditions: {', '.join(invalid_conditions)}"
            )
            
        return validation

    async def _arun(self, constraints: Dict[str, Any]) -> Dict[str, Any]:
        """Async run constraint validation"""
        return self._run(constraints)

class GenerateSearchParamsTool(BaseTool):
    """Tool for generating search parameters"""
    name = "generate_search_params"
    description = "Generate optimized search parameters from goal constraints"

    def _run(self, constraints: Dict[str, Any]) -> Dict[str, Any]:
        """Run search parameter generation"""
        # Convert constraints to search parameters
        search_params = {
            "price_range": {
                "min": constraints.get("min_price"),
                "max": constraints.get("max_price")
            },
            "brands": constraints.get("brands", []),
            "conditions": constraints.get("conditions", []),
            "keywords": constraints.get("keywords", []),
            "sort_by": "price_asc" if constraints.get("max_price") else "best_match",
            "filters": self._generate_filters(constraints),
            "search_strategy": self._determine_search_strategy(constraints)
        }
        
        return {
            "parameters": search_params,
            "estimated_results": self._estimate_results(search_params),
            "refresh_interval": self._calculate_refresh_interval(search_params)
        }

    async def _arun(self, constraints: Dict[str, Any]) -> Dict[str, Any]:
        """Async run search parameter generation"""
        return self._run(constraints)

    def _generate_filters(self, constraints: Dict[str, Any]) -> Dict[str, Any]:
        """Generate additional filters based on constraints"""
        filters = {}
        
        # Add price filters with buffer
        if constraints.get("max_price"):
            filters["max_price"] = constraints["max_price"] * 1.1  # 10% buffer
            
        if constraints.get("min_price"):
            filters["min_price"] = constraints["min_price"] * 0.9  # 10% buffer
            
        # Add brand filters
        if constraints.get("brands"):
            filters["brand_match"] = "exact"  # or "fuzzy" for broader matches
            
        # Add condition filters
        if constraints.get("conditions"):
            filters["condition_match"] = "any"  # or "all" for strict matching
            
        return filters

    def _determine_search_strategy(self, constraints: Dict[str, Any]) -> str:
        """Determine best search strategy based on constraints"""
        if len(constraints.get("keywords", [])) > 3:
            return "broad_match"
        if constraints.get("brands"):
            return "brand_focused"
        if constraints.get("max_price"):
            return "price_focused"
        return "general"

    def _estimate_results(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Estimate search results based on parameters"""
        # For MVP, use simple estimation
        return {
            "estimated_count": 100,  # Placeholder
            "confidence": 0.7,
            "refresh_needed": True
        }

    def _calculate_refresh_interval(self, params: Dict[str, Any]) -> int:
        """Calculate optimal refresh interval"""
        # For MVP, use simple rules
        if params["search_strategy"] == "price_focused":
            return 300  # 5 minutes
        if params["search_strategy"] == "brand_focused":
            return 600  # 10 minutes
        return 900  # 15 minutes 