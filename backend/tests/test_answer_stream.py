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


async def test_answer_generator_uses_general_model_when_retrieval_is_empty() -> None:
    generator = AnswerGenerator(None, None, "test-model", 0)
    generator._model = FakeListChatModel(responses=["可以正常回答非工作问题，并给出建议。"])

    parts = [part async for part in generator.stream("周末看什么电影？", [], [])]

    assert "".join(parts) == "可以正常回答非工作问题，并给出建议。"


def test_answer_prompt_requires_intent_aware_actionable_advice() -> None:
    generator = AnswerGenerator(None, None, "test-model", 0)
    system_prompt = generator._prompt.messages[0].prompt.template

    assert "真正想解决" in system_prompt
    assert "非工作问题" in system_prompt
    assert "禁止提及知识库、检索结果或公司资料缺失" in system_prompt
    assert "具体、可执行的后续建议" in system_prompt
    assert "绝不能把通用经验伪装成公司规定" in system_prompt
