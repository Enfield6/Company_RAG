import re
from pathlib import Path

from app.documents.base import append_element
from app.documents.types import ParsedElement


class PlainTextParser:
    def parse(self, path: Path) -> list[ParsedElement]:
        text = decode_text(path.read_bytes())
        elements: list[ParsedElement] = []
        for paragraph in re.split(r"\n\s*\n", text):
            content = paragraph.strip()
            if content:
                append_element(
                    elements,
                    ParsedElement(sequence_no=0, kind="text", text=content),
                )
        return elements


def decode_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "gb18030"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")
