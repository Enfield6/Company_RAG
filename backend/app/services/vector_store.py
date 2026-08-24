import asyncio
from typing import Any

from pymilvus import DataType, MilvusClient

from app.documents.types import KnowledgeChunk, RetrievedChunk


class MilvusVectorStore:
    def __init__(
        self,
        uri: str,
        token: str | None,
        collection_name: str,
        dimension: int,
    ) -> None:
        self.uri = uri
        self.token = token
        self.collection_name = collection_name
        self.dimension = dimension
        self._client: MilvusClient | None = None

    def _get_client(self) -> MilvusClient:
        if self._client is None:
            kwargs: dict[str, Any] = {"uri": self.uri}
            if self.token:
                kwargs["token"] = self.token
            self._client = MilvusClient(**kwargs)
        return self._client

    async def ensure_collection(self) -> None:
        await asyncio.to_thread(self._ensure_collection_sync)

    def _ensure_collection_sync(self) -> None:
        client = self._get_client()
        if client.has_collection(self.collection_name):
            return

        schema = client.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field("id", DataType.VARCHAR, is_primary=True, max_length=64)
        schema.add_field("knowledge_base_id", DataType.VARCHAR, max_length=36)
        schema.add_field("document_id", DataType.VARCHAR, max_length=36)
        schema.add_field("chunk_type", DataType.VARCHAR, max_length=32)
        schema.add_field("sequence_no", DataType.INT64)
        schema.add_field("content", DataType.VARCHAR, max_length=65535)
        schema.add_field("metadata", DataType.JSON)
        schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=self.dimension)

        indexes = client.prepare_index_params()
        indexes.add_index("embedding", index_type="AUTOINDEX", metric_type="COSINE")
        indexes.add_index("knowledge_base_id", index_type="INVERTED")
        indexes.add_index("document_id", index_type="INVERTED")
        client.create_collection(
            collection_name=self.collection_name,
            schema=schema,
            index_params=indexes,
        )

    async def upsert(
        self,
        knowledge_base_id: str,
        document_id: str,
        chunks: list[KnowledgeChunk],
        vectors: list[list[float]],
    ) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("Chunk/vector count mismatch")
        await self.ensure_collection()
        rows = [
            {
                "id": chunk.id,
                "knowledge_base_id": knowledge_base_id,
                "document_id": document_id,
                "chunk_type": chunk.kind,
                "sequence_no": chunk.sequence_no,
                "content": chunk.content,
                "metadata": {
                    **chunk.metadata,
                    "heading_path": chunk.heading_path,
                    "element_sequences": chunk.element_sequences,
                    "image_path": chunk.image_path,
                },
                "embedding": vector,
            }
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        await asyncio.to_thread(self._replace_document_sync, document_id, rows)

    def _replace_document_sync(self, document_id: str, rows: list[dict[str, Any]]) -> None:
        client = self._get_client()
        client.delete(
            collection_name=self.collection_name,
            filter=f'document_id == "{document_id}"',
        )
        client.flush(collection_name=self.collection_name)
        if rows:
            client.upsert(collection_name=self.collection_name, data=rows)
            client.flush(collection_name=self.collection_name)

    async def search(
        self,
        knowledge_base_id: str,
        vector: list[float],
        limit: int,
    ) -> list[RetrievedChunk]:
        await self.ensure_collection()
        results = await asyncio.to_thread(
            self._get_client().search,
            collection_name=self.collection_name,
            data=[vector],
            filter=f'knowledge_base_id == "{knowledge_base_id}"',
            limit=limit,
            output_fields=["document_id", "chunk_type", "sequence_no", "content", "metadata"],
            search_params={"metric_type": "COSINE", "params": {}},
        )
        hits = results[0] if results else []
        return [
            RetrievedChunk(
                id=str(hit["id"]),
                document_id=str(hit["entity"]["document_id"]),
                content=str(hit["entity"]["content"]),
                chunk_type=str(hit["entity"]["chunk_type"]),
                sequence_no=int(hit["entity"]["sequence_no"]),
                score=float(hit.get("distance", 0)),
                metadata=hit["entity"].get("metadata") or {},
            )
            for hit in hits
        ]

    async def delete_document(self, document_id: str) -> None:
        if not self._get_client().has_collection(self.collection_name):
            return
        await asyncio.to_thread(
            self._get_client().delete,
            collection_name=self.collection_name,
            filter=f'document_id == "{document_id}"',
        )

    async def ping(self) -> bool:
        try:
            await asyncio.to_thread(self._get_client().list_collections)
            return True
        except Exception:
            return False
