import re
from collections import defaultdict
from dataclasses import dataclass
from math import sqrt
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.documents import document_elements, documents

SOURCE_PATTERN = re.compile(r"\[来源(\d+)]")
HEADING_PATTERN = re.compile(r"^(#{1,4})\s+(.+)$")
ORDERED_ITEM_PATTERN = re.compile(r"^\s*(\d+)[.)、]\s+(.+)$")
BULLET_ITEM_PATTERN = re.compile(r"^\s*[-*•]\s+(.+)$")
BOLD_HEADING_PATTERN = re.compile(r"^\*\*(?=\S)(.+?\S)\*\*$")
SEMANTIC_TEXT_PATTERN = re.compile(r"[^a-z0-9\u4e00-\u9fff]+")


@dataclass(slots=True)
class _ArticleSection:
    anchor_index: int
    block_indexes: list[int]
    text: str
    source_ranks: set[int]


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
        if images:
            image_document_ids = {
                str(block["document_id"]) for block in images if block.get("document_id")
            }
            valid_image_keys = await document_elements.list_image_keys(
                db, image_document_ids
            )
            images = [
                block
                for block in images
                if (str(block.get("document_id")), block.get("sequence_no"))
                in valid_image_keys
            ]
            valid_block_ids = {str(block.get("id")) for block in images}
            blocks = [
                block
                for block in blocks
                if block.get("type") != "image" or str(block.get("id")) in valid_block_ids
            ]
        used = {(block.get("document_id"), block.get("sequence_no")) for block in images}

        document_ids = {str(item["document_id"]) for item in citations if item.get("document_id")}
        filenames: dict[str, str] = {}
        if document_ids:
            filenames = await documents.get_filenames(db, document_ids)
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
            element = await document_elements.get_nearest_image(
                db, str(document_id), sequence_no
            )
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
                    "anchor_text": " ".join(
                        str(value)
                        for value in (
                            citation.get("quote"),
                            element.image_caption,
                            (element.element_metadata or {}).get("previous_text"),
                            (element.element_metadata or {}).get("next_text"),
                        )
                        if value
                    ),
                }
            )

        return self.insert_images(blocks, related_images)

    def insert_images(
        self, blocks: list[dict[str, Any]], images: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        article_blocks = [block for block in blocks if block.get("type") != "image"]
        all_images: list[dict[str, Any]] = []
        seen: set[tuple[object, object]] = set()
        for image in [
            *(block for block in blocks if block.get("type") == "image"),
            *images,
        ]:
            key = (image.get("document_id"), image.get("sequence_no"))
            if key in seen:
                continue
            seen.add(key)
            all_images.append(image)

        if not all_images or not article_blocks:
            return self._with_ids([*article_blocks, *all_images])

        sections = self._article_sections(article_blocks)
        placements: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for image in all_images:
            anchor = self._best_image_anchor(image, sections, article_blocks)
            placed_image = {
                key: value for key, value in image.items() if key != "anchor_text"
            }
            placements[anchor].append({**placed_image, "placement": "inline"})

        result: list[dict[str, Any]] = []
        for index, block in enumerate(article_blocks):
            result.append(block)
            result.extend(placements.get(index, []))
        return self._with_ids(result)

    def _article_sections(self, blocks: list[dict[str, Any]]) -> list[_ArticleSection]:
        ranges: list[tuple[int, int]] = []
        start = 0
        for index, block in enumerate(blocks):
            if index and block.get("type") == "heading":
                ranges.append((start, index))
                start = index
        ranges.append((start, len(blocks)))

        sections: list[_ArticleSection] = []
        for range_start, range_end in ranges:
            section_blocks = blocks[range_start:range_end]
            body_indexes = [
                index
                for index in range(range_start, range_end)
                if blocks[index].get("type") != "heading"
            ]
            if not body_indexes and len(ranges) > 1:
                continue
            sections.append(
                _ArticleSection(
                    anchor_index=body_indexes[-1] if body_indexes else range_end - 1,
                    block_indexes=body_indexes or [range_end - 1],
                    text=" ".join(self._block_text(block) for block in section_blocks),
                    source_ranks={
                        int(rank)
                        for block in section_blocks
                        for rank in block.get("source_ranks", [])
                    },
                )
            )
        if not sections:
            sections.append(
                _ArticleSection(
                    anchor_index=len(blocks) - 1,
                    block_indexes=[len(blocks) - 1],
                    text=" ".join(self._block_text(block) for block in blocks),
                    source_ranks=set(),
                )
            )
        return sections

    def _best_image_anchor(
        self,
        image: dict[str, Any],
        sections: list[_ArticleSection],
        blocks: list[dict[str, Any]],
    ) -> int:
        image_text = " ".join(
            str(value)
            for value in (image.get("caption"), image.get("anchor_text"))
            if value
        )
        image_units = self._semantic_units(image_text)
        source_rank = image.get("source_rank")

        def score(section: _ArticleSection) -> tuple[float, float]:
            section_units = self._semantic_units(section.text)
            overlap = len(image_units & section_units) / max(1.0, sqrt(len(section_units)))
            source_match = 10.0 if source_rank in section.source_ranks else 0.0
            return source_match + overlap, overlap

        section = max(sections, key=score)

        def block_score(index: int) -> tuple[float, float]:
            block = blocks[index]
            block_units = self._semantic_units(self._block_text(block))
            overlap = len(image_units & block_units) / max(1.0, sqrt(len(block_units)))
            source_match = (
                10.0 if source_rank in set(block.get("source_ranks", [])) else 0.0
            )
            return source_match + overlap, overlap

        best_index = max(section.block_indexes, key=block_score)
        if block_score(best_index) == (0.0, 0.0):
            return section.anchor_index
        return best_index

    @staticmethod
    def _block_text(block: dict[str, Any]) -> str:
        if block.get("type") == "list":
            return " ".join(str(item) for item in block.get("items", []))
        return str(block.get("text") or "")

    @staticmethod
    def _semantic_units(text: str) -> set[str]:
        compact = SEMANTIC_TEXT_PATTERN.sub("", text.lower())
        if len(compact) < 2:
            return {compact} if compact else set()
        return {compact[index : index + 2] for index in range(len(compact) - 1)}

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
            bold_heading = BOLD_HEADING_PATTERN.match(line)
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
            elif bold_heading:
                flush_paragraph()
                flush_list()
                flush_quote()
                blocks.append(
                    {
                        "type": "heading",
                        "level": 3,
                        "text": bold_heading.group(1).strip(),
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
            "anchor_text": quote,
        }

    @staticmethod
    def _source_ranks(text: str) -> list[int]:
        return sorted({int(rank) for rank in SOURCE_PATTERN.findall(text)})

    @staticmethod
    def _with_ids(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{**block, "id": f"block-{index}"} for index, block in enumerate(blocks)]
