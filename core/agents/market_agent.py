from typing import List, Dict
from core.models.deal import Deal
from core.models.enums import MarketCategory
from core.services.market_search import MarketSearchService
from core.integrations.scraper_api import ScraperAPIService
from core.agents.base.base_agent import BaseAgent
from core.agents.config.agent_config import AgentConfig
from core.repositories.market import MarketRepository
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from core.agents.utils.llm_manager import LLMManager
import json

class MarketAgent:
    def __init__(self, llm_manager: LLMManager):
        self.llm_manager = llm_manager

    async def analyze_market_trends(self, deals: List[Dict]) -> Dict:
        """Analyze market trends based on deal history.

        Args:
            deals: List of deal dictionaries with price history

        Returns:
            Dict containing trend analysis results
        """
        prompt = f"""Analyze the market trends for the following deals:
        {json.dumps(deals, indent=2)}
        
        Provide a detailed analysis of:
        - Price trends (increasing, decreasing, fluctuating)
        - Average price
        - Price range (min/max)
        - Confidence in the analysis
        """
        
        response = await self.llm_manager.generate_response(prompt)
        return response 

    async def generate_deal_recommendation(self, deal: Deal, user_preferences: Dict) -> Dict:
        """Generate deal recommendation based on user preferences.

        Args:
            deal: Deal object to analyze
            user_preferences: User preferences dictionary

        Returns:
            Dict containing recommendation details
        """
        score = 0.0
        reasons = []

        # Check brand preference
        if deal.deal_metadata.get("brand") in user_preferences.get("preferred_brands", []):
            score += 0.3
            reasons.append(f"Matches preferred brand: {deal.deal_metadata['brand']}")

        # Check price against max price
        if user_preferences.get("max_price"):
            price_ratio = deal.price / user_preferences["max_price"]
            if price_ratio <= 1:
                score += 0.3 * (1 - price_ratio)
                reasons.append(f"Price within budget: ${deal.price} vs ${user_preferences['max_price']}")

        # Check specifications
        required_specs = user_preferences.get("required_specs", {})
        matching_specs = 0
        total_specs = len(required_specs)
        
        if total_specs > 0:
            for spec, value in required_specs.items():
                if deal.deal_metadata.get("specs", {}).get(spec) == value:
                    matching_specs += 1
            
            if matching_specs > 0:
                spec_score = 0.3 * (matching_specs / total_specs)
                score += spec_score
                reasons.append(f"Matches {matching_specs}/{total_specs} required specifications")

        # Check for significant discount
        if deal.original_price:
            discount_ratio = (deal.original_price - deal.price) / deal.original_price
            if discount_ratio >= 0.3:
                score += 0.2
                reasons.append(f"Significant discount: {int(discount_ratio * 100)}% off")
            elif discount_ratio >= 0.1:
                score += 0.1
                reasons.append(f"Moderate discount: {int(discount_ratio * 100)}% off")

        # Check customer ratings if available
        if deal.deal_metadata.get("rating", 0) >= 4.5:
            score += 0.2
            reasons.append("High customer rating")

        return {
            "score": min(score, 1.0),
            "reasons": reasons
        } 