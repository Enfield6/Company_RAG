from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.db.models import Document, KnowledgeBase


@dataclass(frozen=True, slots=True)
class KnowledgeBaseWithDocumentCount:
    knowledge_base: KnowledgeBase
    document_count: int


class CRUDKnowledgeBase(CRUDBase[KnowledgeBase]):
    async def list_with_document_count(
        self, session: AsyncSession
    ) -> list[KnowledgeBaseWithDocumentCount]:
        result = await session.execute(
            select(KnowledgeBase, func.count(Document.id).label("document_count"))
            .outerjoin(Document)
            .group_by(KnowledgeBase.id)
            .order_by(KnowledgeBase.updated_at.desc())
        )
        return [KnowledgeBaseWithDocumentCount(item, int(count)) for item, count in result.all()]

    async def get_with_document_count(
        self, session: AsyncSession, knowledge_base_id: str
    ) -> KnowledgeBaseWithDocumentCount | None:
        result = await session.execute(
            select(KnowledgeBase, func.count(Document.id).label("document_count"))
            .outerjoin(Document)
            .where(KnowledgeBase.id == knowledge_base_id)
            .group_by(KnowledgeBase.id)
        )
        row = result.one_or_none()
        if row is None:
            return None
        item, count = row
        return KnowledgeBaseWithDocumentCount(item, int(count))


knowledge_bases = CRUDKnowledgeBase(KnowledgeBase)
