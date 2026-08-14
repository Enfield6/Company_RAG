import asyncio

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.deps import get_storage
from app.api.routes import documents as document_routes
from app.db.base import Base
from app.db.models import KnowledgeBase
from app.db.session import get_db
from app.main import app
from app.services.storage import LocalFileStorage


def test_upload_accepts_markdown_and_rejects_unknown_format(tmp_path, monkeypatch) -> None:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'upload.db'}",
        poolclass=NullPool,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def prepare_database() -> str:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with session_factory() as session:
            knowledge_base = KnowledgeBase(
                name="格式测试",
                embedding_model="text-embedding-v4",
                embedding_dimension=1024,
            )
            session.add(knowledge_base)
            await session.commit()
            return knowledge_base.id

    async def override_db():
        async with session_factory() as session:
            yield session

    async def skip_ingestion(_document_id: str) -> None:
        return None

    knowledge_base_id = asyncio.run(prepare_database())
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_storage] = lambda: LocalFileStorage(tmp_path / "uploads")
    monkeypatch.setattr(document_routes, "_ingest_document", skip_ingestion)
    try:
        with TestClient(app) as client:
            accepted = client.post(
                f"/api/v1/knowledge-bases/{knowledge_base_id}/documents",
                files={"file": ("guide.md", b"# Guide\n\nContent", "text/markdown")},
            )
            rejected = client.post(
                f"/api/v1/knowledge-bases/{knowledge_base_id}/documents",
                files={"file": ("data.csv", b"a,b", "text/csv")},
            )
    finally:
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())

    assert accepted.status_code == 202
    assert accepted.json()["document"]["content_type"] == "text/markdown"
    assert rejected.status_code == 415
    assert ".pdf" in rejected.json()["detail"]
