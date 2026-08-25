from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.crud.knowledge_bases import knowledge_bases
from app.db.models import KnowledgeBase
from app.services.errors import ResourceNotFoundError


@dataclass(frozen=True, slots=True)
class KnowledgeBaseSummary:
    knowledge_base: KnowledgeBase
    document_count: int


class KnowledgeBaseService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def create(self, name: str, description: str | None) -> KnowledgeBase:
        knowledge_base = await knowledge_bases.create(
            self.session,
            name=name.strip(),
            description=description,
            embedding_model=self.settings.embedding_model,
            embedding_dimension=self.settings.embedding_dimension,
        )
        await self.session.commit()
        await self.session.refresh(knowledge_base)
        return knowledge_base

    async def list(self) -> list[KnowledgeBaseSummary]:
        records = await knowledge_bases.list_with_document_count(self.session)
        return [
            KnowledgeBaseSummary(record.knowledge_base, record.document_count) for record in records
        ]

    async def get(self, knowledge_base_id: str) -> KnowledgeBaseSummary:
        record = await knowledge_bases.get_with_document_count(self.session, knowledge_base_id)
        if record is None:
            raise ResourceNotFoundError("知识库不存在")
        return KnowledgeBaseSummary(record.knowledge_base, record.document_count)
