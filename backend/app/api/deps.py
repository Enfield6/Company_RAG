from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import AsyncSessionLocal, get_db
from app.documents.chunker import StructureAwareChunker
from app.graph.rag import AnswerGenerator, RAGGraph
from app.services.chat import ChatService
from app.services.documents import DocumentService
from app.services.embeddings import EmbeddingService
from app.services.health import HealthService
from app.services.image_enrichment import ImageEnricher
from app.services.ingestion import IngestionService
from app.services.knowledge_bases import KnowledgeBaseService
from app.services.storage import LocalFileStorage
from app.services.vector_store import MilvusVectorStore


@lru_cache
def get_storage() -> LocalFileStorage:
    return LocalFileStorage(get_settings().upload_dir)


@lru_cache
def get_vector_store() -> MilvusVectorStore:
    settings = get_settings()
    return MilvusVectorStore(
        settings.milvus_uri,
        settings.milvus_token,
        settings.milvus_collection,
        settings.embedding_dimension,
    )


@lru_cache
def get_embeddings() -> EmbeddingService:
    settings = get_settings()
    return EmbeddingService(
        settings.embedding_model,
        settings.embedding_dimension,
        settings.resolved_embedding_base_url,
        settings.resolved_embedding_api_key,
    )


@lru_cache
def get_image_enricher() -> ImageEnricher:
    settings = get_settings()
    return ImageEnricher(
        settings.resolved_vision_base_url,
        settings.resolved_vision_api_key,
        settings.vision_model,
    )


def build_ingestion_service() -> IngestionService:
    settings = get_settings()
    return IngestionService(
        AsyncSessionLocal,
        get_storage(),
        get_embeddings(),
        get_vector_store(),
        get_image_enricher(),
        StructureAwareChunker(settings.chunk_size, settings.chunk_overlap),
        image_enrichment_concurrency=settings.image_enrichment_concurrency,
    )


@lru_cache
def get_rag_graph() -> RAGGraph:
    settings = get_settings()
    generator = AnswerGenerator(
        settings.resolved_llm_base_url,
        settings.resolved_llm_api_key,
        settings.llm_model,
        settings.llm_temperature,
    )
    return RAGGraph(
        get_embeddings(),
        get_vector_store(),
        generator,
        settings.retrieval_top_k,
    )


def get_knowledge_base_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> KnowledgeBaseService:
    return KnowledgeBaseService(db, settings)


def get_document_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    storage: Annotated[LocalFileStorage, Depends(get_storage)],
) -> DocumentService:
    return DocumentService(db, settings, storage)


def get_chat_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChatService:
    return ChatService(db)


def get_health_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    vector_store: Annotated[MilvusVectorStore, Depends(get_vector_store)],
) -> HealthService:
    return HealthService(db, vector_store)
