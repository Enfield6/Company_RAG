from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import get_health_service
from app.services.health import HealthService

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(
    response: Response,
    service: Annotated[HealthService, Depends(get_health_service)],
) -> dict[str, str]:
    checks = await service.readiness()
    if "down" in checks.values():
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", **checks}
    return {"status": "ok", **checks}
