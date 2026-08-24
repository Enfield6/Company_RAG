from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Company Knowledge AI"
    app_env: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    mysql_dsn: str = "mysql+asyncmy://company_rag:change-me@localhost:3306/company_rag"

    milvus_uri: str = "http://localhost:19530"
    milvus_token: str | None = None
    milvus_collection: str = "company_knowledge_chunks"
    qwen_api_key: str | None = None
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    embedding_base_url: str | None = None
    embedding_api_key: str | None = None
    embedding_model: str = "text-embedding-v4"
    embedding_dimension: int = 1024

    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str = "qwen3.5-omni-plus"
    llm_temperature: float = 0.1

    vision_base_url: str | None = None
    vision_api_key: str | None = None
    vision_model: str | None = "qwen3.5-omni-plus"
    image_enrichment_concurrency: int = Field(default=4, ge=1, le=8)

    upload_dir: Path = Path("storage/uploads")
    max_upload_mb: int = 100
    chunk_size: int = 900
    chunk_overlap: int = 120
    retrieval_top_k: int = 6

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def resolved_embedding_base_url(self) -> str:
        return self.embedding_base_url or self.dashscope_base_url

    @property
    def resolved_embedding_api_key(self) -> str | None:
        return self.embedding_api_key or self.qwen_api_key

    @property
    def resolved_llm_base_url(self) -> str:
        return self.llm_base_url or self.dashscope_base_url

    @property
    def resolved_llm_api_key(self) -> str | None:
        return self.llm_api_key or self.qwen_api_key

    @property
    def resolved_vision_base_url(self) -> str:
        return self.vision_base_url or self.dashscope_base_url

    @property
    def resolved_vision_api_key(self) -> str | None:
        return self.vision_api_key or self.qwen_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
