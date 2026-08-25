from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import build_ingestion_service, get_document_service
from app.schemas.knowledge import DocumentRead, UploadAccepted
from app.services.documents import DocumentService

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
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> UploadAccepted:
    filename = file.filename or "document"
    content = await file.read(service.upload_read_limit)
    accepted = await service.create_upload(
        knowledge_base_id=knowledge_base_id,
        filename=filename,
        declared_content_type=file.content_type,
        content=content,
    )
    background_tasks.add_task(_ingest_document, accepted.document.id)
    return UploadAccepted(
        document=DocumentRead.model_validate(accepted.document), job_id=accepted.job.id
    )


@router.get("/knowledge-bases/{knowledge_base_id}/documents", response_model=list[DocumentRead])
async def list_documents(
    knowledge_base_id: str,
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> list[DocumentRead]:
    return [DocumentRead.model_validate(item) for item in await service.list(knowledge_base_id)]


@router.get("/documents/{document_id}", response_model=DocumentRead)
async def get_document(
    document_id: str,
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> DocumentRead:
    return DocumentRead.model_validate(await service.get(document_id))


@router.get("/documents/{document_id}/elements/{sequence_no}/image")
async def get_document_image(
    document_id: str,
    sequence_no: int,
    service: Annotated[DocumentService, Depends(get_document_service)],
) -> FileResponse:
    return FileResponse(await service.get_image_path(document_id, sequence_no))
