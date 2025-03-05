# LLM Configuration

This document details the configuration settings for the Language Learning Models (LLMs) used in the AI Agentic Deals System.

## Overview

The AI Agentic Deals System uses multiple LLM providers with a primary/fallback strategy to ensure reliability and optimal performance. The system is designed to be model-agnostic, allowing different LLMs to be plugged in based on availability, performance, and cost considerations.

## LLM Provider Configuration

### Primary Provider: DeepSeek R1

DeepSeek R1 is the primary LLM used in the production environment.

#### Configuration

```python
# DeepSeek Configuration
DEEPSEEK_CONFIG = {
    "api_key": os.getenv("DEEPSEEK_API_KEY"),
    "model": "deepseek-chat",  # or other appropriate model name
    "temperature": 0.7,
    "max_tokens": 4000,
    "top_p": 0.95,
    "frequency_penalty": 0.0,
    "presence_penalty": 0.0,
    "timeout": 60,
    "retry_count": 3,
    "stream": False,
}
```

#### Request Format

```python
request_data = {
    "model": DEEPSEEK_CONFIG["model"],
    "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ],
    "temperature": DEEPSEEK_CONFIG["temperature"],
    "max_tokens": DEEPSEEK_CONFIG["max_tokens"],
    "top_p": DEEPSEEK_CONFIG["top_p"],
    "frequency_penalty": DEEPSEEK_CONFIG["frequency_penalty"],
    "presence_penalty": DEEPSEEK_CONFIG["presence_penalty"],
    "stream": DEEPSEEK_CONFIG["stream"],
}
```

#### Response Format

```python
{
    "id": "chat-Xxxxxxxxxxxxxxxxxxxxxxxx",
    "object": "chat.completion",
    "created": 1698721635,
    "model": "deepseek-chat",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "This is the response content from DeepSeek."
            },
            "finish_reason": "stop"
        }
    ],
    "usage": {
        "prompt_tokens": 57,
        "completion_tokens": 154,
        "total_tokens": 211
    }
}
```

### Fallback Provider: OpenAI GPT-4

GPT-4 is used as a fallback when the primary provider is unavailable or unsuitable for specific tasks.

#### Configuration

```python
# OpenAI Configuration
OPENAI_CONFIG = {
    "api_key": os.getenv("OPENAI_API_KEY"),
    "model": "gpt-4",  # or "gpt-4-turbo" based on requirements
    "temperature": 0.7,
    "max_tokens": 4000,
    "top_p": 0.95,
    "frequency_penalty": 0.0,
    "presence_penalty": 0.0,
    "timeout": 60,
    "retry_count": 3,
    "stream": False,
}
```

#### Request Format

```python
request_data = {
    "model": OPENAI_CONFIG["model"],
    "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ],
    "temperature": OPENAI_CONFIG["temperature"],
    "max_tokens": OPENAI_CONFIG["max_tokens"],
    "top_p": OPENAI_CONFIG["top_p"],
    "frequency_penalty": OPENAI_CONFIG["frequency_penalty"],
    "presence_penalty": OPENAI_CONFIG["presence_penalty"],
    "stream": OPENAI_CONFIG["stream"],
}
```

#### Response Format

```python
{
    "id": "chatcmpl-Xxxxxxxxxxxxxxxxxxxxxxxx",
    "object": "chat.completion",
    "created": 1698721635,
    "model": "gpt-4",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "This is the response content from GPT-4."
            },
            "finish_reason": "stop"
        }
    ],
    "usage": {
        "prompt_tokens": 57,
        "completion_tokens": 154,
        "total_tokens": 211
    }
}
```

## LLM Service Implementation

The system uses a unified `LLMService` that abstracts provider-specific details:

```python
class LLMService:
    """Service for interacting with Language Learning Models."""
    
    def __init__(self, primary_config: Dict = None, fallback_config: Dict = None):
        # Use provided configs or load from environment
        self.primary_config = primary_config or self._load_primary_config()
        self.fallback_config = fallback_config or self._load_fallback_config()
        
        # Initialize HTTP client
        self.client = httpx.AsyncClient(timeout=60.0)
        
        # Token calculator
        self.token_calculator = TokenCalculator()
    
    def _load_primary_config(self) -> Dict:
        """Load primary LLM configuration."""
        if os.getenv("DEEPSEEK_API_KEY"):
            return {
                "provider": "deepseek",
                "api_key": os.getenv("DEEPSEEK_API_KEY"),
                "model": "deepseek-chat",
                "temperature": 0.7,
                "max_tokens": 4000,
                "api_url": "https://api.deepseek.com/v1/chat/completions",
            }
        return None
    
    def _load_fallback_config(self) -> Dict:
        """Load fallback LLM configuration."""
        if os.getenv("OPENAI_API_KEY"):
            return {
                "provider": "openai",
                "api_key": os.getenv("OPENAI_API_KEY"),
                "model": "gpt-4",
                "temperature": 0.7,
                "max_tokens": 4000,
                "api_url": "https://api.openai.com/v1/chat/completions",
            }
        return None
    
    async def generate_response(
        self, 
        messages: List[Dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        use_fallback: bool = False
    ) -> Dict:
        """Generate a response from the LLM."""
        # Determine which config to use
        config = self.fallback_config if use_fallback else self.primary_config
        
        # If primary is not available and not explicitly using fallback,
        # fall back to the fallback provider
        if config is None:
            if use_fallback or self.fallback_config is None:
                raise ValueError("No LLM configuration available")
            config = self.fallback_config
        
        # Prepare the request
        request_data = {
            "model": config["model"],
            "messages": messages,
            "temperature": temperature or config.get("temperature", 0.7),
            "max_tokens": max_tokens or config.get("max_tokens", 1000),
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config['api_key']}"
        }
        
        try:
            # Make the API request
            response = await self.client.post(
                config["api_url"],
                json=request_data,
                headers=headers
            )
            response.raise_for_status()
            result = response.json()
            
            # Extract and return the response
            return {
                "text": result["choices"][0]["message"]["content"],
                "usage": result.get("usage", {})
            }
        except Exception as e:
            # If using primary and it fails, try fallback
            if not use_fallback and self.fallback_config is not None:
                logger.warning(f"Primary LLM failed: {str(e)}. Trying fallback.")
                return await self.generate_response(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    use_fallback=True
                )
            # If already using fallback or no fallback available, raise the error
            raise LLMServiceError(f"LLM service error: {str(e)}")
```

## Environment-Specific LLM Strategy

### Production Environment

- **Primary Model**: DeepSeek R1
  - Used for all standard operations
  - Optimized for production workloads
  - Configured with higher token limits

- **Fallback Model**: GPT-4
  - Used when DeepSeek is unavailable
  - Used for specific complex reasoning tasks
  - Configured for high-quality outputs

### Development Environment

- **Primary Model**: DeepSeek R1 (with development settings)
  - Lower token limits to reduce costs
  - Higher temperature for more creative responses
  - Faster response times prioritized

- **Fallback Model**: GPT-4 (optional)
  - Used for testing fallback scenarios
  - Used for developing prompts

### Test Environment

- **Model**: Mock LLM
  - Used for automated testing
  - Returns predetermined responses
  - No API keys required
  - Fast and consistent for tests

```python
class MockLLM:
    """Mock LLM for testing purposes."""
    
    def __init__(self, responses: Dict[str, str] = None):
        self.responses = responses or {}
        self.default_response = "This is a mock response from the LLM."
        self.calls = []
    
    async def generate_response(
        self, 
        messages: List[Dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Dict:
        """Generate a mock response."""
        # Record the call for assertions in tests
        self.calls.append({
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        })
        
        # Find a matching response or use default
        prompt = messages[-1]["content"] if messages else ""
        response = self.responses.get(prompt, self.default_response)
        
        return {
            "text": response,
            "usage": {
                "prompt_tokens": len(prompt) // 4,
                "completion_tokens": len(response) // 4,
                "total_tokens": (len(prompt) + len(response)) // 4
            }
        }
```

## Provider-Specific Settings

### DeepSeek-Specific Settings

```python
DEEPSEEK_SPECIFIC = {
    "max_parallel_requests": 10,
    "timeout_multiplier": 1.5,  # Longer timeout for complex requests
    "retry_status_codes": [429, 500, 502, 503, 504],
    "specific_models": {
        "reasoning": "deepseek-coder",
        "creative": "deepseek-chat",
        "analysis": "deepseek-chat"
    }
}
```

### OpenAI-Specific Settings

```python
OPENAI_SPECIFIC = {
    "max_parallel_requests": 5,
    "timeout_multiplier": 1.2,
    "retry_status_codes": [429, 500, 502, 503, 504],
    "specific_models": {
        "reasoning": "gpt-4",
        "creative": "gpt-4",
        "analysis": "gpt-4-turbo"
    }
}
```

## Task-Specific LLM Settings

Different tasks may require different LLM configurations:

### Market Analysis

```python
MARKET_ANALYSIS_CONFIG = {
    "temperature": 0.3,  # Lower temperature for more factual responses
    "max_tokens": 2000,
    "system_prompt": "You are a market analysis expert. Analyze the provided data and give factual insights."
}
```

### Creative Deal Generation

```python
DEAL_GENERATION_CONFIG = {
    "temperature": 0.8,  # Higher temperature for more creative responses
    "max_tokens": 1500,
    "system_prompt": "You are a creative deal finder. Generate innovative deal ideas based on the provided criteria."
}
```

### Complex Reasoning

```python
COMPLEX_REASONING_CONFIG = {
    "temperature": 0.2,  # Very low temperature for logical reasoning
    "max_tokens": 4000,  # Higher token limit for complex reasoning chains
    "system_prompt": "You are a logical reasoning expert. Break down complex problems step by step."
}
```

## Token Management

The system implements token management to control costs and ensure fair usage:

```python
class TokenManager:
    """Manages token usage for LLM calls."""
    
    def __init__(self, redis_client, user_service):
        self.redis = redis_client
        self.user_service = user_service
    
    async def check_token_availability(self, user_id: str, estimated_tokens: int) -> bool:
        """Check if user has enough tokens available."""
        balance = await self.user_service.get_token_balance(user_id)
        return balance >= estimated_tokens
    
    async def reserve_tokens(self, user_id: str, estimated_tokens: int) -> str:
        """Reserve tokens for an operation and return a reservation ID."""
        if not await self.check_token_availability(user_id, estimated_tokens):
            raise InsufficientTokensError("Not enough tokens available")
        
        reservation_id = str(uuid.uuid4())
        await self.redis.set(
            f"token:reservation:{reservation_id}",
            json.dumps({
                "user_id": user_id,
                "tokens": estimated_tokens,
                "timestamp": time.time()
            }),
            ex=3600  # Expire after 1 hour if not used
        )
        return reservation_id
    
    async def consume_tokens(self, reservation_id: str, actual_tokens: int) -> None:
        """Consume tokens based on actual usage."""
        reservation_data = await self.redis.get(f"token:reservation:{reservation_id}")
        if not reservation_data:
            raise ReservationNotFoundError("Token reservation not found")
        
        data = json.loads(reservation_data)
        user_id = data["user_id"]
        
        # Deduct tokens from user's balance
        await self.user_service.deduct_tokens(user_id, actual_tokens)
        
        # Delete the reservation
        await self.redis.delete(f"token:reservation:{reservation_id}")
```

## Error Handling

The system implements robust error handling for LLM interactions:

```python
class LLMServiceError(Exception):
    """Base exception for LLM service errors."""
    pass

class LLMProviderError(LLMServiceError):
    """Exception for provider-specific errors."""
    pass

class LLMRateLimitError(LLMProviderError):
    """Exception for rate limit errors."""
    pass

class LLMContextLengthError(LLMProviderError):
    """Exception for context length exceeded errors."""
    pass

class LLMAuthenticationError(LLMProviderError):
    """Exception for authentication errors."""
    pass

class LLMResponseError(LLMServiceError):
    """Exception for invalid response formats."""
    pass
```

## LLM Request Logging

The system logs LLM requests for monitoring and debugging:

```python
async def log_llm_request(
    user_id: str,
    request_type: str,
    prompt_tokens: int,
    completion_tokens: int,
    provider: str,
    model: str,
    success: bool,
    error: Optional[str] = None,
    duration_ms: int = 0
) -> None:
    """Log LLM request to database."""
    log_entry = LLMRequestLog(
        user_id=user_id,
        request_type=request_type,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        provider=provider,
        model=model,
        success=success,
        error=error,
        duration_ms=duration_ms,
        timestamp=datetime.utcnow()
    )
    async with get_db_session() as session:
        session.add(log_entry)
        await session.commit() 