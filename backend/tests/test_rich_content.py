from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import Document, DocumentElement, KnowledgeBase
from app.services.rich_content import RichContentBuilder


def test_rich_content_builds_editorial_blocks_and_direct_image() -> None:
    answer = """## 请假审批要点

员工应先在系统发起申请。[来源1]

1. 填写请假时间
2. 直属主管审批[来源2]

> 审批完成后再安排休假。"""
    citations = [
        {
            "chunk_id": "image-1",
            "document_id": "doc-1",
            "rank": 2,
            "score": 0.91,
            "quote": "图片说明：请假审批流程图\n图片OCR：提交 审批 归档",
            "chunk_type": "image",
            "sequence_no": 8,
            "metadata": {"heading_path": ["员工手册", "请假流程"]},
        }
    ]

    blocks = RichContentBuilder().build(answer, citations)

    assert [block["type"] for block in blocks] == [
        "heading",
        "lead",
        "image",
        "list",
        "callout",
    ]
    assert blocks[1]["source_ranks"] == [1]
    assert blocks[2]["caption"] == "请假审批流程图"
    assert blocks[2]["relation"] == "direct"
    assert blocks[3]["style"] == "ordered"


async def test_rich_content_adds_only_nearby_document_image(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'rich.db'}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        knowledge_base = KnowledgeBase(
            name="制度库",
            embedding_model="test-model",
            embedding_dimension=4,
        )
        session.add(knowledge_base)
        await session.flush()
        document = Document(
            knowledge_base_id=knowledge_base.id,
            filename="员工手册.docx",
            content_type="application/docx",
            size_bytes=100,
            sha256="a" * 64,
            storage_path="doc/original/员工手册.docx",
        )
        session.add(document)
        await session.flush()
        session.add(
            DocumentElement(
                document_id=document.id,
                sequence_no=13,
                kind="image",
                image_path="doc/images/13.png",
                image_caption="审批角色与流转关系",
            )
        )
        await session.commit()

        blocks = RichContentBuilder().build("审批需要直属主管确认。[来源1]", [])
        result = await RichContentBuilder().add_related_document_images(
            session,
            blocks,
            [
                {
                    "document_id": document.id,
                    "sequence_no": 10,
                    "rank": 1,
                    "chunk_type": "text",
                }
            ],
        )

    await engine.dispose()
    image = next(block for block in result if block["type"] == "image")
    assert image["sequence_no"] == 13
    assert image["relation"] == "nearby"
    assert image["source_label"] == "员工手册.docx"
