# Language Model Configuration

## Overview
The AI Agentic Deals System uses multiple Language Models (LLMs) to provide robust and reliable AI capabilities across different environments. Each model is selected for its specific strengths and use cases.

## Model Configurations

### 1. Production Environment (DeepSeek R1)
- **Model Name**: `deepseek-r1`
- **Environment Variable**: `DEEPSEEK_API_KEY`
- **Configuration**:
  ```python
  DeepSeek(
      api_key=settings.DEEPSEEK_API_KEY,
      model_name=settings.DEEPSEEK_MODEL_NAME,
      temperature=settings.LLM_TEMPERATURE,
      max_tokens=settings.LLM_MAX_TOKENS
  )
  ```
- **Use Cases**:
  - Production deal analysis
  - Critical decision making
  - High-stakes evaluations
- **Advantages**:
  - High accuracy
  - Specialized in deal evaluation
  - Production-grade reliability

### 2. Fallback Model (GPT-4)
- **Model Name**: `gpt-4`
- **Environment Variable**: `OPENAI_API_KEY`
- **Configuration**:
  ```python
  ChatOpenAI(
      model_name="gpt-4",
      openai_api_key=settings.OPENAI_API_KEY,
      temperature=settings.LLM_TEMPERATURE,
      max_tokens=settings.LLM_MAX_TOKENS
  )
  ```
- **Use Cases**:
  - Backup when primary model fails
  - Complex reasoning tasks
  - General-purpose AI tasks
- **Advantages**:
  - High reliability
  - Strong general performance
  - Well-documented behavior

### 3. Test Environment (Mock LLM)
- **Model Name**: `mock`
- **Environment Variable**: None required
- **Configuration**:
  ```python
  MockLLM()  # Custom implementation for testing
  ```
- **Use Cases**:
  - Unit testing
  - Integration testing
  - CI/CD pipelines
- **Advantages**:
  - No external dependencies
  - Fast execution
  - Deterministic responses

## Usage Guidelines

### Environment Variables
```bash
# Production
DEEPSEEK_API_KEY=your_deepseek_api_key
LLM_MODEL=deepseek

# Fallback
OPENAI_API_KEY=your_openai_api_key
LLM_MODEL=gpt4

# Testing
LLM_MODEL=mock
```

### Best Practices
1. **API Key Management**:
   - Never commit API keys to version control
   - Use environment variables or secure secrets management
   - Rotate keys regularly

2. **Error Handling**:
   - Always handle model-specific errors
   - Implement graceful fallback to backup models
   - Log all LLM-related errors for monitoring

3. **Performance Optimization**:
   - Cache responses when appropriate
   - Use appropriate temperature settings
   - Monitor token usage and costs

4. **Testing**:
   - Use mock LLM for all tests
   - Test fallback scenarios
   - Verify error handling

## LLM Usage in Deal Analysis

The AI Agentic Deals System leverages LLMs for critical aspects of deal analysis and scoring. This section outlines how LLMs are integrated into the deal evaluation process.

### Base Score Generation

LLMs play a central role in generating the initial base score for deals:

```python
# Example LLM prompt for base score generation
DEAL_SCORING_PROMPT = """
Analyze the following product deal and assign a base score from 0-100:

Product: {product_name}
Current Price: {current_price}
Original Price: {original_price}
Marketplace: {marketplace}
Category: {category}
Description: {description}

Consider the following factors:
1. Price competitiveness
2. Product quality and features
3. Value for money
4. Typical pricing for this category

Provide your analysis and a final score between 0-100.
"""

# Processing LLM response
response = llm_client.generate(DEAL_SCORING_PROMPT.format(**deal_data))
base_score = extract_score_from_response(response)
```

### Error Handling for Deal Analysis

When using LLMs for deal analysis, robust error handling is essential:

```python
def get_deal_base_score(deal_data):
    try:
        # Try primary model first
        response = primary_llm.generate(DEAL_SCORING_PROMPT.format(**deal_data))
        return extract_score_from_response(response)
    except PrimaryModelError:
        try:
            # Fall back to secondary model
            response = fallback_llm.generate(DEAL_SCORING_PROMPT.format(**deal_data))
            return extract_score_from_response(response)
        except FallbackModelError:
            # Use heuristic scoring as last resort
            logger.warning("All LLM models failed, using heuristic scoring")
            return calculate_heuristic_score(deal_data)
```

### Caching Strategy for LLM Responses

To optimize performance and reduce costs, LLM responses for deal analysis are cached:

```python
# Cache configuration for LLM responses
LLM_CACHE_CONFIG = {
    "deal_base_score": {
        "ttl": 86400,  # 24 hours
        "key_pattern": "llm:score:{deal_id}"
    },
    "deal_analysis": {
        "ttl": 43200,  # 12 hours
        "key_pattern": "llm:analysis:{deal_id}"
    }
}
```

### Model Selection for Different Analysis Types

Different types of deal analysis may use different LLM models based on requirements:

| Analysis Type | Primary Model | Fallback Model | Considerations |
|---------------|---------------|----------------|----------------|
| Base Scoring | DeepSeek R1 | GPT-4 | Requires numerical output |
| Deal Description | DeepSeek R1 | GPT-4 | Requires natural language |
| Trend Analysis | DeepSeek R1 | GPT-4 | Requires reasoning |
| Comparative Analysis | DeepSeek R1 | GPT-4 | Requires market knowledge |

### Performance Requirements

LLM performance for deal analysis must meet these requirements:

- Response time: < 1 second for base scoring
- Accuracy: > 90% agreement with human evaluators
- Consistency: < 5% variation in scores for identical deals
- Cost efficiency: < $0.01 per deal analysis

## Monitoring and Maintenance

### Metrics to Track
- Response times
- Error rates
- Token usage
- Cost per request
- Fallback frequency

### Regular Tasks
1. Review and update API keys
2. Monitor model performance
3. Adjust configuration parameters
4. Update model versions
5. Review error logs

## Troubleshooting

### Common Issues
1. **API Key Errors**:
   - Verify key is set in environment
   - Check key permissions
   - Ensure key is valid

2. **Model Unavailability**:
   - Check service status
   - Verify network connectivity
   - Confirm rate limits

3. **Performance Issues**:
   - Review temperature settings
   - Check token limits
   - Monitor response times 