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
        "list",
        "image",
        "callout",
    ]
    assert blocks[1]["source_ranks"] == [1]
    assert blocks[2]["style"] == "ordered"
    assert blocks[3]["caption"] == "请假审批流程图"
    assert blocks[3]["relation"] == "direct"
    assert blocks[3]["placement"] == "inline"


def test_rich_content_uses_semantics_when_answer_does_not_repeat_source_rank() -> None:
    answer = """### 卡机连接故障排查

**1. 检查网络**
确认网线和无线网络是否正常。[来源1]

**2. 完成卡机入库**
在设备后台填写设备码并绑定酒店。[来源1]

**3. 重启验证**
保存设置后重启应用。"""
    image = {
        "type": "image",
        "document_id": "doc-1",
        "sequence_no": 12,
        "caption": "卡机入库页面，需要填写设备码并选择酒店",
        "source_rank": 2,
        "source_label": "操作手册.docx",
        "relation": "nearby",
        "alt": "卡机入库页面",
        "anchor_text": "新卡机入库，填写设备码后绑定酒店",
    }

    blocks = RichContentBuilder().insert_images(
        RichContentBuilder().build(answer, []), [image]
    )

    image_index = next(index for index, block in enumerate(blocks) if block["type"] == "image")
    assert blocks[image_index - 2]["text"] == "2. 完成卡机入库"
    assert blocks[image_index - 1]["text"].startswith("在设备后台填写设备码")
    assert blocks[image_index]["placement"] == "inline"
    assert "anchor_text" not in blocks[image_index]


def test_rich_content_turns_standalone_bold_lines_into_section_headings() -> None:
    answer = """### 故障排查

**1. 检查网络环境**
请先确认有线网络是否可用。[来源1]

**2. 检查设备状态**
重启设备后再次验证。"""

    blocks = RichContentBuilder().build(answer, [])

    assert [block["type"] for block in blocks] == [
        "heading",
        "heading",
        "lead",
        "heading",
        "paragraph",
    ]
    assert blocks[1]["text"] == "1. 检查网络环境"
    assert blocks[1]["level"] == 3


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
        blocks.append(
            {
                "id": "stale-image",
                "type": "image",
                "document_id": document.id,
                "sequence_no": 99,
                "caption": "已经失效的旧图片引用",
            }
        )
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
