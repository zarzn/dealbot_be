import sys
import logging
import json
from datetime import datetime
from uuid import uuid4
from decimal import Decimal

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Mock Deal class to avoid SQLAlchemy dependencies
class MockDeal:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

# Mock Deal Service with only _convert_to_response method
class MockDealService:
    def _convert_to_response(self, deal, user_id=None, include_ai_analysis=True, analysis=None):
        """Simplified version of the real _convert_to_response method for testing"""
        # Get market name (safely)
        market_name = "Unknown Market"
        if hasattr(deal, 'market_id') and deal.market_id:
            market_name = f"Market {deal.market_id[:8]}"
            
        # Check if deal is tracked by user
        is_tracked = False
        
        # Safely handle original price
        original_price = None
        if hasattr(deal, 'original_price') and deal.original_price:
            original_price = float(deal.original_price)
            
        # Safely get category
        category = "unknown"
        if hasattr(deal, 'category'):
            category = str(deal.category)
        
        # Handle AI analysis
        ai_analysis = None
        if include_ai_analysis:
            # Use provided analysis
            if analysis:
                ai_analysis = analysis
            else:
                # Basic score calculation if no analysis available
                discount_percentage = 0
                if original_price and deal.price:
                    discount_percentage = ((original_price - float(deal.price)) / original_price) * 100
                    basic_score = min(discount_percentage / 100 * 0.8 + 0.2, 1.0)
                else:
                    basic_score = 0.5
                    
                # Create fallback analysis
                ai_analysis = {
                    "deal_id": str(deal.id),
                    "score": round(basic_score * 100) / 100,
                    "confidence": 0.5,
                    "price_analysis": {
                        "discount_percentage": discount_percentage,
                        "is_good_deal": False,
                        "price_trend": "unknown",
                        "trend_details": {},
                        "original_price": original_price,
                        "current_price": float(deal.price)
                    },
                    "market_analysis": {
                        "competition": "Average",
                        "availability": "Unavailable",
                        "market_info": {
                            "name": deal.source.capitalize() if deal.source else "Unknown",
                            "type": deal.source.lower() if deal.source else "unknown"
                        },
                        "price_position": "Mid-range",
                        "popularity": "Unknown"
                    },
                    "recommendations": ["Limited discount on this item. Consider waiting for a better deal.",
                                     "Compare features with similar models in this price range."],
                    "analysis_date": datetime.utcnow().isoformat(),
                    "expiration_analysis": "Deal expires on " + deal.expires_at.isoformat() if deal.expires_at else "No expiration date provided"
                }
        
        # Safely handle seller_info and availability
        seller_info = {"name": "Unknown", "rating": 0, "reviews": 0}
        if hasattr(deal, 'seller_info') and deal.seller_info:
            seller_info = deal.seller_info
            
        availability = {}
        if hasattr(deal, 'availability') and deal.availability:
            availability = deal.availability
            
        # Get deal_metadata safely
        deal_metadata = {}
        if hasattr(deal, 'deal_metadata') and deal.deal_metadata:
            deal_metadata = deal.deal_metadata
            
        # Build the response
        response = {
            "id": str(deal.id),
            "title": deal.title,
            "description": deal.description or "",
            "url": deal.url,
            "price": str(deal.price),
            "original_price": str(original_price) if original_price else None,
            "currency": deal.currency,
            "source": deal.source,
            "image_url": deal.image_url,
            "category": category,
            "deal_metadata": deal_metadata,
            "price_metadata": deal.price_metadata if hasattr(deal, 'price_metadata') else {},
            "seller_info": seller_info,
            "availability": availability,
            "status": deal.status,
            "found_at": deal.found_at,
            "expires_at": deal.expires_at,
            "goal_id": str(deal.goal_id) if hasattr(deal, 'goal_id') and deal.goal_id else None,
            "market_id": str(deal.market_id) if hasattr(deal, 'market_id') and deal.market_id else None,
            "market_name": market_name,
            "created_at": deal.created_at if hasattr(deal, 'created_at') else datetime.utcnow(),
            "updated_at": deal.updated_at if hasattr(deal, 'updated_at') else datetime.utcnow(),
            "is_tracked": is_tracked,
            "latest_score": float(deal.score) if hasattr(deal, 'score') and deal.score else None,
            "price_history": [],  # Placeholder, filled in by specific endpoints
            "market_analysis": None,  # Placeholder for market data
            "deal_score": float(deal.score) if hasattr(deal, 'score') and deal.score else None,
            "features": None,  # For future use
            "ai_analysis": ai_analysis
        }
        
        # Adapt AI analysis to match frontend expectations if it exists
        if ai_analysis and isinstance(ai_analysis, dict):
            # Copy to avoid modifying the original
            updated_analysis = dict(ai_analysis)
            
            # Ensure score is between 0-10 for frontend
            if "score" in updated_analysis and isinstance(updated_analysis["score"], (int, float)):
                # If score is a fraction (0-1), convert to 0-10 scale
                if updated_analysis["score"] <= 1:
                    updated_analysis["score"] = updated_analysis["score"] * 10
                # Ensure it's within 0-10 range
                updated_analysis["score"] = max(0, min(10, updated_analysis["score"]))
            
            # Ensure the structure matches the frontend expectations
            if "price_analysis" in updated_analysis:
                price_analysis = updated_analysis["price_analysis"]
                # Ensure the required fields exist
                if "discount_percentage" not in price_analysis:
                    price_analysis["discount_percentage"] = 0
                if "is_good_deal" not in price_analysis:
                    price_analysis["is_good_deal"] = False
                if "price_trend" not in price_analysis:
                    price_analysis["price_trend"] = "unknown"
            else:
                updated_analysis["price_analysis"] = {
                    "discount_percentage": 0,
                    "is_good_deal": False,
                    "price_trend": "unknown"
                }
            
            # Ensure market_analysis structure
            if "market_analysis" in updated_analysis:
                market_analysis = updated_analysis["market_analysis"]
                if "competition" not in market_analysis:
                    market_analysis["competition"] = "Average"
                if "availability" not in market_analysis:
                    market_analysis["availability"] = "Unknown"
            else:
                updated_analysis["market_analysis"] = {
                    "competition": "Average",
                    "availability": "Unknown"
                }
            
            # Ensure recommendations exist
            if "recommendations" not in updated_analysis or not updated_analysis["recommendations"]:
                updated_analysis["recommendations"] = ["No specific recommendations available."]
            
            # Update the response with the adjusted analysis
            response["ai_analysis"] = updated_analysis
        
        return response

def main():
    # Create a mock deal
    mock_deal = MockDeal(
        id=str(uuid4()),
        title="HP 15.6\" Business Laptop, Free Microsoft Office 2024 Lifetime License",
        description="HP laptop with Copilot AI Chat, HD Touchscreen Display, Intel 6-Core i3-1215U 4.4 GHz, 16GB RAM",
        price=401.99,
        original_price=499.99,
        currency="USD",
        source="amazon",
        status="active",
        market_id=str(uuid4()),
        url="https://www.amazon.com/dp/B0CWN27G3V",
        image_url="https://m.media-amazon.com/images/I/71xEfn8Qi8L.jpg",
        found_at=datetime.utcnow(),
        expires_at=datetime.utcnow().replace(year=datetime.utcnow().year + 1),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        seller_info={"name": "Amazon", "rating": 4.5, "reviews": 1200},
        availability={"in_stock": True, "quantity": 10},
        deal_metadata={"source": "amazon", "scraped_at": datetime.utcnow().isoformat(), "search_query": "laptop"},
        price_metadata={},
        category="electronics",
        score=0.85
    )
    
    # Create a mock AI analysis
    mock_analysis = {
        "deal_id": str(mock_deal.id),
        "score": 0.5,
        "confidence": 0.6,
        "price_analysis": {
            "discount_percentage": 20,
            "is_good_deal": False,
            "price_trend": "unknown",
            "trend_details": {},
            "original_price": 499.99,
            "current_price": 401.99
        },
        "market_analysis": {
            "competition": "Average",
            "availability": "Available",
            "market_info": {
                "name": "Amazon",
                "type": "amazon"
            },
            "price_position": "Mid-range",
            "popularity": "Unknown"
        },
        "recommendations": [
            "Limited discount on this item. Consider waiting for a better deal.",
            "Compare features with similar models in this price range."
        ],
        "analysis_date": datetime.utcnow().isoformat(),
        "expiration_analysis": "Deal expires on " + mock_deal.expires_at.isoformat()
    }
    
    # Create mock deal service
    deal_service = MockDealService()
    
    # Get a response with the mocked analysis
    response = deal_service._convert_to_response(mock_deal, include_ai_analysis=True, analysis=mock_analysis)
    
    # Pretty print the response
    logger.info(f"Deal response with AI analysis:")
    logger.info(json.dumps(response, indent=2, default=str))
    
    # Check if the AI analysis is in the expected format for frontend
    ai_analysis = response.get('ai_analysis')
    if ai_analysis:
        logger.info(f"AI analysis score: {ai_analysis.get('score')}")
        logger.info(f"AI analysis confidence: {ai_analysis.get('confidence')}")
        logger.info(f"Price analysis: {json.dumps(ai_analysis.get('price_analysis'), indent=2, default=str)}")
        logger.info(f"Market analysis: {json.dumps(ai_analysis.get('market_analysis'), indent=2, default=str)}")
        logger.info(f"Recommendations: {json.dumps(ai_analysis.get('recommendations'), indent=2, default=str)}")
    else:
        logger.warning("No AI analysis found in the response")

if __name__ == '__main__':
    main() 