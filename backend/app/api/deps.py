from functools import lru_cache

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.documents.chunker import StructureAwareChunker
from app.graph.rag import AnswerGenerator, RAGGraph
from app.services.embeddings import EmbeddingService
from app.services.image_enrichment import ImageEnricher
from app.services.ingestion import IngestionService
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
