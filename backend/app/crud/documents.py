from collections.abc import Iterable

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.db.models import Document, DocumentElement


class CRUDDocument(CRUDBase[Document]):
    async def list_by_knowledge_base(
        self, session: AsyncSession, knowledge_base_id: str
    ) -> list[Document]:
        result = await session.execute(
            select(Document)
            .where(Document.knowledge_base_id == knowledge_base_id)
            .order_by(Document.created_at.desc())
        )
        return list(result.scalars())

    async def get_filenames(self, session: AsyncSession, document_ids: set[str]) -> dict[str, str]:
        if not document_ids:
            return {}
        result = await session.execute(
            select(Document.id, Document.filename).where(Document.id.in_(document_ids))
        )
        return dict(result.all())


class CRUDDocumentElement(CRUDBase[DocumentElement]):
    async def get_image(
        self, session: AsyncSession, document_id: str, sequence_no: int
    ) -> DocumentElement | None:
        result = await session.execute(
            select(DocumentElement).where(
                DocumentElement.document_id == document_id,
                DocumentElement.sequence_no == sequence_no,
                DocumentElement.kind == "image",
            )
        )
        return result.scalar_one_or_none()

    async def list_image_keys(
        self, session: AsyncSession, document_ids: set[str]
    ) -> set[tuple[str, int]]:
        if not document_ids:
            return set()
        result = await session.execute(
            select(DocumentElement.document_id, DocumentElement.sequence_no).where(
                DocumentElement.document_id.in_(document_ids),
                DocumentElement.kind == "image",
                DocumentElement.image_path.is_not(None),
            )
        )
        return set(result.tuples().all())

    async def get_nearest_image(
        self, session: AsyncSession, document_id: str, sequence_no: int
    ) -> DocumentElement | None:
        result = await session.execute(
            select(DocumentElement)
            .where(
                DocumentElement.document_id == document_id,
                DocumentElement.kind == "image",
                DocumentElement.image_path.is_not(None),
            )
            .order_by(func.abs(DocumentElement.sequence_no - sequence_no))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def replace_for_document(
        self,
        session: AsyncSession,
        document_id: str,
        elements: Iterable[DocumentElement],
    ) -> None:
        await session.execute(
            delete(DocumentElement).where(DocumentElement.document_id == document_id)
        )
        session.add_all(list(elements))
        await session.flush()


documents = CRUDDocument(Document)
document_elements = CRUDDocumentElement(DocumentElement)
