import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.api.deps import get_chat_service, get_rag_graph
from app.graph.rag import RAGGraph
from app.schemas.chat import ChatRequest, ConversationDetail, ConversationRead
from app.services.chat import ChatService

router = APIRouter(prefix="/chat", tags=["Chat"])


def _sse(event: str, data: object) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/stream", response_class=StreamingResponse)
async def stream_chat(
    payload: ChatRequest,
    request: Request,
    graph: Annotated[RAGGraph, Depends(get_rag_graph)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> StreamingResponse:
    context = await service.start(
        knowledge_base_id=payload.knowledge_base_id,
        question=payload.question,
        conversation_id=payload.conversation_id,
    )

    async def event_stream() -> AsyncIterator[str]:
        yield _sse("meta", {"conversation_id": context.conversation.id})
        yield _sse("status", {"stage": "retrieving", "message": "正在检索文字与相关图片"})
        try:
            result = await graph.ask(payload.question, payload.knowledge_base_id, context.history)
            answer = result.get("answer", "")
            citations = result.get("citations", [])
            rich_blocks = await service.add_related_document_images(
                graph.rich_content, result.get("rich_blocks", []), citations
            )
            yield _sse("status", {"stage": "composing", "message": "正在组织图文回答"})

            media_blocks = [block for block in rich_blocks if block.get("type") == "image"]
            emitted_media = 0
            for index in range(0, len(answer), 12):
                if await request.is_disconnected():
                    return
                yield _sse("token", {"content": answer[index : index + 12]})
                progress = (index + 12) / max(len(answer), 1)
                threshold = 0.18 + emitted_media * 0.38
                if emitted_media < len(media_blocks) and progress >= threshold:
                    yield _sse("media", media_blocks[emitted_media])
                    emitted_media += 1
                await asyncio.sleep(0)
            for media_block in media_blocks[emitted_media:]:
                yield _sse("media", media_block)

            yield _sse("rich", {"blocks": rich_blocks})

            assistant_message = await service.complete(
                conversation_id=context.conversation.id,
                answer=answer,
                content_blocks=rich_blocks,
                model_name=graph.answer_generator.model_name,
                citation_values=citations,
            )
            yield _sse("citations", citations)
            yield _sse("done", {"message_id": assistant_message.id})
        except Exception as exc:
            await service.rollback()
            yield _sse("error", {"message": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/conversations", response_model=list[ConversationRead])
async def list_conversations(
    service: Annotated[ChatService, Depends(get_chat_service)],
    knowledge_base_id: str | None = None,
) -> list[ConversationRead]:
    return [
        ConversationRead.model_validate(item)
        for item in await service.list_conversations(knowledge_base_id)
    ]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str,
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> ConversationDetail:
    return ConversationDetail.model_validate(await service.get_conversation(conversation_id))
