from fastapi import APIRouter, Depends

from app.api.deps import get_database, require_platform_permission
from app.core.errors import ApiError
from app.db import DatabaseConnection
from app.domain.auth import Principal
from app.domain.knowledge import BuildRequest
from app.services.kb_authz import KbAction, authorize_kb_access
from app.services.knowledge_base_repository import KnowledgeBaseRepository

# Mounted under /knowledge-bases/{knowledge_base_id} (see app/api/v1/router.py).
#
# Phase 2 placeholder: these endpoints only reserve the route + contract. They create no
# build records and write no snapshot. Build details are intentionally deferred until the
# shape is settled; for now a knowledge base only exposes whether it is usable via its status.
# The real build worker/provider lands in a later phase (design sections 4.3 / 8 / 9).
#
# Even as a placeholder the resource semantics are honoured: the knowledge base must exist (404)
# and, for build actions, not be archived (409) -- only then is 501 returned. Returning 501 for a
# missing knowledge base would let callers probe arbitrary ids.
router = APIRouter()

_STUB_STATUS = 501


def _require_kb(connection: DatabaseConnection, principal: Principal, kb_id: str, action: KbAction):
    kb = KnowledgeBaseRepository(connection).get(kb_id)
    if not kb:
        raise ApiError(404, "KB_NOT_FOUND", "Knowledge base not found")
    authorize_kb_access(principal, kb, action)


def _not_implemented(knowledge_base_id: str) -> dict:
    return {
        "status": "not_implemented",
        "knowledgeBaseId": knowledge_base_id,
        "message": "Build is not implemented yet; this endpoint is a placeholder.",
    }


@router.post("/build", status_code=_STUB_STATUS)
async def trigger_build(
    knowledge_base_id: str,
    body: BuildRequest,
    principal: Principal = Depends(require_platform_permission("kb:build")),
    connection: DatabaseConnection = Depends(get_database),
) -> dict:
    _require_kb(connection, principal, knowledge_base_id, "build")
    return _not_implemented(knowledge_base_id)


@router.get("/builds", status_code=_STUB_STATUS)
async def list_builds(
    knowledge_base_id: str,
    principal: Principal = Depends(require_platform_permission("kb:read")),
    connection: DatabaseConnection = Depends(get_database),
) -> dict:
    _require_kb(connection, principal, knowledge_base_id, "read")
    return _not_implemented(knowledge_base_id)


@router.get("/builds/{build_id}", status_code=_STUB_STATUS)
async def get_build(
    knowledge_base_id: str,
    build_id: str,
    principal: Principal = Depends(require_platform_permission("kb:read")),
    connection: DatabaseConnection = Depends(get_database),
) -> dict:
    _require_kb(connection, principal, knowledge_base_id, "read")
    return _not_implemented(knowledge_base_id)


@router.post("/builds/{build_id}/cancel", status_code=_STUB_STATUS)
async def cancel_build(
    knowledge_base_id: str,
    build_id: str,
    principal: Principal = Depends(require_platform_permission("kb:build")),
    connection: DatabaseConnection = Depends(get_database),
) -> dict:
    _require_kb(connection, principal, knowledge_base_id, "build")
    return _not_implemented(knowledge_base_id)
