from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.conversations import citations, conversations, messages
from app.crud.knowledge_bases import knowledge_bases
from app.db.models import Conversation, Message
from app.services.errors import ResourceNotFoundError
from app.services.rich_content import RichContentBuilder


@dataclass(frozen=True, slots=True)
class ChatContext:
    conversation: Conversation
    history: list[dict[str, str]]


class ChatService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def start(
        self,
        knowledge_base_id: str,
        question: str,
        conversation_id: str | None = None,
    ) -> ChatContext:
        if await knowledge_bases.get(self.session, knowledge_base_id) is None:
            raise ResourceNotFoundError("知识库不存在")

        conversation: Conversation | None = None
        if conversation_id:
            conversation = await conversations.get(self.session, conversation_id)
            if conversation is None or conversation.knowledge_base_id != knowledge_base_id:
                raise ResourceNotFoundError("对话不存在")
        if conversation is None:
            conversation = await conversations.create(
                self.session,
                knowledge_base_id=knowledge_base_id,
                title=question.strip()[:48] or "新对话",
            )

        history_messages = await messages.list_recent_history(
            self.session, conversation.id, limit=16
        )
        history = [{"role": item.role, "content": item.content} for item in history_messages]
        await messages.create(
            self.session,
            conversation_id=conversation.id,
            role="user",
            content=question.strip(),
        )
        await self.session.commit()
        return ChatContext(conversation=conversation, history=history)

    async def add_related_document_images(
        self,
        builder: RichContentBuilder,
        blocks: list[dict[str, Any]],
        citation_values: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return await builder.add_related_document_images(self.session, blocks, citation_values)

    async def resolve_document_images(
        self,
        builder: RichContentBuilder,
        citation_values: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return await builder.resolve_document_images(self.session, citation_values)

    async def complete(
        self,
        conversation_id: str,
        answer: str,
        content_blocks: list[dict[str, Any]],
        model_name: str,
        citation_values: list[dict[str, Any]],
    ) -> Message:
        assistant_message = await messages.create(
            self.session,
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
            content_blocks=content_blocks,
            model_name=model_name,
        )
        await citations.create_for_message(self.session, assistant_message.id, citation_values)
        await self.session.commit()
        return assistant_message

    async def rollback(self) -> None:
        await self.session.rollback()

    async def list_conversations(self, knowledge_base_id: str | None = None) -> list[Conversation]:
        return await conversations.list_recent(
            self.session, knowledge_base_id=knowledge_base_id, limit=100
        )

    async def get_conversation(self, conversation_id: str) -> Conversation:
        conversation = await conversations.get_detail(self.session, conversation_id)
        if conversation is None:
            raise ResourceNotFoundError("对话不存在")
        return conversation
