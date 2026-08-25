from app.documents.types import RetrievedChunk
from app.graph.rag import AnswerGenerator, RAGGraph


class FakeEmbeddings:
    async def embed_query(self, _question: str) -> list[float]:
        return [0.1, 0.2]


class FakeVectorStore:
    async def search(self, _knowledge_base_id: str, _vector: list[float], _top_k: int):
        return [
            RetrievedChunk(
                id="relevant",
                document_id="doc-1",
                content="卡机入库流程",
                chunk_type="text",
                sequence_no=1,
                score=0.71,
            ),
            RetrievedChunk(
                id="irrelevant",
                document_id="doc-1",
                content="与电影推荐无关的公司资料",
                chunk_type="text",
                sequence_no=2,
                score=0.18,
            ),
        ]


async def test_rag_filters_irrelevant_company_context_before_answering() -> None:
    graph = RAGGraph(
        FakeEmbeddings(),
        FakeVectorStore(),
        AnswerGenerator(None, None, "test-model", 0),
        top_k=6,
        min_relevance_score=0.4,
    )

    chunks = await graph.retrieve("周末看什么电影？", "kb-1")

    assert [chunk.id for chunk in chunks] == ["relevant"]
    assert graph.min_relevance_score == 0.4
