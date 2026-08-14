from app.documents.chunker import StructureAwareChunker
from app.documents.types import ParsedElement


def test_chunker_keeps_image_context_and_relation_metadata() -> None:
    elements = [
        ParsedElement(sequence_no=0, kind="text", text="审批流程如下。", heading_path=["流程"]),
        ParsedElement(
            sequence_no=1,
            kind="image",
            heading_path=["流程"],
            image_path="doc/images/000001.png",
            image_caption="一张三步审批流程图",
            image_ocr="提交 复核 批准",
            relationship_id="rId7",
            metadata={
                "previous_text": "审批流程如下。",
                "next_text": "审批完成后归档。",
                "previous_sequence": 0,
                "next_sequence": 2,
                "caption_source": "vision_model",
            },
        ),
        ParsedElement(sequence_no=2, kind="text", text="审批完成后归档。", heading_path=["流程"]),
    ]

    chunks = StructureAwareChunker(chunk_size=100, overlap=10).chunk(elements)

    assert [chunk.kind for chunk in chunks] == ["text", "image", "text"]
    image = chunks[1]
    assert "三步审批流程图" in image.content
    assert "提交 复核 批准" in image.content
    assert image.image_path == "doc/images/000001.png"
    assert image.metadata["previous_sequence"] == 0
    assert image.metadata["next_sequence"] == 2


def test_chunker_splits_long_text_with_overlap() -> None:
    text = "第一句。" * 80
    chunks = StructureAwareChunker(chunk_size=120, overlap=20).chunk(
        [ParsedElement(sequence_no=0, kind="text", text=text)]
    )

    assert len(chunks) > 1
    assert all(len(chunk.content) <= 120 for chunk in chunks)
