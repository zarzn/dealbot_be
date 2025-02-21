from enum import Enum
from typing import List

class GoalType(str, Enum):
    DEAL_FINDING = "deal_finding"
    PRICE_TRACKING = "price_tracking"
    MARKET_ANALYSIS = "market_analysis"
    BRAND_MONITORING = "brand_monitoring"
    CUSTOM = "custom"
    
    @classmethod
    def list(cls) -> List[str]:
        return [goal_type.value for goal_type in cls]

class GoalStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    ERROR = "error"
    
    @classmethod
    def list(cls) -> List[str]:
        return [status.value for status in cls]

class GoalPriority(int, Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5
    
    @classmethod
    def list(cls) -> List[int]:
        return [priority.value for priority in cls] 