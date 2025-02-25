"""Base factory for test data generation."""

from typing import Any, Dict, List, Optional, Type, TypeVar
from factory import Factory, Faker
from factory.declarations import LazyAttribute
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar('T')

class BaseFactory(Factory):
    """Base factory with common functionality."""
    
    class Meta:
        abstract = True

    @classmethod
    async def create_async(cls, **kwargs) -> T:
        """Create an instance asynchronously."""
        instance = cls.build(**kwargs)
        if hasattr(instance, 'save'):
            await instance.save()
        return instance

    @classmethod
    async def create_batch_async(cls, size: int, **kwargs) -> List[T]:
        """Create multiple instances asynchronously."""
        return [await cls.create_async(**kwargs) for _ in range(size)]

    @classmethod
    async def create_with_dependencies(cls, session: AsyncSession, **kwargs) -> T:
        """Create an instance with all required dependencies."""
        deps = await cls._create_dependencies(session, **kwargs)
        return await cls.create_async(**{**deps, **kwargs})

    @classmethod
    async def _create_dependencies(cls, session: AsyncSession, **kwargs) -> Dict[str, Any]:
        """Create dependencies for the factory.
        
        Override this method in subclasses to create required dependencies.
        """
        return {}

    @classmethod
    def get_test_password(cls) -> str:
        """Get a consistent test password."""
        return "TestPassword123!"

    @classmethod
    def get_test_email(cls) -> str:
        """Get a unique test email."""
        return Faker('email').generate({})

    @classmethod
    async def cleanup(cls, session: AsyncSession):
        """Clean up factory-created data."""
        pass  # Override in subclasses if needed 