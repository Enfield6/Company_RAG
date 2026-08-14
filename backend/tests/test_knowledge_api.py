import asyncio

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app


def test_create_and_list_knowledge_base(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'api.db'}", poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def prepare_database() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def override_db():
        async with session_factory() as session:
            yield session

    asyncio.run(prepare_database())
    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            created = client.post(
                "/api/v1/knowledge-bases",
                json={"name": "研发资料", "description": "内部技术文档"},
            )
            listed = client.get("/api/v1/knowledge-bases")
    finally:
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())

    assert created.status_code == 201
    assert created.json()["name"] == "研发资料"
    assert listed.status_code == 200
    assert listed.json()[0]["document_count"] == 0
