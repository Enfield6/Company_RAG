from app.documents.types import KnowledgeChunk
from app.services.vector_store import MilvusVectorStore


class FakeMilvusClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def has_collection(self, _collection_name: str) -> bool:
        return True

    def delete(self, *, collection_name: str, filter: str) -> None:
        self.calls.append(("delete", (collection_name, filter)))

    def flush(self, *, collection_name: str) -> None:
        self.calls.append(("flush", collection_name))

    def upsert(self, *, collection_name: str, data: list[dict]) -> None:
        self.calls.append(("upsert", (collection_name, data)))


async def test_upsert_replaces_existing_document_vectors() -> None:
    store = MilvusVectorStore("http://milvus:19530", None, "chunks", 2)
    client = FakeMilvusClient()
    store._client = client  # type: ignore[assignment]
    chunk = KnowledgeChunk(
        id="chunk-1",
        kind="text",
        content="更新后的内容",
        sequence_no=3,
        element_sequences=[3],
        heading_path=["说明"],
    )

    await store.upsert("kb-1", "doc-1", [chunk], [[0.1, 0.2]])

    assert [name for name, _ in client.calls] == ["delete", "flush", "upsert", "flush"]
    assert client.calls[0][1] == ("chunks", 'document_id == "doc-1"')
    upsert_rows = client.calls[2][1][1]  # type: ignore[index]
    assert len(upsert_rows) == 1
    assert upsert_rows[0]["document_id"] == "doc-1"
