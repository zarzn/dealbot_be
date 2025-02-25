"""Agent system configuration.

This module contains all configuration settings for the agent system,
including LLM settings, processing limits, and performance thresholds.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum
import os

from core.exceptions import ConfigurationError

class PriorityLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class LLMProvider(str, Enum):
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

class AgentConfig(BaseModel):
    """Configuration for an agent"""
    priority: PriorityLevel = Field(default=PriorityLevel.MEDIUM)
    llm_provider: LLMProvider = Field(default=LLMProvider.DEEPSEEK)
    max_retries: int = Field(default=3)
    timeout: int = Field(default=30)
    batch_size: int = Field(default=20)
    cache_ttl: int = Field(default=3600)
    memory_limit: int = Field(default=512)  # MB
    metadata: Optional[Dict[str, Any]] = None

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
def load_llm_configs() -> Dict[LLMProvider, LLMConfig]:
    """Load LLM configurations with environment variables."""
    configs = {
        LLMProvider.DEEPSEEK: LLMConfig(
            provider=LLMProvider.DEEPSEEK,
            model="deepseek-coder",
            api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            temperature=0.7,
            max_tokens=4096
        ),
        LLMProvider.OPENAI: LLMConfig(
            provider=LLMProvider.OPENAI,
            model="gpt-4",
            api_key=os.getenv("OPENAI_API_KEY", ""),
            temperature=0.7,
            max_tokens=4096
        )
    }
    
    # Validate required API keys
    for provider, config in configs.items():
        if not config.api_key:
            raise ConfigurationError(
                config_key=f"LLM_API_KEY_{provider.value.upper()}",
                message=f"Missing API key for provider: {provider}"
            )
    
    return configs

LLM_CONFIGS = load_llm_configs()

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
    "max_memory_usage": 512,  # MB per agent
    "cache_ttl": 3600  # 1 hour
}

# Rate limiting
RATE_LIMITS = {
    "user_requests_per_minute": 60,
    "ip_requests_per_minute": 100,
    "llm_requests_per_minute": 50
} 