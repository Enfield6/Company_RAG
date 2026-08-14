from pathlib import Path

from app.documents.base import DocumentParser
from app.documents.docx_parser import DocxParser
from app.documents.markdown_parser import MarkdownParser
from app.documents.office_converter import OfficeConverter
from app.documents.pdf_parser import PdfParser
from app.documents.pptx_parser import PptxParser
from app.documents.text_parser import PlainTextParser
from app.documents.types import ParsedElement

SUPPORTED_DOCUMENT_TYPES: dict[str, str] = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".pdf": "application/pdf",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".ppt": "application/vnd.ms-powerpoint",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".txt": "text/plain",
}


class DocumentParserRegistry:
    def __init__(self, office_converter: OfficeConverter | None = None) -> None:
        self.office_converter = office_converter or OfficeConverter()
        self.parsers: dict[str, DocumentParser] = {
            ".docx": DocxParser(),
            ".pdf": PdfParser(),
            ".pptx": PptxParser(self.office_converter),
            ".md": MarkdownParser(),
            ".markdown": MarkdownParser(),
            ".txt": PlainTextParser(),
        }

    def parse(self, path: Path) -> list[ParsedElement]:
        extension = path.suffix.lower()
        if extension == ".doc":
            with self.office_converter.convert(path, ".docx") as converted:
                return self._parse_with(".docx", converted, path.name)
        if extension == ".ppt":
            with self.office_converter.convert(path, ".pptx") as converted:
                return self._parse_with(".pptx", converted, path.name)
        return self._parse_with(extension, path, path.name)

    def _parse_with(
        self,
        extension: str,
        path: Path,
        original_name: str,
    ) -> list[ParsedElement]:
        parser = self.parsers.get(extension)
        if parser is None:
            raise ValueError(f"不支持的文档格式：{extension or '无扩展名'}")
        elements = parser.parse(path)
        if not elements:
            raise ValueError(f"没有从 {original_name} 中提取到可索引的文字或图片。")
        return elements


def supported_extensions_label() -> str:
    return "、".join(SUPPORTED_DOCUMENT_TYPES)


def content_type_for(filename: str, supplied: str | None) -> str:
    extension = Path(filename).suffix.lower()
    if supplied and supplied != "application/octet-stream":
        return supplied
    return SUPPORTED_DOCUMENT_TYPES.get(extension, supplied or "application/octet-stream")
