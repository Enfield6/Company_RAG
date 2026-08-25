from langchain_core.language_models.fake_chat_models import FakeListChatModel

from app.documents.types import RetrievedChunk
from app.graph.rag import AnswerGenerator


async def test_answer_generator_yields_model_chunks_instead_of_waiting_for_full_answer() -> None:
    generator = AnswerGenerator(None, None, "test-model", 0)
    generator._model = FakeListChatModel(responses=["甲乙丙"])
    chunk = RetrievedChunk(
        id="chunk-1",
        document_id="doc-1",
        content="测试资料",
        chunk_type="text",
        sequence_no=1,
        score=0.9,
    )

    parts = [part async for part in generator.stream("测试问题", [], [chunk])]

    assert parts == ["甲", "乙", "丙"]
