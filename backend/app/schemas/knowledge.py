from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)


class KnowledgeBaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    is_active: bool
    embedding_model: str
    embedding_dimension: int
    document_count: int = 0
    created_at: datetime
    updated_at: datetime


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    knowledge_base_id: str
    filename: str
    content_type: str
    size_bytes: int
    status: str
    element_count: int
    chunk_count: int
    error_message: str | None
    processed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class UploadAccepted(BaseModel):
    document: DocumentRead
    job_id: str
