import asyncio
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.deps import get_rag_graph
from app.db.base import Base
from app.db.models import Citation, KnowledgeBase, Message
from app.db.session import get_db
from app.main import app
from app.schemas.chat import CitationRead


class FakeRichContent:
    async def add_related_document_images(self, _db, blocks, _citations):
        return blocks


class FakeGraph:
    answer_generator = SimpleNamespace(model_name="test-model")
    rich_content = FakeRichContent()

    async def ask(self, _question, _knowledge_base_id, _history):
        return {
            "answer": "这是一个图文回答。",
            "citations": [],
            "rich_blocks": [
                {
                    "id": "block-0",
                    "type": "image",
                    "document_id": "doc-1",
                    "sequence_no": 3,
                    "caption": "流程图",
                    "source_label": "测试文档",
                    "relation": "nearby",
                    "alt": "流程图",
                }
            ],
        }


def test_citation_schema_uses_json_metadata_column() -> None:
    citation = Citation(
        document_id="doc-1",
        chunk_id="chunk-1",
        rank=1,
        score=0.88,
        citation_metadata={"chunk_type": "image", "sequence_no": 3},
    )

    parsed = CitationRead.model_validate(citation)

    assert parsed.metadata == {"chunk_type": "image", "sequence_no": 3}


def test_chat_stream_emits_and_persists_rich_blocks(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'chat.db'}", poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def prepare_database() -> str:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with session_factory() as session:
            knowledge_base = KnowledgeBase(
                name="图文知识库", embedding_model="test", embedding_dimension=4
            )
            session.add(knowledge_base)
            await session.commit()
            return knowledge_base.id

    async def override_db():
        async with session_factory() as session:
            yield session

    async def load_assistant_message() -> Message:
        async with session_factory() as session:
            result = await session.execute(select(Message).where(Message.role == "assistant"))
            return result.scalar_one()

    knowledge_base_id = asyncio.run(prepare_database())
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_rag_graph] = lambda: FakeGraph()
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/chat/stream",
                json={"knowledge_base_id": knowledge_base_id, "question": "展示流程"},
            )
        message = asyncio.run(load_assistant_message())
    finally:
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())

    assert response.status_code == 200
    assert "event: status" in response.text
    assert "event: media" in response.text
    assert "event: rich" in response.text
    assert message.content_blocks[0]["caption"] == "流程图"
