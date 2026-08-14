from dataclasses import dataclass, field
from typing import Any, Literal

ElementKind = Literal["text", "table", "image"]
ChunkKind = Literal["text", "table", "image"]


@dataclass(slots=True)
class ParsedElement:
    sequence_no: int
    kind: ElementKind
    text: str = ""
    heading_path: list[str] = field(default_factory=list)
    image_bytes: bytes | None = None
    image_extension: str | None = None
    image_content_type: str | None = None
    relationship_id: str | None = None
    image_path: str | None = None
    image_caption: str = ""
    image_ocr: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class KnowledgeChunk:
    id: str
    kind: ChunkKind
    content: str
    sequence_no: int
    element_sequences: list[int]
    heading_path: list[str]
    image_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RetrievedChunk:
    id: str
    document_id: str
    content: str
    chunk_type: str
    sequence_no: int
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)
