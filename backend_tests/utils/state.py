from typing import Dict, Set, Optional
from enum import Enum, auto

class TestLevel(Enum):
    """Test levels in order of dependency."""
    CORE = auto()
    SERVICE = auto()
    FEATURE = auto()
    INTEGRATION = auto()

class TestState:
    """Manages test state and dependencies."""
    
    def __init__(self):
        self._state: Dict[str, bool] = {}
        self._dependencies: Dict[str, Set[str]] = {}
        self._level_map: Dict[str, TestLevel] = {}
    
    def register_test(self, test_name: str, level: TestLevel, dependencies: Optional[Set[str]] = None) -> None:
        """Register a test with its level and dependencies."""
        self._state[test_name] = False
        self._level_map[test_name] = level
        if dependencies:
            self._dependencies[test_name] = dependencies
    
    def mark_success(self, test_name: str) -> None:
        """Mark a test as successful."""
        self._state[test_name] = True
    
    def mark_failure(self, test_name: str) -> None:
        """Mark a test as failed."""
        self._state[test_name] = False
    
    def can_run(self, test_name: str) -> bool:
        """Check if a test can be run based on its dependencies."""
        if test_name not in self._dependencies:
            return True
        
        return all(self._state.get(dep, False) for dep in self._dependencies[test_name])
    
    def get_level(self, test_name: str) -> TestLevel:
        """Get the level of a test."""
        return self._level_map.get(test_name, TestLevel.CORE)
    
    def reset(self) -> None:
        """Reset all test states."""
        self._state.clear()

# Global state manager instance
state_manager = TestState() 