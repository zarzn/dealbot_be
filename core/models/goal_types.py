from enum import Enum
from typing import List

class GoalStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    EXPIRED = "expired"
    
    @classmethod
    def list(cls) -> List[str]:
        return [status.value for status in cls] 