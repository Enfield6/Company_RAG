import hashlib
import logging
from collections import Counter
from pathlib import Path
from typing import Any

import pymupdf

from app.documents.base import append_element, attach_image_neighborhood
from app.documents.types import ParsedElement

logger = logging.getLogger(__name__)


class PdfParser:
    """Extract text and embedded page images in their visual reading order."""

    def parse(self, path: Path) -> list[ParsedElement]:
        elements: list[ParsedElement] = []
        with pymupdf.open(path) as document:
            if document.needs_pass:
                raise ValueError("PDF 已加密，请先移除打开密码后再上传。")
            for page_index, page in enumerate(document):
                page_number = page_index + 1
                page_path = [f"第 {page_number} 页"]
                page_dict = page.get_text("dict", sort=True)
                usable_images = 0
                page_text = ""
                blocks = sorted(
                    page_dict.get("blocks", []),
                    key=lambda block: self._block_sort_key(block),
                )
                image_digests = Counter(
                    digest
                    for block in blocks
                    if block.get("type") == 1 and self._is_usable_image(block)
                    if (digest := self._image_digest(block))
                )
                repeated_asset_digests = {
                    digest for digest, count in image_digests.items() if count >= 3
                }
                seen_image_digests: set[str] = set()
                suppressed_images = 0
                for block_index, block in enumerate(blocks):
                    if block.get("type") == 0:
                        text = self._text_from_block(block)
                        if not text:
                            continue
                        page_text += text
                        append_element(
                            elements,
                            ParsedElement(
                                sequence_no=0,
                                kind="text",
                                text=text,
                                heading_path=page_path,
                                metadata={
                                    "source": "pdf",
                                    "page_number": page_number,
                                    "bbox": list(block.get("bbox", ())),
                                },
                            ),
                        )
                    elif block.get("type") == 1 and self._is_usable_image(block):
                        image_bytes = block.get("image")
                        if not isinstance(image_bytes, bytes):
                            continue
                        digest = hashlib.sha256(image_bytes).hexdigest()
                        if digest in repeated_asset_digests:
                            suppressed_images += 1
                            continue
                        if digest in seen_image_digests:
                            suppressed_images += 1
                            continue
                        seen_image_digests.add(digest)
                        extension = str(block.get("ext") or "png").lower().lstrip(".")
                        usable_images += 1
                        append_element(
                            elements,
                            ParsedElement(
                                sequence_no=0,
                                kind="image",
                                heading_path=page_path,
                                image_bytes=image_bytes,
                                image_extension=f".{extension}",
                                image_content_type=self._content_type(extension),
                                relationship_id=f"page-{page_number}-block-{block_index}",
                                metadata={
                                    "source": "pdf",
                                    "page_number": page_number,
                                    "bbox": list(block.get("bbox", ())),
                                    "width": block.get("width"),
                                    "height": block.get("height"),
                                    "sha256": digest,
                                },
                            ),
                        )
                if suppressed_images:
                    logger.info(
                        "PDF page %s ignored %s repeated image assets",
                        page_number,
                        suppressed_images,
                    )
                if not page_text.strip() and not usable_images:
                    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False)
                    append_element(
                        elements,
                        ParsedElement(
                            sequence_no=0,
                            kind="image",
                            heading_path=page_path,
                            image_bytes=pixmap.tobytes("png"),
                            image_extension=".png",
                            image_content_type="image/png",
                            relationship_id=f"page-{page_number}-render",
                            metadata={
                                "source": "pdf_page_render",
                                "page_number": page_number,
                                "scan_fallback": True,
                            },
                        ),
                    )
        attach_image_neighborhood(elements)
        return elements

    @staticmethod
    def _block_sort_key(block: dict[str, Any]) -> tuple[float, float]:
        bbox = block.get("bbox") or (0, 0, 0, 0)
        return float(bbox[1]), float(bbox[0])

    @staticmethod
    def _text_from_block(block: dict[str, Any]) -> str:
        lines: list[str] = []
        for line in block.get("lines", []):
            text = "".join(str(span.get("text", "")) for span in line.get("spans", [])).strip()
            if text:
                lines.append(text)
        return "\n".join(lines).strip()

    @staticmethod
    def _is_usable_image(block: dict[str, Any]) -> bool:
        width = int(block.get("width") or 0)
        height = int(block.get("height") or 0)
        return width >= 24 and height >= 24 and bool(block.get("image"))

    @staticmethod
    def _image_digest(block: dict[str, Any]) -> str | None:
        image_bytes = block.get("image")
        if not isinstance(image_bytes, bytes):
            return None
        return hashlib.sha256(image_bytes).hexdigest()

    @staticmethod
    def _content_type(extension: str) -> str:
        return {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp",
            "gif": "image/gif",
            "bmp": "image/bmp",
            "tif": "image/tiff",
            "tiff": "image/tiff",
        }.get(extension, "application/octet-stream")
