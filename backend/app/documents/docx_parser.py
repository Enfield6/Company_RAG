import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from docx import Document as OpenDocument
from docx.document import Document as DocumentObject
from docx.oxml.ns import qn
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.documents.base import append_element, attach_image_neighborhood
from app.documents.types import ParsedElement


class DocxParser:
    """Extract ordered text, tables and images from a DOCX package.

    Images are emitted at the run that owns their OOXML relationship. Nearby
    text is attached after parsing so the logical document neighborhood remains
    available to captioning, embedding and citation rendering.
    """

    def parse(self, path: Path) -> list[ParsedElement]:
        document = OpenDocument(path)
        elements: list[ParsedElement] = []
        heading_stack: list[str] = []

        for block in self._iter_blocks(document):
            if isinstance(block, Paragraph):
                self._parse_paragraph(block, document, heading_stack, elements)
            else:
                self._parse_table(block, document, heading_stack, elements)

        attach_image_neighborhood(elements)
        return elements

    def _parse_paragraph(
        self,
        paragraph: Paragraph,
        document: DocumentObject,
        heading_stack: list[str],
        elements: list[ParsedElement],
    ) -> None:
        paragraph_text = paragraph.text.strip()
        heading_level = self._heading_level(paragraph)
        if heading_level and paragraph_text:
            del heading_stack[heading_level - 1 :]
            while len(heading_stack) < heading_level - 1:
                heading_stack.append("")
            heading_stack.append(paragraph_text)

        pending_text: list[str] = []
        found_image = False
        for run in paragraph.runs:
            if run.text:
                pending_text.append(run.text)

            relationship_ids = self._run_image_relationships(run)
            for relationship_id in relationship_ids:
                found_image = True
                self._flush_text(pending_text, heading_stack, elements)
                alt_text = self._run_alt_text(run)
                image = self._image_element(
                    document,
                    relationship_id,
                    heading_stack,
                    metadata={
                        "source": "paragraph",
                        "style": paragraph.style.name,
                        "alt_text": alt_text,
                    },
                )
                if image:
                    image.image_caption = alt_text
                    self._append(elements, image)

        self._flush_text(pending_text, heading_stack, elements)
        if not found_image and not paragraph.runs and paragraph_text:
            self._append(
                elements,
                ParsedElement(
                    sequence_no=0,
                    kind="text",
                    text=paragraph_text,
                    heading_path=self._clean_heading_path(heading_stack),
                    metadata={"style": paragraph.style.name},
                ),
            )

    def _parse_table(
        self,
        table: Table,
        document: DocumentObject,
        heading_stack: list[str],
        elements: list[ParsedElement],
    ) -> None:
        rows: list[str] = []
        images: list[tuple[str, dict[str, Any]]] = []
        seen_relationships: set[str] = set()
        for row_index, row in enumerate(table.rows):
            cells: list[str] = []
            for column_index, cell in enumerate(row.cells):
                cells.append(
                    " ".join(part.strip() for part in cell.text.splitlines() if part.strip())
                )
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        for relationship_id in self._run_image_relationships(run):
                            if relationship_id not in seen_relationships:
                                seen_relationships.add(relationship_id)
                                images.append(
                                    (
                                        relationship_id,
                                        {
                                            "source": "table",
                                            "table_row": row_index,
                                            "table_column": column_index,
                                            "alt_text": self._run_alt_text(run),
                                        },
                                    )
                                )
            rows.append(" | ".join(cells))

        table_text = "\n".join(row for row in rows if row.strip(" |"))
        if table_text:
            self._append(
                elements,
                ParsedElement(
                    sequence_no=0,
                    kind="table",
                    text=table_text,
                    heading_path=self._clean_heading_path(heading_stack),
                    metadata={"row_count": len(table.rows), "column_count": len(table.columns)},
                ),
            )
        for relationship_id, metadata in images:
            image = self._image_element(document, relationship_id, heading_stack, metadata)
            if image:
                image.image_caption = metadata.get("alt_text", "")
                self._append(elements, image)

    @staticmethod
    def _run_image_relationships(run) -> list[str]:
        relationship_ids = [
            relationship_id
            for blip in run._element.xpath(".//a:blip")
            if (relationship_id := blip.get(qn("r:embed")))
        ]
        relationship_ids.extend(
            relationship_id
            for image_data in run._element.xpath(".//*[local-name()='imagedata']")
            if (relationship_id := image_data.get(qn("r:id")))
        )
        return list(dict.fromkeys(relationship_ids))

    @staticmethod
    def _run_alt_text(run) -> str:
        for property_element in run._element.xpath(".//*[local-name()='docPr']"):
            for attribute in ("descr", "title", "name"):
                value = property_element.get(attribute)
                if value and not value.lower().startswith("picture "):
                    return value.strip()
        return ""

    def _flush_text(
        self,
        pending_text: list[str],
        heading_stack: list[str],
        elements: list[ParsedElement],
    ) -> None:
        text = "".join(pending_text).strip()
        pending_text.clear()
        if text:
            self._append(
                elements,
                ParsedElement(
                    sequence_no=0,
                    kind="text",
                    text=text,
                    heading_path=self._clean_heading_path(heading_stack),
                ),
            )

    @staticmethod
    def _image_element(
        document: DocumentObject,
        relationship_id: str | None,
        heading_stack: list[str],
        metadata: dict[str, Any],
    ) -> ParsedElement | None:
        if not relationship_id:
            return None
        image_part = document.part.related_parts.get(relationship_id)
        if image_part is None or not hasattr(image_part, "blob"):
            return None
        extension = Path(str(getattr(image_part, "partname", "image.bin"))).suffix or ".bin"
        return ParsedElement(
            sequence_no=0,
            kind="image",
            heading_path=DocxParser._clean_heading_path(heading_stack),
            image_bytes=image_part.blob,
            image_extension=extension.lower(),
            image_content_type=getattr(image_part, "content_type", "application/octet-stream"),
            relationship_id=relationship_id,
            metadata=metadata,
        )

    @staticmethod
    def _heading_level(paragraph: Paragraph) -> int | None:
        style_name = paragraph.style.name or ""
        match = re.match(r"(?:Heading|标题)\s*([1-9])", style_name, flags=re.IGNORECASE)
        return int(match.group(1)) if match else None

    @staticmethod
    def _clean_heading_path(headings: list[str]) -> list[str]:
        return [heading for heading in headings if heading]

    @staticmethod
    def _append(elements: list[ParsedElement], element: ParsedElement) -> None:
        append_element(elements, element)

    @staticmethod
    def _iter_blocks(parent: DocumentObject) -> Iterator[Paragraph | Table]:
        for child in parent.element.body.iterchildren():
            if isinstance(child, CT_P):
                yield Paragraph(child, parent)
            elif isinstance(child, CT_Tbl):
                yield Table(child, parent)
