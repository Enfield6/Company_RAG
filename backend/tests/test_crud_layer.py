import ast
import asyncio
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.crud.documents import documents
from app.crud.knowledge_bases import knowledge_bases
from app.db.base import Base
from app.services.chat import ChatService
from app.services.knowledge_bases import KnowledgeBaseService


def test_crud_objects_are_reusable_without_http(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'crud.db'}", poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def exercise_crud() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with session_factory() as session:
            knowledge_base = await knowledge_bases.create(
                session,
                name="可复用知识库",
                description=None,
                embedding_model="test",
                embedding_dimension=4,
            )
            await documents.create(
                session,
                knowledge_base_id=knowledge_base.id,
                filename="guide.md",
                content_type="text/markdown",
                size_bytes=5,
                sha256="a" * 64,
                storage_path="doc/original/guide.md",
            )
            await session.commit()

            record = await knowledge_bases.get_with_document_count(session, knowledge_base.id)
            listed_documents = await documents.list_by_knowledge_base(session, knowledge_base.id)

        assert record is not None
        assert record.document_count == 1
        assert [item.filename for item in listed_documents] == ["guide.md"]

    try:
        asyncio.run(exercise_crud())
    finally:
        asyncio.run(engine.dispose())


def test_services_compose_crud_into_one_chat_workflow(tmp_path) -> None:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'service.db'}", poolclass=NullPool
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def exercise_services() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with session_factory() as session:
            settings = Settings(embedding_model="test", embedding_dimension=4)
            knowledge_service = KnowledgeBaseService(session, settings)
            knowledge_base = await knowledge_service.create("业务层知识库", None)

            chat_service = ChatService(session)
            context = await chat_service.start(knowledge_base.id, "第一问")
            await chat_service.complete(
                conversation_id=context.conversation.id,
                answer="第一答",
                content_blocks=[{"type": "paragraph", "text": "第一答"}],
                model_name="test-model",
                citation_values=[],
            )
            second_context = await chat_service.start(
                knowledge_base.id, "第二问", context.conversation.id
            )
            detail = await chat_service.get_conversation(context.conversation.id)

        assert second_context.history == [
            {"role": "user", "content": "第一问"},
            {"role": "assistant", "content": "第一答"},
        ]
        assert [message.content for message in detail.messages] == [
            "第一问",
            "第一答",
            "第二问",
        ]

    try:
        asyncio.run(exercise_services())
    finally:
        asyncio.run(engine.dispose())


def test_route_modules_do_not_import_database_or_sqlalchemy() -> None:
    routes_directory = Path(__file__).parents[1] / "app" / "api" / "routes"
    violations: list[str] = []
    forbidden_prefixes = ("sqlalchemy", "app.db", "app.crud")

    for route_path in routes_directory.glob("*.py"):
        tree = ast.parse(route_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            for module in modules:
                if module.startswith(forbidden_prefixes):
                    violations.append(f"{route_path.name}: {module}")

    assert violations == []


def test_crud_modules_do_not_control_transactions() -> None:
    crud_directory = Path(__file__).parents[1] / "app" / "crud"
    violations: list[str] = []

    for crud_path in crud_directory.glob("*.py"):
        tree = ast.parse(crud_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in {"commit", "rollback"}:
                violations.append(f"{crud_path.name}: {node.attr}")

    assert violations == []
