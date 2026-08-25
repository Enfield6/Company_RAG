import hashlib
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.crud.documents import document_elements, documents
from app.crud.ingestion_jobs import ingestion_jobs
from app.crud.knowledge_bases import knowledge_bases
from app.db.models import Document, IngestionJob
from app.documents.registry import (
    SUPPORTED_DOCUMENT_TYPES,
    content_type_for,
    supported_extensions_label,
)
from app.services.errors import (
    ConflictError,
    InvalidInputError,
    PayloadTooLargeError,
    ResourceNotFoundError,
    UnsupportedMediaTypeError,
)
from app.services.storage import LocalFileStorage


@dataclass(frozen=True, slots=True)
class AcceptedDocumentUpload:
    document: Document
    job: IngestionJob


class DocumentService:
    def __init__(
        self, session: AsyncSession, settings: Settings, storage: LocalFileStorage
    ) -> None:
        self.session = session
        self.settings = settings
        self.storage = storage

    @property
    def upload_read_limit(self) -> int:
        """Read one extra byte so the service can distinguish an oversized upload."""
        return self.settings.max_upload_bytes + 1

    async def create_upload(
        self,
        knowledge_base_id: str,
        filename: str,
        declared_content_type: str | None,
        content: bytes,
    ) -> AcceptedDocumentUpload:
        if await knowledge_bases.get(self.session, knowledge_base_id) is None:
            raise ResourceNotFoundError("知识库不存在")

        extension = Path(filename).suffix.lower()
        if extension not in SUPPORTED_DOCUMENT_TYPES:
            supported = supported_extensions_label()
            raise UnsupportedMediaTypeError(
                f"不支持 {extension or '无扩展名'} 文件；当前支持：{supported}"
            )
        if len(content) > self.settings.max_upload_bytes:
            raise PayloadTooLargeError(f"文件不能超过 {self.settings.max_upload_mb} MB")
        if not content:
            raise InvalidInputError("文件为空")

        document: Document | None = None
        try:
            document = await documents.create(
                self.session,
                knowledge_base_id=knowledge_base_id,
                filename=filename,
                content_type=content_type_for(filename, declared_content_type),
                size_bytes=len(content),
                sha256=hashlib.sha256(content).hexdigest(),
                storage_path="pending",
            )
            document.storage_path = self.storage.save_document(document.id, filename, content)
            job = await ingestion_jobs.create(self.session, document_id=document.id)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            if document is not None:
                self.storage.delete_document(document.id)
            raise ConflictError("该知识库中已存在内容相同的文档") from exc
        except Exception:
            await self.session.rollback()
            if document is not None:
                self.storage.delete_document(document.id)
            raise

        await self.session.refresh(document)
        await self.session.refresh(job)
        return AcceptedDocumentUpload(document=document, job=job)

    async def list(self, knowledge_base_id: str) -> list[Document]:
        return await documents.list_by_knowledge_base(self.session, knowledge_base_id)

    async def get(self, document_id: str) -> Document:
        document = await documents.get(self.session, document_id)
        if document is None:
            raise ResourceNotFoundError("文档不存在")
        return document

    async def get_image_path(self, document_id: str, sequence_no: int) -> Path:
        element = await document_elements.get_image(self.session, document_id, sequence_no)
        if element is None or not element.image_path:
            raise ResourceNotFoundError("图片不存在")
        path = self.storage.resolve(element.image_path)
        if not path.exists():
            raise ResourceNotFoundError("图片文件不存在")
        return path
