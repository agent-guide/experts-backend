from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.api.deps import (
    get_acp_admin_client,
    get_acp_gateway_client,
    get_database,
    get_ngent_client,
    require_tenant_permission,
)
from app.clients.acp_admin import AcpAdminClient
from app.clients.acp_gateway import AcpGatewayClient
from app.clients.ngent import NgentClient
from app.core.config import Settings, get_settings
from app.db import DatabaseConnection
from app.db import open_database_connection
from app.domain.auth import Principal
from app.domain.chat import (
    ArchiveSessionRequest,
    ChatTurnRequest,
    CreateSessionRequest,
    PinSessionRequest,
    RenameSessionRequest,
    ResolvePermissionRequest,
)
from app.services.chat_service import ChatService

router = APIRouter()


def build_chat_service(
    connection: DatabaseConnection,
    settings: Settings,
    ngent: NgentClient,
    acp: AcpGatewayClient,
    acp_admin: AcpAdminClient,
) -> ChatService:
    return ChatService(
        connection,
        backend=settings.chat_backend,
        ngent=ngent,
        acp=acp,
        acp_admin=acp_admin,
    )


def get_chat_service(
    connection: DatabaseConnection = Depends(get_database),
    settings: Settings = Depends(get_settings),
    ngent: NgentClient = Depends(get_ngent_client),
    acp: AcpGatewayClient = Depends(get_acp_gateway_client),
    acp_admin: AcpAdminClient = Depends(get_acp_admin_client),
) -> ChatService:
    return build_chat_service(connection, settings, ngent, acp, acp_admin)


# --- Sessions -----------------------------------------------------------------


@router.post("/sessions", status_code=201)
async def create_session(
    body: CreateSessionRequest,
    principal: Principal = Depends(require_tenant_permission("chat:ask")),
    service: ChatService = Depends(get_chat_service),
) -> dict:
    return (await service.create_session(principal, body)).model_dump()


@router.get("/sessions")
async def list_sessions(
    status: str = Query(default="active", pattern="^(active|archived)$"),
    principal: Principal = Depends(require_tenant_permission("chat:ask")),
    service: ChatService = Depends(get_chat_service),
) -> dict:
    return {"items": [s.model_dump() for s in service.list_sessions(principal, status)]}


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    principal: Principal = Depends(require_tenant_permission("chat:ask")),
    service: ChatService = Depends(get_chat_service),
) -> dict:
    return service.get_session(principal, session_id).model_dump()


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    principal: Principal = Depends(require_tenant_permission("chat:ask")),
    service: ChatService = Depends(get_chat_service),
) -> dict:
    await service.delete_session(principal, session_id)
    return {"id": session_id, "status": "deleted"}


@router.get("/sessions/{session_id}/messages")
async def list_messages(
    session_id: str,
    principal: Principal = Depends(require_tenant_permission("chat:ask")),
    service: ChatService = Depends(get_chat_service),
) -> dict:
    return {"items": service.list_messages(principal, session_id)}


@router.get("/sessions/{session_id}/transcript")
async def get_transcript(
    session_id: str,
    principal: Principal = Depends(require_tenant_permission("chat:ask")),
    service: ChatService = Depends(get_chat_service),
) -> dict:
    # History replay: the agent-side transcript (ACP admin plane) when available, else the
    # durable local turn records. Shape: {sessionId, messages: [{role, text}], source}.
    return await service.get_transcript(principal, session_id)


@router.patch("/sessions/{session_id}/title")
async def rename_session(
    session_id: str,
    body: RenameSessionRequest,
    principal: Principal = Depends(require_tenant_permission("chat:ask")),
    service: ChatService = Depends(get_chat_service),
) -> dict:
    return (await service.rename_session(principal, session_id, body.title)).model_dump()


@router.patch("/sessions/{session_id}/pin")
async def pin_session(
    session_id: str,
    body: PinSessionRequest,
    principal: Principal = Depends(require_tenant_permission("chat:ask")),
    service: ChatService = Depends(get_chat_service),
) -> dict:
    return service.pin_session(principal, session_id, body.isPinned).model_dump()


@router.patch("/sessions/{session_id}/archive")
def archive_session(
    session_id: str,
    body: ArchiveSessionRequest,
    principal: Principal = Depends(require_tenant_permission("chat:ask")),
    service: ChatService = Depends(get_chat_service),
) -> dict:
    return service.archive_session(principal, session_id, body.archived).model_dump()


# --- Turns --------------------------------------------------------------------


@router.post("/sessions/{session_id}/turns")
async def create_turn(
    session_id: str,
    body: ChatTurnRequest,
    principal: Principal = Depends(require_tenant_permission("chat:ask")),
    settings: Settings = Depends(get_settings),
    ngent: NgentClient = Depends(get_ngent_client),
    acp: AcpGatewayClient = Depends(get_acp_gateway_client),
    acp_admin: AcpAdminClient = Depends(get_acp_admin_client),
) -> StreamingResponse:
    # The compute engine creates and streams a turn in one shot; the service forwards the SSE
    # stream to the caller while persisting the assembled turn record locally (translating ACP
    # events to the same public contract when the ACP backend is active).
    async def events():
        with open_database_connection(settings) as connection:
            service = build_chat_service(connection, settings, ngent, acp, acp_admin)
            async for line in service.stream_turn(principal, session_id, body):
                yield line

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
    )


@router.post("/turns/{turn_id}/cancel")
async def cancel_turn(
    turn_id: str,
    principal: Principal = Depends(require_tenant_permission("chat:ask")),
    service: ChatService = Depends(get_chat_service),
) -> dict:
    return await service.cancel_turn(principal, turn_id)


@router.get("/turns/{turn_id}/events")
async def turn_events(
    turn_id: str,
    principal: Principal = Depends(require_tenant_permission("chat:ask")),
    service: ChatService = Depends(get_chat_service),
    after: int | None = Query(default=None, ge=0),
) -> StreamingResponse:
    # Replay + live stream. `after` resumes from a given event seq for reconnects.
    events = await service.stream_turn_events(principal, turn_id, after)
    return StreamingResponse(events, media_type="text/event-stream")


@router.post("/permissions/{permission_id}")
async def resolve_permission(
    permission_id: str,
    body: ResolvePermissionRequest,
    principal: Principal = Depends(require_tenant_permission("chat:ask")),
    service: ChatService = Depends(get_chat_service),
) -> dict:
    # Resolves a `permission_required` event raised mid-turn (e.g. tool approval).
    return await service.resolve_permission(principal, permission_id, body)
