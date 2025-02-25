"""Test state management utility."""

from typing import Dict, List, Set, Optional
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

class TestState:
    """Represents the state of a test feature."""
    
    def __init__(self, name: str):
        self.name = name
        self.tests_pass = False
        self.dependencies_met = False
        self.last_run = None
        self.error_count = 0

class TestStateManager:
    """Manages test state and dependencies."""
    
    def __init__(self):
        self._state: Dict[str, TestState] = {}
        self._dependencies: Dict[str, List[str]] = {
            # Core Level (1)
            'db_models': [],
            'auth_core': ['db_models'],
            'redis_core': [],
            
            # Service Level (2)
            'user_service': ['auth_core', 'db_models'],
            'goal_service': ['user_service', 'db_models'],
            'deal_service': ['goal_service', 'market_service'],
            'token_service': ['user_service', 'redis_core'],
            'market_service': ['db_models'],
            
            # Feature Level (3)
            'goals': ['goal_service', 'user_service'],
            'deals': ['deal_service', 'goal_service'],
            'agents': ['deal_service', 'goal_service'],
            
            # Integration Level (4)
            'api': ['goals', 'deals', 'agents'],
            'websocket': ['api'],
            'workflows': ['api', 'websocket']
        }
        self._initialize_states()

    def _initialize_states(self):
        """Initialize states for all features."""
        for feature in self._dependencies.keys():
            self._state[feature] = TestState(feature)

    def register_dependency(self, feature: str, depends_on: List[str]):
        """Register feature dependencies."""
        self._dependencies[feature] = depends_on
        if feature not in self._state:
            self._state[feature] = TestState(feature)

    def verify_dependencies(self, feature: str) -> bool:
        """Verify all dependencies pass their tests."""
        if feature not in self._dependencies:
            return True
        
        for dep in self._dependencies[feature]:
            if not self._state.get(dep, TestState(dep)).tests_pass:
                return False
        return True

    def mark_test_passed(self, feature: str):
        """Mark a feature's tests as passed."""
        if feature in self._state:
            self._state[feature].tests_pass = True

    def mark_test_failed(self, feature: str):
        """Mark a feature's tests as failed."""
        if feature in self._state:
            state = self._state[feature]
            state.tests_pass = False
            state.error_count += 1

    def get_failed_dependencies(self, feature: str) -> List[str]:
        """Get list of failed dependencies for a feature."""
        failed = []
        if feature in self._dependencies:
            for dep in self._dependencies[feature]:
                if not self._state.get(dep, TestState(dep)).tests_pass:
                    failed.append(dep)
        return failed

    def reset_state(self, feature: str):
        """Reset state for a feature."""
        if feature in self._state:
            self._state[feature] = TestState(feature)

    def reset_all(self):
        """Reset all states."""
        self._initialize_states()

    def get_test_order(self) -> List[str]:
        """Get correct order of test execution."""
        visited: Set[str] = set()
        order: List[str] = []

        def visit(feature: str):
            if feature in visited:
                return
            visited.add(feature)
            for dep in self._dependencies.get(feature, []):
                visit(dep)
            order.append(feature)

        for feature in self._dependencies:
            visit(feature)
        return order

    async def run_with_dependencies(
        self,
        feature: str,
        session: AsyncSession,
        test_func: callable,
        cleanup_func: Optional[callable] = None
    ):
        """Run a test function with dependency checking."""
        if not self.verify_dependencies(feature):
            failed_deps = self.get_failed_dependencies(feature)
            pytest.skip(f"Dependencies not met: {', '.join(failed_deps)}")
            return

        try:
            await test_func(session)
            self.mark_test_passed(feature)
        except Exception as e:
            self.mark_test_failed(feature)
            if cleanup_func:
                await cleanup_func(session)
            raise e
        finally:
            if cleanup_func:
                await cleanup_func(session)

# Global state manager instance
state_manager = TestStateManager() 