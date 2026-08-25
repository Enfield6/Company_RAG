from collections.abc import Mapping
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.db.models import Citation, Conversation, Message


class CRUDConversation(CRUDBase[Conversation]):
    async def list_recent(
        self,
        session: AsyncSession,
        knowledge_base_id: str | None = None,
        limit: int = 100,
    ) -> list[Conversation]:
        statement = select(Conversation).order_by(Conversation.updated_at.desc()).limit(limit)
        if knowledge_base_id:
            statement = statement.where(Conversation.knowledge_base_id == knowledge_base_id)
        result = await session.execute(statement)
        return list(result.scalars())

    async def get_detail(self, session: AsyncSession, conversation_id: str) -> Conversation | None:
        result = await session.execute(
            select(Conversation)
            .options(selectinload(Conversation.messages).selectinload(Message.citations))
            .where(Conversation.id == conversation_id)
        )
        return result.scalar_one_or_none()


class CRUDMessage(CRUDBase[Message]):
    async def list_recent_history(
        self, session: AsyncSession, conversation_id: str, limit: int = 16
    ) -> list[Message]:
        result = await session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        return list(reversed(result.scalars().all()))


class CRUDCitation(CRUDBase[Citation]):
    async def create_for_message(
        self,
        session: AsyncSession,
        message_id: str,
        citation_values: list[Mapping[str, Any]],
    ) -> list[Citation]:
        citations = [
            Citation(
                message_id=message_id,
                document_id=str(item["document_id"]),
                chunk_id=str(item["chunk_id"]),
                rank=int(item["rank"]),
                score=float(item["score"]),
                quote=item.get("quote"),
                citation_metadata={
                    "chunk_type": item.get("chunk_type"),
                    "sequence_no": item.get("sequence_no"),
                    **(item.get("metadata") or {}),
                },
            )
            for item in citation_values
        ]
        session.add_all(citations)
        await session.flush()
        return citations


conversations = CRUDConversation(Conversation)
messages = CRUDMessage(Message)
citations = CRUDCitation(Citation)
