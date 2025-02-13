"""Agent system configuration.

This module contains all configuration settings for the agent system,
including LLM settings, processing limits, and performance thresholds.
"""

from typing import Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

class PriorityLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class LLMProvider(str, Enum):
    GEMINI = "gemini"  # Development only
    DEEPSEEK = "deepseek"  # Primary
    OPENAI = "openai"  # Fallback

class PriorityConfig(BaseModel):
    """Configuration for priority levels"""
    timeout: int
    max_retries: int
    batch_size: int = Field(default=20)

class LLMConfig(BaseModel):
    """LLM provider configuration"""
    provider: LLMProvider
    model: str
    api_key: str
    temperature: float = Field(default=0.7)
    max_tokens: int = Field(default=4096)
    is_development: bool = Field(default=False)

# Priority level configurations
PRIORITY_CONFIGS: Dict[PriorityLevel, PriorityConfig] = {
    PriorityLevel.HIGH: PriorityConfig(
        timeout=5,
        max_retries=2,
        batch_size=10
    ),
    PriorityLevel.MEDIUM: PriorityConfig(
        timeout=15,
        max_retries=1,
        batch_size=20
    ),
    PriorityLevel.LOW: PriorityConfig(
        timeout=30,
        max_retries=0,
        batch_size=50
    )
}

# LLM configurations
LLM_CONFIGS: Dict[LLMProvider, LLMConfig] = {
    LLMProvider.GEMINI: LLMConfig(
        provider=LLMProvider.GEMINI,
        model="gemini-2.0-flash",
        api_key="AIzaSyDfOgCtxPOg5ZzwIob6hTDtN7aFtpsiIGQ",
        is_development=True
    ),
    LLMProvider.DEEPSEEK: LLMConfig(
        provider=LLMProvider.DEEPSEEK,
        model="deepseek-chat",
        api_key="${DEEPSEEK_API_KEY}"
    ),
    LLMProvider.OPENAI: LLMConfig(
        provider=LLMProvider.OPENAI,
        model="gpt-4-turbo",
        api_key="${OPENAI_API_KEY}"
    )
}

# Processing configurations
PROCESSING_CONFIG = {
    "max_concurrent_tasks": 100,
    "default_batch_size": 20,
    "queue_timeout": 60,  # seconds
    "max_queue_size": 10000,
    "processing_interval": 1  # seconds
}

# Cache configurations
CACHE_CONFIG = {
    "llm_responses": {
        "ttl": 3600,  # 1 hour
        "max_size": 10000
    },
    "market_data": {
        "ttl": 300,  # 5 minutes
        "max_size": 50000
    },
    "user_context": {
        "ttl": 1800,  # 30 minutes
        "max_size": 5000
    }
}

# Scaling configurations
SCALING_CONFIG = {
    "min_instances": 3,
    "max_instances": 10,
    "scale_up_threshold": 0.7,  # CPU utilization
    "scale_down_threshold": 0.3,
    "cooldown_period": 300  # seconds
}

# Performance thresholds
PERFORMANCE_THRESHOLDS = {
    "instant_response_time": 0.5,  # seconds
    "max_processing_time": 30,  # seconds
    "min_cache_hit_ratio": 0.8,
    "max_error_rate": 0.01,
    "max_memory_usage": 512  # MB per agent
}

# Rate limiting
RATE_LIMITS = {
    "user_requests_per_minute": 60,
    "ip_requests_per_minute": 100,
    "llm_requests_per_minute": 50
} 