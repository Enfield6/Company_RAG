from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.db.models import IngestionJob


class CRUDIngestionJob(CRUDBase[IngestionJob]):
    async def get_latest(self, session: AsyncSession, document_id: str) -> IngestionJob | None:
        result = await session.execute(
            select(IngestionJob)
            .where(IngestionJob.document_id == document_id)
            .order_by(IngestionJob.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


ingestion_jobs = CRUDIngestionJob(IngestionJob)
