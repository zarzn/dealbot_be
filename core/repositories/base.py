from typing import Any, Generic, TypeVar
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from core.exceptions import DatabaseError

T = TypeVar('T')

class BaseRepository(Generic[T]):
    """Base repository class providing common CRUD operations"""
    
    def __init__(self, db: AsyncSession):
        self.db = db

    async def commit(self) -> None:
        """Commit the current transaction"""
        try:
            await self.db.commit()
        except SQLAlchemyError as e:
            await self.db.rollback()
            raise DatabaseError("Database operation failed") from e

    async def refresh(self, entity: T) -> None:
        """Refresh the state of an entity"""
        try:
            await self.db.refresh(entity)
        except SQLAlchemyError as e:
            raise DatabaseError("Failed to refresh entity") from e

    async def execute(self, statement: Any) -> Any:
        """Execute a SQLAlchemy statement"""
        try:
            return await self.db.execute(statement)
        except SQLAlchemyError as e:
            raise DatabaseError("Failed to execute statement") from e
