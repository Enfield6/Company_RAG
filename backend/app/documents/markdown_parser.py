import re
from pathlib import Path

from app.documents.base import append_element
from app.documents.text_parser import decode_text
from app.documents.types import ParsedElement

HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


class MarkdownParser:
    """Preserve Markdown headings while storing render-independent plain text."""

    def parse(self, path: Path) -> list[ParsedElement]:
        lines = decode_text(path.read_bytes()).splitlines()
        elements: list[ParsedElement] = []
        heading_stack: list[str] = []
        buffer: list[str] = []
        fenced = False

        def flush() -> None:
            text = "\n".join(buffer).strip()
            buffer.clear()
            if not text:
                return
            def image_label(match: re.Match[str]) -> str:
                alt_text = match.group(1) or "无说明"
                return f"[Markdown 图片：{alt_text}，地址：{match.group(2)}]"

            text = IMAGE_PATTERN.sub(
                image_label,
                text,
            )
            append_element(
                elements,
                ParsedElement(
                    sequence_no=0,
                    kind="text",
                    text=text,
                    heading_path=[item for item in heading_stack if item],
                    metadata={"source": "markdown"},
                ),
            )

        for line in lines:
            if line.lstrip().startswith("```") or line.lstrip().startswith("~~~"):
                fenced = not fenced
                buffer.append(line)
                continue
            match = HEADING_PATTERN.match(line) if not fenced else None
            if match:
                flush()
                level = len(match.group(1))
                title = match.group(2).strip()
                del heading_stack[level - 1 :]
                while len(heading_stack) < level - 1:
                    heading_stack.append("")
                heading_stack.append(title)
                append_element(
                    elements,
                    ParsedElement(
                        sequence_no=0,
                        kind="text",
                        text=title,
                        heading_path=[item for item in heading_stack if item],
                        metadata={"source": "markdown", "heading_level": level},
                    ),
                )
            elif not line.strip() and not fenced:
                flush()
            else:
                buffer.append(line)
        flush()
        return elements
