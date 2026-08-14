import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Document, DocumentElement, IngestionJob
from app.documents.chunker import StructureAwareChunker
from app.documents.registry import DocumentParserRegistry
from app.services.embeddings import EmbeddingService
from app.services.image_enrichment import ImageEnricher
from app.services.storage import LocalFileStorage
from app.services.vector_store import MilvusVectorStore

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        storage: LocalFileStorage,
        embeddings: EmbeddingService,
        vector_store: MilvusVectorStore,
        image_enricher: ImageEnricher,
        chunker: StructureAwareChunker,
        parser_registry: DocumentParserRegistry | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.storage = storage
        self.embeddings = embeddings
        self.vector_store = vector_store
        self.image_enricher = image_enricher
        self.chunker = chunker
        self.parser_registry = parser_registry or DocumentParserRegistry()

    async def process(self, document_id: str) -> None:
        async with self.session_factory() as session:
            document = await session.get(Document, document_id)
            if not document:
                logger.warning("Document %s disappeared before ingestion", document_id)
                return
            job = await self._latest_job(session, document_id)
            if not job:
                logger.warning("Document %s has no ingestion job", document_id)
                return

            try:
                job.status = "running"
                job.stage = "parsing"
                job.progress = 10
                job.attempts += 1
                job.started_at = datetime.now(UTC)
                document.status = "processing"
                await session.commit()

                path = self.storage.resolve(document.storage_path)
                elements = await asyncio.to_thread(self.parser_registry.parse, path)

                job.stage = "image_enrichment"
                job.progress = 35
                await session.commit()
                for element in elements:
                    if element.kind != "image" or not element.image_bytes:
                        continue
                    element.image_path = self.storage.save_image(
                        document.id,
                        element.sequence_no,
                        element.image_extension or ".bin",
                        element.image_bytes,
                    )
                    await self.image_enricher.enrich(element)

                job.stage = "chunking"
                job.progress = 55
                await session.commit()
                chunks = self.chunker.chunk(elements)

                job.stage = "embedding"
                job.progress = 70
                await session.commit()
                vectors = await self.embeddings.embed_documents([chunk.content for chunk in chunks])

                job.stage = "vector_indexing"
                job.progress = 85
                await session.commit()
                await self.vector_store.upsert(
                    document.knowledge_base_id, document.id, chunks, vectors
                )

                session.add_all(
                    [
                        DocumentElement(
                            document_id=document.id,
                            sequence_no=element.sequence_no,
                            kind=element.kind,
                            text_content=element.text or None,
                            heading_path=element.heading_path or None,
                            image_path=element.image_path,
                            image_caption=element.image_caption or None,
                            image_ocr=element.image_ocr or None,
                            relationship_id=element.relationship_id,
                            element_metadata=element.metadata or None,
                        )
                        for element in elements
                    ]
                )
                document.status = "completed"
                document.element_count = len(elements)
                document.chunk_count = len(chunks)
                document.error_message = None
                document.processed_at = datetime.now(UTC)
                job.status = "completed"
                job.stage = "completed"
                job.progress = 100
                job.finished_at = datetime.now(UTC)
                await session.commit()
            except Exception as exc:
                logger.exception("Ingestion failed for document %s", document_id)
                await session.rollback()
                try:
                    await self.vector_store.delete_document(document_id)
                except Exception:
                    logger.exception("Failed to clean Milvus rows for %s", document_id)
                document = await session.get(Document, document_id)
                job = await self._latest_job(session, document_id)
                if document:
                    document.status = "failed"
                    document.error_message = str(exc)[:4000]
                if job:
                    job.status = "failed"
                    job.stage = "failed"
                    job.error_message = str(exc)[:4000]
                    job.finished_at = datetime.now(UTC)
                await session.commit()

    @staticmethod
    async def _latest_job(session: AsyncSession, document_id: str) -> IngestionJob | None:
        result = await session.execute(
            select(IngestionJob)
            .where(IngestionJob.document_id == document_id)
            .order_by(IngestionJob.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
