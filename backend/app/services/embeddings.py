from langchain_openai import OpenAIEmbeddings


class EmbeddingService:
    def __init__(
        self,
        model_name: str,
        dimension: int,
        base_url: str,
        api_key: str | None,
    ) -> None:
        self._configured = bool(api_key)
        self._model = OpenAIEmbeddings(
            model=model_name,
            dimensions=dimension,
            base_url=base_url,
            api_key=api_key or "missing-qwen-api-key",
            chunk_size=10,
            max_retries=3,
            check_embedding_ctx_length=False,
        )

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self._ensure_configured()
        return await self._model.aembed_documents(texts)

    async def embed_query(self, text: str) -> list[float]:
        self._ensure_configured()
        return await self._model.aembed_query(text)

    def _ensure_configured(self) -> None:
        if not self._configured:
            raise RuntimeError("未配置 QWEN_API_KEY，无法调用通义千问向量模型。")
