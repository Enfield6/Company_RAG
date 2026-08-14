from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import Document, KnowledgeBase
from app.db.session import get_db
from app.schemas.knowledge import KnowledgeBaseCreate, KnowledgeBaseRead

router = APIRouter(prefix="/knowledge-bases", tags=["Knowledge bases"])


@router.post("", response_model=KnowledgeBaseRead, status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> KnowledgeBaseRead:
    knowledge_base = KnowledgeBase(
        name=payload.name.strip(),
        description=payload.description,
        embedding_model=settings.embedding_model,
        embedding_dimension=settings.embedding_dimension,
    )
    db.add(knowledge_base)
    await db.commit()
    await db.refresh(knowledge_base)
    return KnowledgeBaseRead.model_validate(knowledge_base)


@router.get("", response_model=list[KnowledgeBaseRead])
async def list_knowledge_bases(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[KnowledgeBaseRead]:
    result = await db.execute(
        select(KnowledgeBase, func.count(Document.id).label("document_count"))
        .outerjoin(Document)
        .group_by(KnowledgeBase.id)
        .order_by(KnowledgeBase.updated_at.desc())
    )
    return [
        KnowledgeBaseRead.model_validate(item).model_copy(update={"document_count": count})
        for item, count in result.all()
    ]


@router.get("/{knowledge_base_id}", response_model=KnowledgeBaseRead)
async def get_knowledge_base(
    knowledge_base_id: str, db: Annotated[AsyncSession, Depends(get_db)]
) -> KnowledgeBaseRead:
    result = await db.execute(
        select(KnowledgeBase, func.count(Document.id).label("document_count"))
        .outerjoin(Document)
        .where(KnowledgeBase.id == knowledge_base_id)
        .group_by(KnowledgeBase.id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="知识库不存在")
    item, count = row
    return KnowledgeBaseRead.model_validate(item).model_copy(update={"document_count": count})
