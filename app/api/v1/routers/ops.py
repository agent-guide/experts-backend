from fastapi import APIRouter, Depends

from app.api.deps import (
    get_database,
    get_object_store,
    get_settings,
    require_platform_permission,
)
from app.core.config import Settings
from app.db import DatabaseConnection
from app.domain.auth import Principal
from app.services.document_service import DocumentService
from app.services.object_store import ObjectStore

router = APIRouter()


@router.get("/metrics")
async def metrics(_: Principal = Depends(require_platform_permission("system:ops"))) -> dict:
    return {
        "counters": {},
        "gauges": {},
        "derived": {"external": {"pageIndexConfigured": False, "ngentConfigured": False}},
    }


@router.post("/storage/gc")
async def run_storage_gc(
    _: Principal = Depends(require_platform_permission("system:ops")),
    connection: DatabaseConnection = Depends(get_database),
    object_store: ObjectStore = Depends(get_object_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Run the object-storage garbage collection passes and report what each reclaimed.

    The reclamation methods on DocumentService are otherwise only reachable from code; this is the
    operational entry point (call it from a cron via the `system:ops` permission). Each pass is
    idempotent and best-effort by object key, so repeated runs are safe and a partial failure is
    retried on the next call. See KNOWLEDGE_BASE_STORAGE_AND_BUILD_DESIGN.md section 11.
    """
    service = DocumentService(connection, object_store, settings)
    return {
        "expiredSessions": service.expire_stale_sessions(),
        "purgedDocuments": service.purge_deleted_objects(),
        "purgedKnowledgeBases": service.purge_deleted_knowledge_bases(),
    }
