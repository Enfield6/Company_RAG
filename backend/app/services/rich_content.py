import re
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document, DocumentElement

SOURCE_PATTERN = re.compile(r"\[来源(\d+)]")
HEADING_PATTERN = re.compile(r"^(#{1,4})\s+(.+)$")
ORDERED_ITEM_PATTERN = re.compile(r"^\s*(\d+)[.)、]\s+(.+)$")
BULLET_ITEM_PATTERN = re.compile(r"^\s*[-*•]\s+(.+)$")


class RichContentBuilder:
    """Turn trusted plain model output into a safe, renderable block document."""

    def build(self, answer: str, citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        blocks = self._parse_text(answer)
        direct_images = [
            self._image_from_citation(citation)
            for citation in citations
            if citation.get("chunk_type") == "image"
            and isinstance(citation.get("sequence_no"), int)
        ]
        return self.insert_images(blocks, [image for image in direct_images if image][:2])

    async def add_related_document_images(
        self,
        db: AsyncSession,
        blocks: list[dict[str, Any]],
        citations: list[dict[str, Any]],
        max_images: int = 2,
        max_sequence_distance: int = 12,
    ) -> list[dict[str, Any]]:
        images = [block for block in blocks if block.get("type") == "image"]
        used = {(block.get("document_id"), block.get("sequence_no")) for block in images}

        document_ids = {str(item["document_id"]) for item in citations if item.get("document_id")}
        filenames: dict[str, str] = {}
        if document_ids:
            result = await db.execute(
                select(Document.id, Document.filename).where(Document.id.in_(document_ids))
            )
            filenames = dict(result.all())
        for image in images:
            image["source_label"] = filenames.get(
                str(image.get("document_id")), image.get("source_label") or "知识库文档"
            )

        related_images: list[dict[str, Any]] = []
        for citation in citations:
            if len(images) + len(related_images) >= max_images:
                break
            document_id = citation.get("document_id")
            sequence_no = citation.get("sequence_no")
            if not document_id or not isinstance(sequence_no, int):
                continue
            result = await db.execute(
                select(DocumentElement)
                .where(
                    DocumentElement.document_id == document_id,
                    DocumentElement.kind == "image",
                    DocumentElement.image_path.is_not(None),
                )
                .order_by(func.abs(DocumentElement.sequence_no - sequence_no))
                .limit(1)
            )
            element = result.scalar_one_or_none()
            if not element:
                continue
            key = (document_id, element.sequence_no)
            if key in used or abs(element.sequence_no - sequence_no) > max_sequence_distance:
                continue
            used.add(key)
            related_images.append(
                {
                    "type": "image",
                    "document_id": document_id,
                    "sequence_no": element.sequence_no,
                    "caption": element.image_caption or "与引用内容位于同一段落附近的文档配图",
                    "source_rank": citation.get("rank"),
                    "source_label": filenames.get(str(document_id), "知识库文档"),
                    "relation": "nearby",
                    "alt": element.image_caption or "相关文档配图",
                }
            )

        return self.insert_images(blocks, related_images)

    def insert_images(
        self, blocks: list[dict[str, Any]], images: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        if not images:
            return self._with_ids(blocks)
        result = list(blocks)
        for image_index, image in enumerate(images):
            if any(
                block.get("type") == "image"
                and block.get("document_id") == image.get("document_id")
                and block.get("sequence_no") == image.get("sequence_no")
                for block in result
            ):
                continue
            text_positions = [
                index
                for index, block in enumerate(result)
                if block.get("type") in {"lead", "paragraph", "list", "callout"}
            ]
            if text_positions:
                anchor_index = min(image_index * 2, len(text_positions) - 1)
                insert_at = text_positions[anchor_index] + 1
            else:
                insert_at = len(result)
            result.insert(insert_at, image)
        return self._with_ids(result)

    def _parse_text(self, answer: str) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        lines = answer.replace("\r\n", "\n").split("\n")
        paragraph_lines: list[str] = []
        list_items: list[str] = []
        list_style = "bullet"
        quote_lines: list[str] = []

        def flush_paragraph() -> None:
            if not paragraph_lines:
                return
            text = " ".join(line.strip() for line in paragraph_lines if line.strip())
            paragraph_lines.clear()
            if text:
                blocks.append(
                    {
                        "type": "paragraph",
                        "text": text,
                        "source_ranks": self._source_ranks(text),
                    }
                )

        def flush_list() -> None:
            if not list_items:
                return
            blocks.append(
                {
                    "type": "list",
                    "style": list_style,
                    "items": list(list_items),
                    "source_ranks": sorted(
                        {rank for item in list_items for rank in self._source_ranks(item)}
                    ),
                }
            )
            list_items.clear()

        def flush_quote() -> None:
            if not quote_lines:
                return
            text = " ".join(quote_lines)
            blocks.append(
                {
                    "type": "callout",
                    "tone": "info",
                    "text": text,
                    "source_ranks": self._source_ranks(text),
                }
            )
            quote_lines.clear()

        for raw_line in lines:
            line = raw_line.strip()
            heading = HEADING_PATTERN.match(line)
            ordered = ORDERED_ITEM_PATTERN.match(line)
            bullet = BULLET_ITEM_PATTERN.match(line)
            if heading:
                flush_paragraph()
                flush_list()
                flush_quote()
                blocks.append(
                    {
                        "type": "heading",
                        "level": min(len(heading.group(1)), 3),
                        "text": heading.group(2).strip(),
                    }
                )
            elif ordered:
                flush_paragraph()
                flush_quote()
                if list_items and list_style != "ordered":
                    flush_list()
                list_style = "ordered"
                list_items.append(ordered.group(2).strip())
            elif bullet:
                flush_paragraph()
                flush_quote()
                if list_items and list_style != "bullet":
                    flush_list()
                list_style = "bullet"
                list_items.append(bullet.group(1).strip())
            elif line.startswith(">"):
                flush_paragraph()
                flush_list()
                quote_lines.append(line.removeprefix(">").strip())
            elif not line:
                flush_paragraph()
                flush_list()
                flush_quote()
            else:
                flush_list()
                flush_quote()
                paragraph_lines.append(line)

        flush_paragraph()
        flush_list()
        flush_quote()

        first_paragraph = next(
            (block for block in blocks if block.get("type") == "paragraph"), None
        )
        if first_paragraph:
            first_paragraph["type"] = "lead"
        return self._with_ids(blocks or [{"type": "paragraph", "text": answer}])

    @staticmethod
    def _image_from_citation(citation: dict[str, Any]) -> dict[str, Any] | None:
        quote = str(citation.get("quote") or "")
        match = re.search(r"图片说明：([^\n]+)", quote)
        caption = match.group(1).strip() if match else "知识库文档中的相关图片"
        heading_path = (citation.get("metadata") or {}).get("heading_path") or []
        return {
            "type": "image",
            "document_id": citation["document_id"],
            "sequence_no": citation["sequence_no"],
            "caption": caption,
            "source_rank": citation.get("rank"),
            "source_label": " / ".join(heading_path[-2:]) or "知识库文档",
            "relation": "direct",
            "alt": caption,
        }

    @staticmethod
    def _source_ranks(text: str) -> list[int]:
        return sorted({int(rank) for rank in SOURCE_PATTERN.findall(text)})

    @staticmethod
    def _with_ids(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{**block, "id": f"block-{index}"} for index, block in enumerate(blocks)]
