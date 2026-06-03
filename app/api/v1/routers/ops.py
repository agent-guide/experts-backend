from fastapi import APIRouter, Depends

from app.api.deps import require_platform_permission
from app.domain.auth import Principal

router = APIRouter()


@router.get("/metrics")
async def metrics(_: Principal = Depends(require_platform_permission("system:ops"))) -> dict:
    return {
        "counters": {},
        "gauges": {},
        "derived": {"external": {"pageIndexConfigured": False, "ngentConfigured": False}},
    }
