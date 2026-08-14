from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_vector_store
from app.db.session import get_db
from app.services.vector_store import MilvusVectorStore

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    vector_store: Annotated[MilvusVectorStore, Depends(get_vector_store)],
) -> dict[str, str]:
    checks = {"mysql": "down", "milvus": "down"}
    try:
        await db.execute(text("SELECT 1"))
        checks["mysql"] = "ok"
    except Exception:
        pass
    if await vector_store.ping():
        checks["milvus"] = "ok"
    if "down" in checks.values():
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", **checks}
    return {"status": "ok", **checks}
