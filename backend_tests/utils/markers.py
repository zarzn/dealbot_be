"""Test markers module."""

from functools import wraps
from typing import Callable, Set, TypeVar, cast
import pytest
from .state import state_manager, TestLevel

F = TypeVar('F', bound=Callable)

def register_marker(name: str, description: str) -> None:
    """Register a marker with pytest."""
    if not hasattr(pytest.mark, name):
        pytest.mark.register(name, description)

# Register test level markers
register_marker('core', 'Core functionality tests')
register_marker('service', 'Service level tests')
register_marker('feature', 'Feature level tests')
register_marker('integration', 'Integration tests')

def core_test(func: F) -> F:
    """Mark test as core test."""
    func = pytest.mark.core(func)
    test_name = f"{func.__module__}.{func.__name__}"
    state_manager.register_test(test_name, TestLevel.CORE)
    return cast(F, func)

def service_test(func: F) -> F:
    """Mark test as service test."""
    func = pytest.mark.service(func)
    test_name = f"{func.__module__}.{func.__name__}"
    state_manager.register_test(test_name, TestLevel.SERVICE)
    return cast(F, func)

def feature_test(func: F) -> F:
    """Mark test as feature test."""
    func = pytest.mark.feature(func)
    test_name = f"{func.__module__}.{func.__name__}"
    state_manager.register_test(test_name, TestLevel.FEATURE)
    return cast(F, func)

def integration_test(func: F) -> F:
    """Mark test as integration test."""
    func = pytest.mark.integration(func)
    test_name = f"{func.__module__}.{func.__name__}"
    state_manager.register_test(test_name, TestLevel.INTEGRATION)
    return cast(F, func)

def depends_on(*test_names: str) -> Callable[[F], F]:
    """Decorator to specify test dependencies."""
    def decorator(func: F) -> F:
        test_name = f"{func.__module__}.{func.__name__}"
        dependencies = set(test_names)
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not state_manager.can_run(test_name):
                pytest.skip(f"Dependencies not met: {', '.join(dependencies)}")
            
            try:
                result = await func(*args, **kwargs)
                state_manager.mark_success(test_name)
                return result
            except Exception as e:
                state_manager.mark_failure(test_name)
                raise
                
        return cast(F, wrapper)
    return decorator 