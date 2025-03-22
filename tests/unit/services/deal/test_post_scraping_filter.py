"""
Unit tests for the post_scraping_filter module.
"""

import pytest
from unittest.mock import patch
from typing import Dict, Any, List, Optional, Tuple
import uuid

from core.services.deal.search.post_scraping_filter import (
    extract_price_constraints,
    extract_search_terms,
    extract_product_price,
    filter_products_by_price,
    calculate_text_similarity,
    calculate_keyword_presence,
    calculate_relevance_score,
    normalize_scores,
    extract_brands_from_query,
    post_process_products
)


class TestPostScrapingFilter:
    """Tests for the post-scraping filter module."""
    
    def test_extract_price_constraints(self):
        """Test extraction of price constraints from queries."""
        # Test "under X" pattern
        min_price, max_price = extract_price_constraints("Laptop under $1000")
        assert min_price is None
        assert max_price == 1000.0
        
        # Test "over X" pattern
        min_price, max_price = extract_price_constraints("Laptop over $500")
        assert min_price == 500.0
        assert max_price is None
        
        # Test range pattern with dash
        min_price, max_price = extract_price_constraints("Laptop $500-$1000")
        assert min_price == 500.0
        assert max_price == 1000.0
        
        # Test range pattern with "to"
        min_price, max_price = extract_price_constraints("Laptop $500 to $1000")
        assert min_price == 500.0
        assert max_price == 1000.0
        
        # Test "less than" pattern
        min_price, max_price = extract_price_constraints("Laptop less than $800")
        assert min_price is None
        assert max_price == 800.0
        
        # Test "more than" pattern
        min_price, max_price = extract_price_constraints("Laptop more than $600")
        assert min_price == 600.0
        assert max_price is None
        
        # Test no price constraints
        min_price, max_price = extract_price_constraints("Laptop")
        assert min_price is None
        assert max_price is None
        
        # Test multiple price patterns (first one should be used)
        min_price, max_price = extract_price_constraints("Laptop under $1000 over $500")
        assert min_price is None
        assert max_price == 1000.0
    
    def test_extract_search_terms(self):
        """Test extraction of search terms from queries."""
        # Test basic extraction
        terms = extract_search_terms("Laptop with 16GB RAM")
        assert set(terms) == {"laptop", "16gb", "ram"}
        
        # Test with filler phrases
        terms = extract_search_terms("I am looking for a laptop with 16GB RAM")
        assert set(terms) == {"laptop", "16gb", "ram"}
        
        # Test with price constraints
        terms = extract_search_terms("Laptop with 16GB RAM under $1000")
        assert set(terms) == {"laptop", "16gb", "ram"}
        
        # Test with all lowercase
        terms = extract_search_terms("laptop with 16gb ram")
        assert set(terms) == {"laptop", "16gb", "ram"}
        
        # Test with punctuation
        terms = extract_search_terms("Laptop, 16GB RAM, SSD!")
        assert set(terms) == {"laptop", "16gb", "ram", "ssd"}
        
        # Test with stop words
        terms = extract_search_terms("I want a laptop with 16GB of RAM")
        assert set(terms) == {"laptop", "16gb", "ram"}
    
    def test_extract_product_price(self):
        """Test extraction of price from product dictionaries."""
        # Test direct price field (number)
        product = {"title": "Test Product", "price": 99.99}
        assert extract_product_price(product) == 99.99
        
        # Test direct price field (string with currency symbol)
        product = {"title": "Test Product", "price": "$99.99"}
        assert extract_product_price(product) == 99.99
        
        # Test price_data with value
        product = {"title": "Test Product", "price_data": {"value": 99.99}}
        assert extract_product_price(product) == 99.99
        
        # Test price_data with amount
        product = {"title": "Test Product", "price_data": {"amount": 99.99}}
        assert extract_product_price(product) == 99.99
        
        # Test original_price field
        product = {"title": "Test Product", "original_price": 99.99}
        assert extract_product_price(product) == 99.99
        
        # Test price_string field
        product = {"title": "Test Product", "price_string": "$99.99"}
        assert extract_product_price(product) == 99.99
        
        # Test with missing price
        product = {"title": "Test Product"}
        assert extract_product_price(product) is None
        
        # Test with invalid price
        product = {"title": "Test Product", "price": "not a price"}
        assert extract_product_price(product) is None
    
    def test_filter_products_by_price(self):
        """Test filtering products by price constraints."""
        products = [
            {"id": "1", "title": "Cheap Product", "price": 50.0},
            {"id": "2", "title": "Mid-range Product", "price": 100.0},
            {"id": "3", "title": "Expensive Product", "price": 200.0},
            {"id": "4", "title": "No Price Product"},
        ]
        
        # Test with no price constraints
        filtered = filter_products_by_price(products, None, None)
        assert len(filtered) == 4
        
        # Test with only min_price
        filtered = filter_products_by_price(products, 75.0, None)
        assert len(filtered) == 2
        assert filtered[0]["id"] == "2"
        assert filtered[1]["id"] == "3"
        
        # Test with only max_price
        filtered = filter_products_by_price(products, None, 150.0)
        assert len(filtered) == 2
        assert filtered[0]["id"] == "1"
        assert filtered[1]["id"] == "2"
        
        # Test with both min_price and max_price
        filtered = filter_products_by_price(products, 75.0, 150.0)
        assert len(filtered) == 1
        assert filtered[0]["id"] == "2"
        
        # Test with product missing price (should be included)
        filtered = filter_products_by_price([products[3]], 10.0, 100.0)
        assert len(filtered) == 1
    
    def test_calculate_text_similarity(self):
        """Test calculation of text similarity between strings."""
        # Test identical strings
        similarity = calculate_text_similarity("laptop", "laptop")
        assert similarity == 1.0
        
        # Test different but similar strings
        similarity = calculate_text_similarity("laptop", "laptops")
        assert similarity > 0.8
        
        # Test completely different strings
        similarity = calculate_text_similarity("laptop", "smartphone")
        assert similarity < 0.5
        
        # Test case insensitivity
        similarity_1 = calculate_text_similarity("LAPTOP", "laptop")
        similarity_2 = calculate_text_similarity("laptop", "laptop")
        assert similarity_1 == similarity_2
        
        # Test with empty strings
        similarity = calculate_text_similarity("", "")
        assert similarity == 1.0
        
        similarity = calculate_text_similarity("laptop", "")
        assert similarity == 0.0
    
    def test_calculate_keyword_presence(self):
        """Test calculation of keyword presence in text."""
        # Test with single keyword
        score = calculate_keyword_presence("apple iphone 13", ["iphone"])
        assert score > 0.0
        
        # Test with multiple keywords, all present
        score = calculate_keyword_presence("apple iphone 13", ["apple", "iphone"])
        assert score > 0.0
        
        # Test with multiple keywords, some present
        score_1 = calculate_keyword_presence("apple iphone 13", ["apple", "iphone"])
        score_2 = calculate_keyword_presence("apple iphone 13", ["apple", "samsung"])
        assert score_1 > score_2
        
        # Test with no keywords present
        score = calculate_keyword_presence("apple iphone 13", ["samsung", "galaxy"])
        assert score == 0.0
        
        # Test with empty text
        score = calculate_keyword_presence("", ["apple", "iphone"])
        assert score == 0.0
        
        # Test with empty keywords
        score = calculate_keyword_presence("apple iphone 13", [])
        assert score == 0.0
    
    def test_calculate_relevance_score(self):
        """Test calculation of relevance score for products."""
        # Basic product with title and description
        product = {
            "id": "1",
            "title": "Apple iPhone 13",
            "description": "Latest iPhone with A15 Bionic chip",
            "price": 799.0
        }
        
        # Test with matching terms
        score = calculate_relevance_score(product, ["iphone", "apple"])
        assert score > 0.0
        
        # Test with non-matching terms
        score_1 = calculate_relevance_score(product, ["iphone", "apple"])
        score_2 = calculate_relevance_score(product, ["samsung", "galaxy"])
        assert score_1 > score_2
        
        # Test with brand matching
        score_1 = calculate_relevance_score(product, ["smartphone"], brands=["apple"])
        score_2 = calculate_relevance_score(product, ["smartphone"], brands=["samsung"])
        assert score_1 > score_2
        
        # Test with feature matching
        score_1 = calculate_relevance_score(product, ["smartphone"], features=["a15", "bionic"])
        score_2 = calculate_relevance_score(product, ["smartphone"], features=["snapdragon"])
        assert score_1 > score_2
        
        # Test with incomplete product
        incomplete_product = {"id": "2", "title": "Apple iPhone 13"}
        score = calculate_relevance_score(incomplete_product, ["iphone", "apple"])
        assert score > 0.0
    
    def test_normalize_scores(self):
        """Test normalization of scores for products."""
        products = [
            {"id": "1", "relevance_score": 0.8},
            {"id": "2", "relevance_score": 0.4},
            {"id": "3", "relevance_score": 0.6}
        ]
        
        normalized = normalize_scores(products)
        
        # Check that scores are normalized to [0,1] range
        assert all(0.0 <= p["relevance_score"] <= 1.0 for p in normalized)
        
        # Check that highest score is normalized to 1.0
        assert normalized[0]["relevance_score"] == 1.0
        
        # Check that relative ordering is preserved
        assert normalized[0]["id"] == "1"
        assert normalized[1]["id"] == "3"
        assert normalized[2]["id"] == "2"
        
        # Test with single product
        single_product = [{"id": "1", "relevance_score": 0.5}]
        normalized = normalize_scores(single_product)
        assert normalized[0]["relevance_score"] == 1.0
        
        # Test with empty list
        empty_list = []
        normalized = normalize_scores(empty_list)
        assert normalized == []
    
    def test_extract_brands_from_query(self):
        """Test extraction of brands from query."""
        # Test with explicit brand
        brands = extract_brands_from_query("Apple iPhone 13", common_brands=["Apple", "Samsung", "Google"])
        assert "Apple" in brands
        assert "Samsung" not in brands
        
        # Test with no brand
        brands = extract_brands_from_query("smartphone", common_brands=["Apple", "Samsung", "Google"])
        assert len(brands) == 0
        
        # Test with multiple brands
        brands = extract_brands_from_query("Apple vs Samsung", common_brands=["Apple", "Samsung", "Google"])
        assert "Apple" in brands
        assert "Samsung" in brands
        assert "Google" not in brands
        
        # Test case insensitivity
        brands = extract_brands_from_query("apple iphone", common_brands=["Apple", "Samsung", "Google"])
        assert "Apple" in brands
        
        # Test with no common brands provided
        brands = extract_brands_from_query("Apple iPhone 13")
        assert len(brands) == 0
    
    def test_post_process_products(self):
        """Test post-processing of products."""
        products = [
            {
                "id": "1",
                "title": "Apple iPhone 13",
                "description": "Latest iPhone with A15 Bionic chip",
                "price": 799.0,
                "brand": "Apple"
            },
            {
                "id": "2",
                "title": "Samsung Galaxy S21",
                "description": "Android smartphone with excellent camera",
                "price": 699.0,
                "brand": "Samsung"
            },
            {
                "id": "3",
                "title": "Google Pixel 6",
                "description": "Pure Android experience with great photos",
                "price": 599.0,
                "brand": "Google"
            }
        ]
        
        # Test with no filters
        processed = post_process_products(products, "smartphone")
        assert len(processed) == 3
        
        # Test with price filters
        processed = post_process_products(products, "smartphone", min_price=700.0)
        assert len(processed) == 1
        assert processed[0]["id"] == "1"
        
        # Test with brand filter
        processed = post_process_products(products, "smartphone", brands=["Samsung"])
        assert len(processed) == 3  # All products returned, but Samsung should be first
        assert processed[0]["id"] == "2"
        
        # Test with search terms
        processed = post_process_products(products, "iphone", search_terms=["iphone", "apple"])
        assert len(processed) == 3
        assert processed[0]["id"] == "1"  # iPhone should be first
        
        # Test with features
        processed = post_process_products(products, "smartphone", features=["android"])
        assert len(processed) == 3
        assert processed[0]["id"] in ["2", "3"]  # Samsung or Google should be first
        
        # Test with empty products list
        processed = post_process_products([], "smartphone")
        assert processed == [] 