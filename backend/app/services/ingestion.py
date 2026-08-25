import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.crud.documents import document_elements, documents
from app.crud.ingestion_jobs import ingestion_jobs
from app.db.models import DocumentElement
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
        image_enrichment_concurrency: int = 4,
    ) -> None:
        self.session_factory = session_factory
        self.storage = storage
        self.embeddings = embeddings
        self.vector_store = vector_store
        self.image_enricher = image_enricher
        self.chunker = chunker
        self.parser_registry = parser_registry or DocumentParserRegistry()
        self.image_enrichment_concurrency = max(1, image_enrichment_concurrency)

    async def process(self, document_id: str) -> None:
        async with self.session_factory() as session:
            document = await documents.get(session, document_id)
            if not document:
                logger.warning("Document %s disappeared before ingestion", document_id)
                return
            job = await ingestion_jobs.get_latest(session, document_id)
            if not job:
                logger.warning("Document %s has no ingestion job", document_id)
                return

            try:
                job.status = "running"
                job.stage = "parsing"
                job.progress = 10
                job.attempts += 1
                job.started_at = datetime.now(UTC)
                job.finished_at = None
                job.error_message = None
                document.status = "processing"
                document.error_message = None
                await session.commit()

                path = self.storage.resolve(document.storage_path)
                elements = await asyncio.to_thread(self.parser_registry.parse, path)

                job.stage = "image_enrichment"
                job.progress = 35
                await session.commit()
                image_elements = [
                    element
                    for element in elements
                    if element.kind == "image" and element.image_bytes
                ]
                for element in image_elements:
                    element.image_path = self.storage.save_image(
                        document.id,
                        element.sequence_no,
                        element.image_extension or ".bin",
                        element.image_bytes,
                    )

                semaphore = asyncio.Semaphore(self.image_enrichment_concurrency)

                async def enrich_image(element) -> None:
                    async with semaphore:
                        await self.image_enricher.enrich(element)

                if image_elements:
                    logger.info(
                        "Enriching %s images for document %s with concurrency %s",
                        len(image_elements),
                        document.id,
                        self.image_enrichment_concurrency,
                    )
                    await asyncio.gather(*(enrich_image(element) for element in image_elements))

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

                await document_elements.replace_for_document(
                    session,
                    document.id,
                    (
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
                    ),
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
                try:
                    self.storage.prune_images(
                        document.id,
                        {element.image_path for element in image_elements if element.image_path},
                    )
                except Exception:
                    logger.exception("Failed to prune stale images for %s", document.id)
            except Exception as exc:
                logger.exception("Ingestion failed for document %s", document_id)
                await session.rollback()
                try:
                    await self.vector_store.delete_document(document_id)
                except Exception:
                    logger.exception("Failed to clean Milvus rows for %s", document_id)
                document = await documents.get(session, document_id)
                job = await ingestion_jobs.get_latest(session, document_id)
                if document:
                    document.status = "failed"
                    document.error_message = str(exc)[:4000]
                if job:
                    job.status = "failed"
                    job.stage = "failed"
                    job.error_message = str(exc)[:4000]
                    job.finished_at = datetime.now(UTC)
                await session.commit()
