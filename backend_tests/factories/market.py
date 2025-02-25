from typing import Optional
from factory import Faker, LazyFunction, Sequence
from uuid import uuid4
from .base import BaseFactory
from core.models.market import Market
from core.models.enums import MarketType, MarketStatus
from sqlalchemy.ext.asyncio import AsyncSession

class MarketFactory(BaseFactory):
    class Meta:
        model = Market
    
    id = LazyFunction(uuid4)
    name = LazyFunction(lambda: f"Test Market {MarketFactory._get_next_sequence()}")
    type = MarketType.TEST
    api_endpoint = "https://api.test.com"
    api_key = LazyFunction(lambda: str(uuid4()))
    status = MarketStatus.ACTIVE
    rate_limit = 100
    is_active = True
    error_count = 0
    requests_today = 0
    total_requests = 0
    success_rate = 1.0
    avg_response_time = 0.0
    config = {
        'headers': {
            'Authorization': 'Bearer test_token',
            'User-Agent': 'Test Agent'
        },
        'params': {
            'retries': 3,
            'timeout': 30
        }
    }

    @classmethod
    def _get_defaults(cls) -> dict:
        """Get the default values for the factory."""
        return {
            'id': cls.id.evaluate(None, None, {}),
            'name': cls.name.evaluate(None, None, {}),
            'type': cls.type.value.lower() if isinstance(cls.type, MarketType) else cls.type,
            'status': cls.status.value.lower() if isinstance(cls.status, MarketStatus) else cls.status,
            'rate_limit': cls.rate_limit,
            'is_active': cls.is_active,
            'error_count': cls.error_count,
            'requests_today': cls.requests_today,
            'total_requests': cls.total_requests,
            'success_rate': cls.success_rate,
            'avg_response_time': cls.avg_response_time,
            'config': cls.config
        }

    @classmethod
    async def create_async(cls, db_session: AsyncSession, **kwargs) -> Market:
        """Create a new market instance with proper defaults."""
        defaults = cls._get_defaults()
        
        # Handle enum values in kwargs
        if 'type' in kwargs and isinstance(kwargs['type'], MarketType):
            kwargs['type'] = kwargs['type'].value.lower()
        if 'status' in kwargs and isinstance(kwargs['status'], MarketStatus):
            kwargs['status'] = kwargs['status'].value.lower()
            
        defaults.update(kwargs)
        return await super().create_async(db_session=db_session, **defaults)

    @classmethod
    def _get_next_sequence(cls) -> int:
        if not hasattr(cls, '_sequence'):
            cls._sequence = 0
        cls._sequence += 1
        return cls._sequence
