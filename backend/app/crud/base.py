from typing import Any, Generic, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class CRUDBase(Generic[ModelT]):
    """Common primary-key reads and model construction without auto-commit."""

    def __init__(self, model: type[ModelT]) -> None:
        self.model = model

    async def get(self, session: AsyncSession, object_id: str) -> ModelT | None:
        return await session.get(self.model, object_id)

    async def create(self, session: AsyncSession, **values: Any) -> ModelT:
        instance = self.model(**values)
        session.add(instance)
        await session.flush()
        return instance
