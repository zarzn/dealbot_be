from typing import Any, Dict, Optional, TypeVar, Type
from factory import Factory as FactoryBoy, enums
from factory.base import FactoryOptions
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_session

T = TypeVar('T')

class BaseFactory(FactoryBoy):
    """Base factory class for all test factories."""
    
    class Meta:
        abstract = True
        strategy = enums.CREATE_STRATEGY
    
    @classmethod
    def _setup_next_sequence(cls) -> int:
        """Get the next sequence number."""
        return 1
    
    @classmethod
    def _create(cls, model_class: Type[T], *args: Any, **kwargs: Any) -> T:
        """Create an instance without saving it to the database."""
        return model_class(*args, **kwargs)
    
    @classmethod
    async def create_async(cls, db_session: AsyncSession = None, **kwargs: Any) -> T:
        """Create and save a new instance to the database."""
        if db_session is None:
            raise ValueError("db_session is required for create_async")
        
        instance = cls._create(cls._meta.model, **kwargs)
        db_session.add(instance)
        await db_session.commit()
        await db_session.refresh(instance)
        return instance
    
    @classmethod
    def build(cls, **kwargs: Any) -> T:
        """Build a new instance without saving it."""
        return cls._create(cls._meta.model, **kwargs)
    
    @staticmethod
    def get_test_password() -> str:
        """Get a standard test password."""
        return "TestPassword123!"
    
    @classmethod
    async def cleanup_created_instances(cls, db_session: AsyncSession) -> None:
        """Clean up all instances created by this factory."""
        await db_session.execute(
            f"DELETE FROM {cls._meta.model.__tablename__}"
        )
        await db_session.commit() 