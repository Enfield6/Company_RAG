from datetime import datetime
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    knowledge_base_id: str
    question: str = Field(min_length=1, max_length=8000)
    conversation_id: str | None = None


class CitationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    chunk_id: str
    document_id: str
    rank: int
    score: float
    quote: str | None = None
    chunk_type: str | None = None
    sequence_no: int | None = None
    metadata: dict[str, Any] | None = Field(
        default=None, validation_alias=AliasChoices("citation_metadata", "metadata")
    )


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: str
    content: str
    content_blocks: list[dict[str, Any]] | None = None
    created_at: datetime
    citations: list[CitationRead] = Field(default_factory=list)


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    knowledge_base_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationRead):
    messages: list[MessageRead]
