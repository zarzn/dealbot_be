"""Test markers utility."""

import pytest
from functools import wraps
from typing import List, Optional, Callable
from .state import state_manager

def depends_on(*features: str):
    """Decorator to mark test dependencies."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for feature in features:
                if not state_manager.verify_dependencies(feature):
                    failed_deps = state_manager.get_failed_dependencies(feature)
                    pytest.skip(f"Dependencies not met for {feature}: {', '.join(failed_deps)}")
                    return
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# Core level markers
core = pytest.mark.core
db_models = pytest.mark.db_models
auth_core = pytest.mark.auth_core
redis_core = pytest.mark.redis_core

# Service level markers
service = pytest.mark.service
user_service = pytest.mark.user_service
goal_service = pytest.mark.goal_service
deal_service = pytest.mark.deal_service
token_service = pytest.mark.token_service
market_service = pytest.mark.market_service

# Feature level markers
feature = pytest.mark.feature
goals = pytest.mark.goals
deals = pytest.mark.deals
agents = pytest.mark.agents

# Integration level markers
integration = pytest.mark.integration
api = pytest.mark.api
websocket = pytest.mark.websocket
workflows = pytest.mark.workflows

# Additional markers
slow = pytest.mark.slow
flaky = pytest.mark.flaky
dependency = pytest.mark.dependency

def register_markers(config):
    """Register all markers to prevent warnings."""
    markers = [
        # Core
        'core: Core functionality tests',
        'db_models: Database model tests',
        'auth_core: Authentication core tests',
        'redis_core: Redis core tests',
        
        # Services
        'service: Service layer tests',
        'user_service: User service tests',
        'goal_service: Goal service tests',
        'deal_service: Deal service tests',
        'token_service: Token service tests',
        'market_service: Market service tests',
        
        # Features
        'feature: Feature tests',
        'goals: Goal feature tests',
        'deals: Deal feature tests',
        'agents: Agent feature tests',
        
        # Integration
        'integration: Integration tests',
        'api: API tests',
        'websocket: WebSocket tests',
        'workflows: Full workflow tests',
        
        # Additional
        'slow: Tests that take longer to run',
        'flaky: Tests that might be unstable',
        'dependency: Tests with dependencies'
    ]
    
    for marker in markers:
        config.addinivalue_line('markers', marker) 