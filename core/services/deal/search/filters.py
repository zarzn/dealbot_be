"""
Filtering module for deal search.

This module provides functionality for filtering products and deals
based on various criteria such as price, relevance, and text similarity.
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple, Union
from uuid import UUID, uuid4

from core.utils.logger import get_logger

logger = get_logger(__name__)

async def filter_deals(
    self,
    products: List[Dict[str, Any]],
    query: str,
    normalized_terms: List[str],
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    brands: Optional[List[str]] = None,
    features: Optional[List[str]] = None,
    quality_requirement: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
    """Filter products based on various criteria and calculate relevance scores.
    
    Args:
        products: List of product dictionaries to filter
        query: Original search query
        normalized_terms: Normalized search terms for matching
        min_price: Minimum price filter
        max_price: Maximum price filter
        brands: List of desired brands to filter by
        features: List of desired features to filter by
        quality_requirement: Quality requirement string
        
    Returns:
        Tuple of (filtered_products, product_scores)
    """
    logger.info(f"Filtering {len(products)} products with criteria: min_price={min_price}, max_price={max_price}")
    
    # Initialize scores dictionary and filtered products list
    product_scores = {}
    filtered_products = []
    
    # Define basic similarity and term matching functions
    def basic_similarity(string1, string2):
        """Calculate basic similarity between two strings."""
        if not string1 or not string2:
            return 0
            
        s1 = string1.lower()
        s2 = string2.lower()
        
        # Direct match
        if s1 == s2:
            return 1.0
            
        # Substring match
        if s1 in s2 or s2 in s1:
            return 0.8
            
        # Word match - count matching words
        words1 = set(s1.split())
        words2 = set(s2.split())
        common_words = words1.intersection(words2)
        
        if not words1 or not words2:
            return 0
            
        return len(common_words) / max(len(words1), len(words2))
    
    def flexible_term_match(term, text):
        """Check if a term matches flexibly in text."""
        if not term or not text:
            return False
            
        term = term.lower()
        text = text.lower()
        
        # Direct match
        if term in text:
            return True
            
        # Handle plurals
        if term.endswith('s') and term[:-1] in text:
            return True
        if not term.endswith('s') and f"{term}s" in text:
            return True
            
        # Handle hyphenation
        if '-' in term:
            non_hyphen = term.replace('-', '')
            if non_hyphen in text:
                return True
                
        if ' ' in term:
            hyphenated = term.replace(' ', '-')
            if hyphenated in text:
                return True
                
        return False
    
    # Process each product
    for product in products:
        # Skip products with no price or missing essential data
        if 'price' not in product or product['price'] is None:
            continue
            
        if 'title' not in product or not product['title']:
            continue
            
        # Initialize score
        score = 0.0
        score_reasons = []
        
        # Convert price to float for comparison
        try:
            price = float(product['price'])
        except (ValueError, TypeError):
            continue
            
        # Apply price filtering
        if min_price is not None and price < min_price:
            continue
            
        if max_price is not None and price > max_price:
            continue
            
        # Score: term matching in title
        title = product.get('title', '').lower()
        title_match_score = 0
        
        for term in normalized_terms:
            if flexible_term_match(term, title):
                title_match_score += 1
                
        if normalized_terms:
            title_match_ratio = title_match_score / len(normalized_terms)
            score += title_match_ratio * 0.4  # Title matches are important
            score_reasons.append(f"Title match: {title_match_ratio:.2f}")
        
        # Score: term matching in description
        description = product.get('description', '').lower()
        desc_match_score = 0
        
        for term in normalized_terms:
            if flexible_term_match(term, description):
                desc_match_score += 1
                
        if normalized_terms and description:
            desc_match_ratio = desc_match_score / len(normalized_terms)
            score += desc_match_ratio * 0.2  # Description matches less important than title
            score_reasons.append(f"Description match: {desc_match_ratio:.2f}")
        
        # Score: brand matching if brands are specified
        if brands:
            brand_matches = 0
            product_brand = product.get('brand', '').lower()
            
            if not product_brand and 'metadata' in product:
                # Try to find brand in metadata
                product_brand = product['metadata'].get('brand', '').lower()
                
            for brand in brands:
                if flexible_term_match(brand.lower(), product_brand) or \
                   flexible_term_match(brand.lower(), title) or \
                   flexible_term_match(brand.lower(), description):
                    brand_matches += 1
                    
            if brand_matches > 0:
                brand_match_ratio = brand_matches / len(brands)
                score += brand_match_ratio * 0.2
                score_reasons.append(f"Brand match: {brand_match_ratio:.2f}")
        
        # Score: feature matching if features are specified
        if features:
            feature_matches = 0
            for feature in features:
                if flexible_term_match(feature.lower(), title) or \
                   flexible_term_match(feature.lower(), description):
                    feature_matches += 1
                    
            if feature_matches > 0:
                feature_match_ratio = feature_matches / len(features)
                score += feature_match_ratio * 0.2
                score_reasons.append(f"Feature match: {feature_match_ratio:.2f}")
        
        # Discount bonus: if original price is available, give bonus for bigger discounts
        if 'original_price' in product and product['original_price'] and product['original_price'] > price:
            try:
                original_price = float(product['original_price'])
                discount_percent = (original_price - price) / original_price * 100
                
                if discount_percent >= 50:
                    score += 0.2
                    score_reasons.append("Large discount (50%+)")
                elif discount_percent >= 30:
                    score += 0.1
                    score_reasons.append("Good discount (30%+)")
                elif discount_percent >= 15:
                    score += 0.05
                    score_reasons.append("Moderate discount (15%+)")
            except (ValueError, TypeError):
                pass
        
        # Quality score based on reviews/ratings if available
        review_count = 0
        rating = 0
        
        if 'rating' in product:
            try:
                rating = float(product['rating'])
            except (ValueError, TypeError):
                pass
                
        if 'review_count' in product:
            try:
                review_count = int(product['review_count'])
            except (ValueError, TypeError):
                pass
        
        # Metadata might have this info if not in the main product data
        if 'metadata' in product:
            metadata = product['metadata']
            if not rating and 'rating' in metadata:
                try:
                    rating = float(metadata['rating'])
                except (ValueError, TypeError):
                    pass
                    
            if not review_count and 'review_count' in metadata:
                try:
                    review_count = int(metadata['review_count'])
                except (ValueError, TypeError):
                    pass
        
        # Add score for high ratings with sufficient reviews
        if rating > 0 and review_count > 0:
            rating_score = 0
            
            if rating >= 4.5 and review_count >= 100:
                rating_score = 0.15
                score_reasons.append("Excellent rating (4.5+ with 100+ reviews)")
            elif rating >= 4.0 and review_count >= 50:
                rating_score = 0.1
                score_reasons.append("Very good rating (4.0+ with 50+ reviews)")
            elif rating >= 3.5 and review_count >= 20:
                rating_score = 0.05
                score_reasons.append("Good rating (3.5+ with 20+ reviews)")
                
            score += rating_score
        
        # Store the score
        product_scores[product.get('id', str(uuid4()))] = score
        
        # Add product to filtered products
        product['relevance_score'] = score
        product['relevance_reasons'] = score_reasons
        filtered_products.append(product)
    
    # Sort filtered products by score
    filtered_products.sort(key=lambda p: p.get('relevance_score', 0), reverse=True)
    
    logger.info(f"Filtered down to {len(filtered_products)} products that match criteria")
    if filtered_products:
        logger.info(f"Top product score: {filtered_products[0].get('relevance_score', 0)}")
        
    return filtered_products, product_scores 