"""
Search utilities for deal operations.

This module contains common utility functions used across different
search operations, including text processing and result formatting.
"""

import re
from typing import Dict, Any, List, Optional, Tuple, Union
import difflib
from collections import Counter

from core.utils.logger import get_logger

logger = get_logger(__name__)

def normalize_text(text: str) -> str:
    """
    Normalize text by lowercasing and removing extra whitespace.
    
    Args:
        text: The text to normalize
        
    Returns:
        Normalized text string
    """
    if not text:
        return ""
    # Convert to lowercase
    normalized = text.lower()
    # Replace multiple spaces with a single space
    normalized = re.sub(r'\s+', ' ', normalized)
    # Remove leading and trailing whitespace
    normalized = normalized.strip()
    return normalized

def calculate_similarity(text1: str, text2: str) -> float:
    """
    Calculate string similarity between two texts.
    
    Args:
        text1: First text string
        text2: Second text string
        
    Returns:
        Similarity score between 0 and 1
    """
    if not text1 or not text2:
        return 0.0
    
    # Normalize texts
    norm_text1 = normalize_text(text1)
    norm_text2 = normalize_text(text2)
    
    # Calculate similarity using difflib
    similarity = difflib.SequenceMatcher(None, norm_text1, norm_text2).ratio()
    return similarity

def extract_text_features(text: str) -> Dict[str, Any]:
    """
    Extract features from text such as keywords, numbers, and phrases.
    
    Args:
        text: Text to analyze
        
    Returns:
        Dictionary of extracted features
    """
    if not text:
        return {"keywords": [], "numbers": [], "phrases": []}
    
    # Normalize text
    normalized = normalize_text(text)
    
    # Extract keywords (non-stop words)
    stop_words = {
        'a', 'an', 'the', 'and', 'or', 'but', 'for', 'nor', 'on', 'at', 'to', 'by',
        'this', 'that', 'these', 'those', 'is', 'are', 'was', 'were', 'be', 'been',
        'being', 'have', 'has', 'had', 'do', 'does', 'did', 'of', 'in', 'with'
    }
    
    words = re.findall(r'\b\w+\b', normalized)
    keywords = [word for word in words if word not in stop_words and len(word) > 1]
    
    # Extract numbers
    numbers = re.findall(r'\b\d+(?:\.\d+)?\b', normalized)
    numbers = [float(num) for num in numbers]
    
    # Remove punctuation for phrase extraction
    normalized_no_punct = re.sub(r'[^\w\s]', ' ', normalized)
    normalized_no_punct = re.sub(r'\s+', ' ', normalized_no_punct).strip()
    
    # Extract potential phrases (2-3 word sequences)
    words = normalized_no_punct.split()
    bigrams = [' '.join(words[i:i+2]) for i in range(len(words)-1)]
    trigrams = [' '.join(words[i:i+3]) for i in range(len(words)-2)]
    phrases = bigrams + trigrams
    
    return {
        "keywords": keywords,
        "numbers": numbers,
        "phrases": phrases
    }

def format_price(price: Union[float, int, str]) -> Optional[float]:
    """
    Format and validate a price value.
    
    Args:
        price: Price value in various formats
        
    Returns:
        Formatted price as float or None if invalid
    """
    if price is None:
        return None
    
    # Handle string prices
    if isinstance(price, str):
        # Remove currency symbols and commas
        price_str = re.sub(r'[^\d.]', '', price)
        try:
            return float(price_str)
        except ValueError:
            return None
    
    # Handle numeric prices
    try:
        return float(price)
    except (ValueError, TypeError):
        return None

def truncate_text(text: str, max_length: int = 100, add_ellipsis: bool = True) -> str:
    """
    Truncate text to a maximum length.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        add_ellipsis: Whether to add ellipsis if truncated
        
    Returns:
        Truncated text
    """
    if not text:
        return ""
    
    if len(text) <= max_length:
        return text
    
    truncated = text[:max_length].rstrip()
    if add_ellipsis:
        truncated += "..."
    
    return truncated 