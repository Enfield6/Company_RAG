import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_rag_graph
from app.db.models import Citation, Conversation, KnowledgeBase, Message
from app.db.session import get_db
from app.graph.rag import RAGGraph
from app.schemas.chat import ChatRequest, ConversationDetail, ConversationRead

router = APIRouter(prefix="/chat", tags=["Chat"])


def _sse(event: str, data: object) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/stream", response_class=StreamingResponse)
async def stream_chat(
    payload: ChatRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    graph: Annotated[RAGGraph, Depends(get_rag_graph)],
) -> StreamingResponse:
    knowledge_base = await db.get(KnowledgeBase, payload.knowledge_base_id)
    if not knowledge_base:
        raise HTTPException(status_code=404, detail="知识库不存在")

    conversation: Conversation | None = None
    if payload.conversation_id:
        conversation = await db.get(Conversation, payload.conversation_id)
        if not conversation or conversation.knowledge_base_id != payload.knowledge_base_id:
            raise HTTPException(status_code=404, detail="对话不存在")
    if not conversation:
        conversation = Conversation(
            knowledge_base_id=payload.knowledge_base_id,
            title=payload.question.strip()[:48] or "新对话",
        )
        db.add(conversation)
        await db.flush()

    history_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .limit(16)
    )
    history_messages = list(reversed(history_result.scalars().all()))
    history = [{"role": item.role, "content": item.content} for item in history_messages]

    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=payload.question.strip(),
    )
    db.add(user_message)
    await db.commit()

    async def event_stream() -> AsyncIterator[str]:
        yield _sse("meta", {"conversation_id": conversation.id})
        yield _sse("status", {"stage": "retrieving", "message": "正在检索文字与相关图片"})
        try:
            result = await graph.ask(payload.question, payload.knowledge_base_id, history)
            answer = result.get("answer", "")
            citations = result.get("citations", [])
            rich_blocks = await graph.rich_content.add_related_document_images(
                db, result.get("rich_blocks", []), citations
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

            assistant_message = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=answer,
                content_blocks=rich_blocks,
                model_name=graph.answer_generator.model_name,
            )
            db.add(assistant_message)
            await db.flush()
            db.add_all(
                [
                    Citation(
                        message_id=assistant_message.id,
                        document_id=item["document_id"],
                        chunk_id=item["chunk_id"],
                        rank=item["rank"],
                        score=item["score"],
                        quote=item.get("quote"),
                        citation_metadata={
                            "chunk_type": item.get("chunk_type"),
                            "sequence_no": item.get("sequence_no"),
                            **(item.get("metadata") or {}),
                        },
                    )
                    for item in citations
                ]
            )
            await db.commit()
            yield _sse("citations", citations)
            yield _sse("done", {"message_id": assistant_message.id})
        except Exception as exc:
            await db.rollback()
            yield _sse("error", {"message": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/conversations", response_model=list[ConversationRead])
async def list_conversations(
    db: Annotated[AsyncSession, Depends(get_db)],
    knowledge_base_id: str | None = None,
) -> list[ConversationRead]:
    statement = select(Conversation).order_by(Conversation.updated_at.desc()).limit(100)
    if knowledge_base_id:
        statement = statement.where(Conversation.knowledge_base_id == knowledge_base_id)
    result = await db.execute(statement)
    return [ConversationRead.model_validate(item) for item in result.scalars()]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str, db: Annotated[AsyncSession, Depends(get_db)]
) -> ConversationDetail:
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages).selectinload(Message.citations))
        .where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="对话不存在")
    return ConversationDetail.model_validate(conversation)
