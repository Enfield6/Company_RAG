from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import get_knowledge_base_service
from app.schemas.knowledge import KnowledgeBaseCreate, KnowledgeBaseRead
from app.services.knowledge_bases import KnowledgeBaseService, KnowledgeBaseSummary

router = APIRouter(prefix="/knowledge-bases", tags=["Knowledge bases"])


def _to_read(record: KnowledgeBaseSummary) -> KnowledgeBaseRead:
    return KnowledgeBaseRead.model_validate(record.knowledge_base).model_copy(
        update={"document_count": record.document_count}
    )


@router.post("", response_model=KnowledgeBaseRead, status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    service: Annotated[KnowledgeBaseService, Depends(get_knowledge_base_service)],
) -> KnowledgeBaseRead:
    knowledge_base = await service.create(
        name=payload.name,
        description=payload.description,
    )
    return KnowledgeBaseRead.model_validate(knowledge_base)


@router.get("", response_model=list[KnowledgeBaseRead])
async def list_knowledge_bases(
    service: Annotated[KnowledgeBaseService, Depends(get_knowledge_base_service)],
) -> list[KnowledgeBaseRead]:
    return [_to_read(record) for record in await service.list()]


@router.get("/{knowledge_base_id}", response_model=KnowledgeBaseRead)
async def get_knowledge_base(
    knowledge_base_id: str,
    service: Annotated[KnowledgeBaseService, Depends(get_knowledge_base_service)],
) -> KnowledgeBaseRead:
    return _to_read(await service.get(knowledge_base_id))
