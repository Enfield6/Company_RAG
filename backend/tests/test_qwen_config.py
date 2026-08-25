import pytest

from app.core.config import Settings
from app.services.embeddings import EmbeddingService


def test_qwen_key_is_shared_by_all_model_capabilities() -> None:
    settings = Settings(_env_file=None, qwen_api_key="test-key")

    assert settings.llm_model == "qwen3.5-omni-plus"
    assert settings.vision_model == "qwen3.5-omni-plus"
    assert settings.embedding_model == "text-embedding-v4"
    assert settings.embedding_dimension == 1024
    assert settings.retrieval_min_score == 0.4
    assert settings.resolved_llm_api_key == "test-key"
    assert settings.resolved_vision_api_key == "test-key"
    assert settings.resolved_embedding_api_key == "test-key"


async def test_embedding_service_fails_clearly_without_api_key() -> None:
    service = EmbeddingService(
        model_name="text-embedding-v4",
        dimension=1024,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key=None,
    )

    with pytest.raises(RuntimeError, match="QWEN_API_KEY"):
        await service.embed_query("不会发出网络请求")
