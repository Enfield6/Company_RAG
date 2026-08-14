import uuid

from app.documents.types import KnowledgeChunk, ParsedElement


class StructureAwareChunker:
    def __init__(self, chunk_size: int = 900, overlap: int = 120) -> None:
        if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
            raise ValueError("chunk_size must be positive and overlap must be smaller")
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, elements: list[ParsedElement]) -> list[KnowledgeChunk]:
        chunks: list[KnowledgeChunk] = []
        pending: list[ParsedElement] = []
        pending_heading: list[str] = []

        def flush() -> None:
            nonlocal pending, pending_heading
            if not pending:
                return
            content = "\n\n".join(element.text for element in pending if element.text)
            sequences = [element.sequence_no for element in pending]
            kind = "table" if all(element.kind == "table" for element in pending) else "text"
            for part_index, part in enumerate(self._split(content)):
                chunks.append(
                    KnowledgeChunk(
                        id=str(uuid.uuid4()),
                        kind=kind,
                        content=part,
                        sequence_no=sequences[0],
                        element_sequences=sequences,
                        heading_path=list(pending_heading),
                        metadata={"part_index": part_index},
                    )
                )
            pending = []
            pending_heading = []

        for element in elements:
            if element.kind == "image":
                flush()
                previous_text = element.metadata.get("previous_text", "")
                next_text = element.metadata.get("next_text", "")
                caption = element.image_caption or "未配置视觉模型，使用图片邻近文字作为语义线索。"
                image_content = (
                    f"图片说明：{caption}\n"
                    f"图片OCR：{element.image_ocr or '无'}\n"
                    f"前文：{previous_text or '无'}\n"
                    f"后文：{next_text or '无'}"
                )
                chunks.append(
                    KnowledgeChunk(
                        id=str(uuid.uuid4()),
                        kind="image",
                        content=image_content,
                        sequence_no=element.sequence_no,
                        element_sequences=[element.sequence_no],
                        heading_path=list(element.heading_path),
                        image_path=element.image_path,
                        metadata={
                            "relationship_id": element.relationship_id,
                            "previous_sequence": element.metadata.get("previous_sequence"),
                            "next_sequence": element.metadata.get("next_sequence"),
                            "caption_source": element.metadata.get(
                                "caption_source", "context_fallback"
                            ),
                        },
                    )
                )
                continue

            projected_size = sum(len(item.text) for item in pending) + len(element.text)
            if pending and (
                element.heading_path != pending_heading or projected_size > self.chunk_size
            ):
                flush()
            if not pending:
                pending_heading = list(element.heading_path)
            pending.append(element)

        flush()
        return chunks

    def _split(self, text: str) -> list[str]:
        if len(text) <= self.chunk_size:
            return [text] if text else []
        result: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            if end < len(text):
                boundary = max(text.rfind("\n", start, end), text.rfind("。", start, end))
                if boundary > start + self.chunk_size // 2:
                    end = boundary + 1
            result.append(text[start:end].strip())
            if end == len(text):
                break
            start = max(end - self.overlap, start + 1)
        return [part for part in result if part]
