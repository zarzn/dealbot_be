from typing import Optional
from core.models.deal import Deal, AIAnalysis
from core.utils.llm import get_llm_instance

class AIService:
    """Service for AI-powered analysis and predictions"""

    def __init__(self):
        self.llm = get_llm_instance()

    async def analyze_deal(self, deal: Deal) -> Optional[AIAnalysis]:
        """
        Analyze a deal using AI to provide insights and recommendations
        """
        try:
            # Get price history and market data
            price_history = [point.price for point in deal.price_points]
            if not price_history:
                return None

            # Calculate basic metrics
            current_price = deal.price
            avg_price = sum(price_history) / len(price_history)
            price_trend = "rising" if current_price > avg_price else "falling"

            # Use LLM to analyze the deal
            analysis_prompt = f"""
            Analyze this deal:
            Title: {deal.title}
            Current Price: {current_price}
            Average Price: {avg_price}
            Price Trend: {price_trend}
            Description: {deal.description}

            Provide:
            1. Deal score (0-1)
            2. Confidence in analysis (0-1)
            3. Price prediction
            4. 3 key recommendations
            """

            response = await self.llm.analyze(analysis_prompt)

            # Parse LLM response and create AIAnalysis
            return AIAnalysis(
                score=response.get("score", 0.5),
                confidence=response.get("confidence", 0.5),
                price_trend=price_trend,
                price_prediction=response.get("price_prediction", current_price),
                recommendations=response.get("recommendations", [
                    "Consider the price trend before purchasing",
                    "Compare with similar products",
                    "Monitor for better deals"
                ]),
                meta_data={
                    "analysis_version": "1.0",
                    "model_used": "deepseek-coder",
                    "analysis_timestamp": str(datetime.utcnow())
                }
            )

        except Exception as e:
            logger.error(f"Failed to analyze deal: {str(e)}")
            return None 