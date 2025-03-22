# AI Prompt Guide for Scraper API Search Query Formatting

This document provides guidelines and templates for creating AI prompts that format search queries optimally for different marketplaces via the Scraper API.

## Overview

The AI system helps transform user queries into optimized search terms that work effectively with different marketplaces. The goal is to ensure that:

1. Price constraints are properly expressed
2. Relevant keywords are included
3. Brand specifications are clear
4. Optional features are highlighted
5. The query format matches marketplace-specific syntax preferences

## System Prompt Template

```
You are a search query optimization assistant that helps format user search queries for e-commerce marketplaces.
Your task is to transform natural language shopping queries into optimized search terms.

For each query, you should:
1. Extract the core product being searched for
2. Identify any price constraints (minimum/maximum)
3. Identify brand preferences
4. Identify key features or specifications
5. Output a formatted search query that respects the syntax of the target marketplace

The output should be a plain search query string without any explanation, formatted optimally for the specified marketplace.
```

## User Query Format (Input)

The user query should be presented in this format:

```
Format a search query for [MARKETPLACE]:
[USER SEARCH DESCRIPTION]
```

Example user queries:
- "Format a search query for Amazon: I'm looking for a wireless gaming headset under $75"
- "Format a search query for Walmart: Need a coffee maker with grinder built in, less than $100"
- "Format a search query for Google Shopping: Apple iPad Pro 12.9 inch around $800-$1000"

## Output Format

The AI should respond with a plain, formatted search query, optimized for the specified marketplace.

For example:
```
wireless gaming headset under $75
```

## Marketplace-Specific Guidelines

### Amazon

- Best query format: `[product] [key features] [price constraint]`
- Avoid quotation marks unless exact phrase matching is required
- Include brand name before product (e.g., "Sony wireless headphones")
- Use "under $X" format for maximum price
- Use "$X-$Y" format for price ranges

### Walmart

- Best query format: `[product] [key features] [price constraint]`
- Similar to Amazon, but may benefit from simpler, shorter queries
- Avoid complex Boolean operators
- Include specific models when known (e.g., "iPhone 13 Pro")

### Google Shopping

- Best query format: `[brand] [product] [key features] [price constraint]`
- Google Shopping works well with more natural language queries
- Can include specific features in more detail
- Price constraints work well with "under $X" format

## Example AI Prompt Responses

### Example 1

**User Input:**
```
Format a search query for Amazon:
I want a 4K TV with at least 55 inch screen and HDMI 2.1 ports for gaming, preferably Samsung or LG, my budget is $700-$1200
```

**AI Output:**
```
Samsung LG 55 inch 4K TV HDMI 2.1 gaming $700-$1200
```

### Example 2

**User Input:**
```
Format a search query for Walmart:
Looking for a kitchen blender that can handle ice and frozen fruit, preferably under 100 dollars
```

**AI Output:**
```
blender ice frozen fruit under $100
```

### Example 3

**User Input:**
```
Format a search query for Google Shopping:
I need noise cancelling headphones with good battery life, wireless, under $200
```

**AI Output:**
```
wireless noise cancelling headphones long battery life under $200
```

## Fallback Formatting Rules

When AI is unavailable, these rules should be applied programmatically:

1. Remove filler words like "I want", "looking for", "find me", etc.
2. Extract price constraints using regex:
   - `under $X` → extract X as max_price
   - `$X-$Y` → extract X as min_price, Y as max_price
   - `over $X` → extract X as min_price
3. Keep brand names intact
4. Remove unnecessary adjectives and articles
5. Ensure key product type and features remain

## Implementation Guidelines

For the fallback function (when AI is unavailable):

```python
def format_search_query_fallback(query: str) -> str:
    """Format a search query without using AI."""
    
    # Remove common filler phrases
    fillers = ["i want", "i need", "looking for", "find me", "searching for", "can you find"]
    normalized_query = query.lower()
    for filler in fillers:
        normalized_query = normalized_query.replace(filler, "")
    
    # Extract price constraints
    price_under_match = re.search(r'under\s+\$?(\d+)', normalized_query)
    price_range_match = re.search(r'\$?(\d+)\s*-\s*\$?(\d+)', normalized_query)
    price_above_match = re.search(r'over\s+\$?(\d+)', normalized_query)
    
    min_price = None
    max_price = None
    
    if price_under_match:
        max_price = float(price_under_match.group(1))
    elif price_range_match:
        min_price = float(price_range_match.group(1))
        max_price = float(price_range_match.group(2))
    elif price_above_match:
        min_price = float(price_above_match.group(1))
    
    # Remove unnecessary words
    stop_words = {'a', 'an', 'the', 'and', 'or', 'for', 'in', 'on', 'at', 'to', 'with', 'by'}
    words = normalized_query.split()
    filtered_words = [word for word in words if word not in stop_words]
    
    # Reconstruct the query
    formatted_query = " ".join(filtered_words).strip()
    
    return formatted_query
```

## Continuous Improvement

As you collect more data from the explorer script, update this document with:

1. More effective query patterns for each marketplace
2. Specific syntax that yields better results
3. Keywords or patterns to avoid
4. Price constraint formats that work most reliably

The goal is continuous refinement of both AI prompts and fallback methods to ensure optimal search results across all marketplaces. 