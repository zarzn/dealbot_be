"""
Unit tests for the deal search filters module.
"""

import pytest
from unittest.mock import MagicMock, patch
import logging
from uuid import uuid4

from core.services.deal.search.filters import filter_deals


class TestDealSearchFilters:
    """Tests for the deal search filters module."""
    
    @pytest.mark.asyncio
    async def test_filter_deals_empty_products(self):
        """Test filtering with empty products list."""
        test_instance = MagicMock()
        filtered, scores = await filter_deals(
            test_instance,
            products=[],
            query="test query",
            normalized_terms=["test", "query"]
        )
        
        assert filtered == []
        assert scores == {}
    
    @pytest.mark.asyncio
    async def test_filter_deals_price_filtering(self):
        """Test filtering products by price."""
        test_instance = MagicMock()
        
        # Test products with various prices
        products = [
            {
                "id": str(uuid4()),
                "title": "Cheap Product",
                "price": 10.0,
                "description": "This is a cheap product"
            },
            {
                "id": str(uuid4()),
                "title": "Mid-range Product",
                "price": 50.0,
                "description": "This is a mid-range product"
            },
            {
                "id": str(uuid4()),
                "title": "Expensive Product",
                "price": 100.0,
                "description": "This is an expensive product"
            }
        ]
        
        # Test min_price filter
        filtered, scores = await filter_deals(
            test_instance,
            products=products,
            query="product",
            normalized_terms=["product"],
            min_price=40.0
        )
        
        assert len(filtered) == 2
        assert filtered[0]["title"] in ["Mid-range Product", "Expensive Product"]
        assert filtered[1]["title"] in ["Mid-range Product", "Expensive Product"]
        
        # Test max_price filter
        filtered, scores = await filter_deals(
            test_instance,
            products=products,
            query="product",
            normalized_terms=["product"],
            max_price=60.0
        )
        
        assert len(filtered) == 2
        assert filtered[0]["title"] in ["Cheap Product", "Mid-range Product"]
        assert filtered[1]["title"] in ["Cheap Product", "Mid-range Product"]
        
        # Test both min_price and max_price filters
        filtered, scores = await filter_deals(
            test_instance,
            products=products,
            query="product",
            normalized_terms=["product"],
            min_price=30.0,
            max_price=70.0
        )
        
        assert len(filtered) == 1
        assert filtered[0]["title"] == "Mid-range Product"
    
    @pytest.mark.asyncio
    async def test_filter_deals_term_matching(self):
        """Test filtering products by term matching."""
        test_instance = MagicMock()
        
        # Test products with various titles and descriptions
        products = [
            {
                "id": str(uuid4()),
                "title": "Apple iPhone 13",
                "price": 799.0,
                "description": "Latest iPhone with A15 Bionic chip"
            },
            {
                "id": str(uuid4()),
                "title": "Samsung Galaxy S21",
                "price": 699.0,
                "description": "Android smartphone with excellent camera"
            },
            {
                "id": str(uuid4()),
                "title": "Google Pixel 6",
                "price": 599.0,
                "description": "Pure Android experience with great photos"
            }
        ]
        
        # Test term matching in title
        filtered, scores = await filter_deals(
            test_instance,
            products=products,
            query="iphone",
            normalized_terms=["iphone"]
        )
        
        assert len(filtered) == 3  # Still returns all products, but scored differently
        assert filtered[0]["title"] == "Apple iPhone 13"  # iPhone should be first
        assert filtered[0]["relevance_score"] > filtered[1]["relevance_score"]
        
        # Test term matching in description
        filtered, scores = await filter_deals(
            test_instance,
            products=products,
            query="camera",
            normalized_terms=["camera"]
        )
        
        assert len(filtered) == 3
        # Samsung or Pixel should have higher scores than iPhone due to "camera" in description
        assert filtered[0]["title"] in ["Samsung Galaxy S21", "Google Pixel 6"]
        
        # Test multiple terms
        filtered, scores = await filter_deals(
            test_instance,
            products=products,
            query="android smartphone",
            normalized_terms=["android", "smartphone"]
        )
        
        assert len(filtered) == 3
        # Samsung should be first due to having both terms
        assert filtered[0]["title"] == "Samsung Galaxy S21"
    
    @pytest.mark.asyncio
    async def test_filter_deals_brand_matching(self):
        """Test filtering products by brand matching."""
        test_instance = MagicMock()
        
        # Test products with various brands
        products = [
            {
                "id": str(uuid4()),
                "title": "Apple iPhone 13",
                "price": 799.0,
                "brand": "Apple",
                "description": "Latest iPhone with A15 Bionic chip"
            },
            {
                "id": str(uuid4()),
                "title": "Samsung Galaxy S21",
                "price": 699.0,
                "brand": "Samsung",
                "description": "Android smartphone with excellent camera"
            },
            {
                "id": str(uuid4()),
                "title": "Google Pixel 6",
                "price": 599.0,
                "brand": "Google",
                "description": "Pure Android experience with great photos"
            }
        ]
        
        # Test brand matching
        filtered, scores = await filter_deals(
            test_instance,
            products=products,
            query="phone",
            normalized_terms=["phone"],
            brands=["Apple"]
        )
        
        assert len(filtered) == 3  # Still returns all products, but scored differently
        assert filtered[0]["title"] == "Apple iPhone 13"  # Apple should be first
        assert filtered[0]["relevance_score"] > filtered[1]["relevance_score"]
        
        # Test with brand in metadata
        products[2]["brand"] = ""
        products[2]["metadata"] = {"brand": "Google"}
        
        filtered, scores = await filter_deals(
            test_instance,
            products=products,
            query="phone",
            normalized_terms=["phone"],
            brands=["Google"]
        )
        
        assert len(filtered) == 3
        assert filtered[0]["title"] == "Google Pixel 6"  # Google should be first
    
    @pytest.mark.asyncio
    async def test_filter_deals_feature_matching(self):
        """Test filtering products by feature matching."""
        test_instance = MagicMock()
        
        # Test products with various features
        products = [
            {
                "id": str(uuid4()),
                "title": "4K HDR TV",
                "price": 799.0,
                "description": "Smart TV with 4K HDR display"
            },
            {
                "id": str(uuid4()),
                "title": "1080p TV",
                "price": 399.0,
                "description": "Budget TV with 1080p resolution"
            },
            {
                "id": str(uuid4()),
                "title": "8K QLED TV",
                "price": 1999.0,
                "description": "Premium TV with 8K resolution and QLED technology"
            }
        ]
        
        # Test feature matching
        filtered, scores = await filter_deals(
            test_instance,
            products=products,
            query="tv",
            normalized_terms=["tv"],
            features=["4K", "HDR"]
        )
        
        assert len(filtered) == 3  # Still returns all products, but scored differently
        assert filtered[0]["title"] == "4K HDR TV"  # 4K HDR TV should be first
        assert filtered[0]["relevance_score"] > filtered[1]["relevance_score"]
    
    @pytest.mark.asyncio
    async def test_filter_deals_discount_bonus(self):
        """Test discount bonus in scoring."""
        test_instance = MagicMock()
        
        # Test products with various discounts
        products = [
            {
                "id": str(uuid4()),
                "title": "Small Discount Product",
                "price": 85.0,
                "original_price": 100.0,  # 15% discount
                "description": "This product has a small discount"
            },
            {
                "id": str(uuid4()),
                "title": "Medium Discount Product",
                "price": 70.0,
                "original_price": 100.0,  # 30% discount
                "description": "This product has a medium discount"
            },
            {
                "id": str(uuid4()),
                "title": "Large Discount Product",
                "price": 40.0,
                "original_price": 100.0,  # 60% discount
                "description": "This product has a large discount"
            }
        ]
        
        # Test discount bonus
        filtered, scores = await filter_deals(
            test_instance,
            products=products,
            query="discount product",
            normalized_terms=["discount", "product"]
        )
        
        assert len(filtered) == 3
        # Products should be ordered by discount size (large to small)
        assert filtered[0]["title"] == "Large Discount Product"
        assert filtered[1]["title"] == "Medium Discount Product"
        assert filtered[2]["title"] == "Small Discount Product"
    
    @pytest.mark.asyncio
    async def test_filter_deals_rating_bonus(self):
        """Test rating bonus in scoring."""
        test_instance = MagicMock()
        
        # Test products with various ratings
        products = [
            {
                "id": str(uuid4()),
                "title": "Highly Rated Product",
                "price": 100.0,
                "rating": 4.8,
                "review_count": 200,
                "description": "This product has many excellent reviews"
            },
            {
                "id": str(uuid4()),
                "title": "Well Rated Product",
                "price": 80.0,
                "rating": 4.2,
                "review_count": 80,
                "description": "This product has good reviews"
            },
            {
                "id": str(uuid4()),
                "title": "Average Rated Product",
                "price": 60.0,
                "rating": 3.5,
                "review_count": 30,
                "description": "This product has average reviews"
            },
            {
                "id": str(uuid4()),
                "title": "Low Rated Product",
                "price": 40.0,
                "rating": 2.8,
                "review_count": 15,
                "description": "This product has poor reviews"
            }
        ]
        
        # Test rating bonus
        filtered, scores = await filter_deals(
            test_instance,
            products=products,
            query="rated product",
            normalized_terms=["rated", "product"]
        )
        
        assert len(filtered) == 4
        # Products should be ordered by rating and review count
        assert filtered[0]["title"] == "Highly Rated Product"
        assert filtered[1]["title"] == "Well Rated Product"
        assert filtered[2]["title"] == "Average Rated Product"
        assert filtered[3]["title"] == "Low Rated Product"
        
        # Test with rating in metadata
        products[0]["rating"] = None
        products[0]["review_count"] = None
        products[0]["metadata"] = {"rating": 4.8, "review_count": 200}
        
        filtered, scores = await filter_deals(
            test_instance,
            products=products,
            query="rated product",
            normalized_terms=["rated", "product"]
        )
        
        assert len(filtered) == 4
        assert filtered[0]["title"] == "Highly Rated Product"  # Should still be first
    
    @pytest.mark.asyncio
    async def test_filter_deals_missing_required_fields(self):
        """Test filtering products with missing required fields."""
        test_instance = MagicMock()
        
        # Test products with missing fields
        products = [
            {
                "id": str(uuid4()),
                "title": "Complete Product",
                "price": 100.0,
                "description": "This product has all required fields"
            },
            {
                "id": str(uuid4()),
                "description": "This product has no title"
            },
            {
                "id": str(uuid4()),
                "title": "No Price Product"
            },
            {
                "id": str(uuid4()),
                "title": "Invalid Price Product",
                "price": "not a number"
            }
        ]
        
        # Test filtering with missing fields
        filtered, scores = await filter_deals(
            test_instance,
            products=products,
            query="product",
            normalized_terms=["product"]
        )
        
        # Only the first product should be included
        assert len(filtered) == 1
        assert filtered[0]["title"] == "Complete Product" 