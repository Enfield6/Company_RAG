from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.vector_store import MilvusVectorStore


class HealthService:
    def __init__(self, session: AsyncSession, vector_store: MilvusVectorStore) -> None:
        self.session = session
        self.vector_store = vector_store

    async def readiness(self) -> dict[str, str]:
        checks = {"mysql": "down", "milvus": "down"}
        try:
            await self.session.execute(text("SELECT 1"))
            checks["mysql"] = "ok"
        except Exception:
            pass
        if await self.vector_store.ping():
            checks["milvus"] = "ok"
        return checks
