import hashlib
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import build_ingestion_service, get_storage
from app.core.config import Settings, get_settings
from app.db.models import Document, DocumentElement, IngestionJob, KnowledgeBase
from app.db.session import get_db
from app.documents.registry import (
    SUPPORTED_DOCUMENT_TYPES,
    content_type_for,
    supported_extensions_label,
)
from app.schemas.knowledge import DocumentRead, UploadAccepted
from app.services.storage import LocalFileStorage

router = APIRouter(tags=["Documents"])


async def _ingest_document(document_id: str) -> None:
    await build_ingestion_service().process(document_id)


@router.post(
    "/knowledge-bases/{knowledge_base_id}/documents",
    response_model=UploadAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    knowledge_base_id: str,
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile, File()],
    db: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    storage: Annotated[LocalFileStorage, Depends(get_storage)],
) -> UploadAccepted:
    knowledge_base = await db.get(KnowledgeBase, knowledge_base_id)
    if not knowledge_base:
        raise HTTPException(status_code=404, detail="知识库不存在")
    filename = file.filename or "document"
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_DOCUMENT_TYPES:
        supported = supported_extensions_label()
        raise HTTPException(
            status_code=415,
            detail=f"不支持 {extension or '无扩展名'} 文件；当前支持：{supported}",
        )
    content = await file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail=f"文件不能超过 {settings.max_upload_mb} MB")
    if not content:
        raise HTTPException(status_code=400, detail="文件为空")

    document = Document(
        knowledge_base_id=knowledge_base_id,
        filename=filename,
        content_type=content_type_for(filename, file.content_type),
        size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        storage_path="pending",
    )
    db.add(document)
    await db.flush()
    document.storage_path = storage.save_document(document.id, filename, content)
    job = IngestionJob(document_id=document.id)
    db.add(job)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        storage.delete_document(document.id)
        raise HTTPException(status_code=409, detail="该知识库中已存在内容相同的文档") from exc
    await db.refresh(document)
    await db.refresh(job)
    background_tasks.add_task(_ingest_document, document.id)
    return UploadAccepted(document=DocumentRead.model_validate(document), job_id=job.id)


@router.get("/knowledge-bases/{knowledge_base_id}/documents", response_model=list[DocumentRead])
async def list_documents(
    knowledge_base_id: str, db: Annotated[AsyncSession, Depends(get_db)]
) -> list[DocumentRead]:
    result = await db.execute(
        select(Document)
        .where(Document.knowledge_base_id == knowledge_base_id)
        .order_by(Document.created_at.desc())
    )
    return [DocumentRead.model_validate(item) for item in result.scalars()]


@router.get("/documents/{document_id}", response_model=DocumentRead)
async def get_document(
    document_id: str, db: Annotated[AsyncSession, Depends(get_db)]
) -> DocumentRead:
    document = await db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
    return DocumentRead.model_validate(document)


@router.get("/documents/{document_id}/elements/{sequence_no}/image")
async def get_document_image(
    document_id: str,
    sequence_no: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[LocalFileStorage, Depends(get_storage)],
) -> FileResponse:
    result = await db.execute(
        select(DocumentElement).where(
            DocumentElement.document_id == document_id,
            DocumentElement.sequence_no == sequence_no,
            DocumentElement.kind == "image",
        )
    )
    element = result.scalar_one_or_none()
    if not element or not element.image_path:
        raise HTTPException(status_code=404, detail="图片不存在")
    path = storage.resolve(element.image_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="图片文件不存在")
    return FileResponse(path)
