from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_ngent_client, require_tenant_permission
from app.clients.ngent import NgentClient
from app.domain.auth import Principal
from app.domain.chat import ChatTaskRequest, CreateSessionRequest, PinSessionRequest, RenameSessionRequest

router = APIRouter()


@router.post("/sessions", status_code=201)
async def create_session(
    body: CreateSessionRequest,
    principal: Principal = Depends(require_tenant_permission("chat:ask")),
    ngent: NgentClient = Depends(get_ngent_client),
) -> dict:
    data = await ngent.request(
        "POST",
        "/v1/threads",
        tenant_id=principal.active_tenant_id,
        json={
            "agent": ngent.default_agent,
            "cwd": ngent.default_cwd,
            "title": body.title,
            "agentOptions": {"knowledgeBaseIds": body.knowledgeBaseIds},
        },
    )
    return {
        "id": data["threadId"],
        "title": body.title,
        "knowledgeBaseIds": body.knowledgeBaseIds,
    }


@router.get("/sessions")
async def list_sessions(
    principal: Principal = Depends(require_tenant_permission("chat:ask")),
    ngent: NgentClient = Depends(get_ngent_client),
) -> dict:
    data = await ngent.request("GET", "/v1/threads", tenant_id=principal.active_tenant_id)
    return {"items": [_thread_to_session(item) for item in data.get("threads", [])]}


@router.get("/sessions/{session_id}/messages")
async def list_messages(
    session_id: str,
    principal: Principal = Depends(require_tenant_permission("chat:ask")),
    ngent: NgentClient = Depends(get_ngent_client),
) -> dict:
    data = await ngent.request(
        "GET",
        f"/v1/threads/{session_id}/history?includeEvents=1",
        tenant_id=principal.active_tenant_id,
    )
    return {"items": data.get("turns", [])}


@router.patch("/sessions/{session_id}/title")
async def rename_session(
    session_id: str,
    body: RenameSessionRequest,
    principal: Principal = Depends(require_tenant_permission("chat:ask")),
    ngent: NgentClient = Depends(get_ngent_client),
) -> dict:
    data = await ngent.request(
        "PATCH",
        f"/v1/threads/{session_id}",
        tenant_id=principal.active_tenant_id,
        json={"title": body.title},
    )
    return _thread_to_session(data["thread"])


@router.patch("/sessions/{session_id}/pin")
async def pin_session(
    session_id: str,
    body: PinSessionRequest,
    _: Principal = Depends(require_tenant_permission("chat:ask")),
) -> dict:
    return {"id": session_id, "isPinned": body.isPinned}


@router.post("/tasks", status_code=202)
async def create_chat_task(
    body: ChatTaskRequest,
    principal: Principal = Depends(require_tenant_permission("chat:ask")),
    ngent: NgentClient = Depends(get_ngent_client),
) -> dict:
    data = await ngent.request(
        "POST",
        f"/v1/threads/{body.sessionId}/turns",
        tenant_id=principal.active_tenant_id,
        json={
            "prompt": {"text": body.question},
            "stream": True,
            "agentOptions": {
                "modelId": body.llmModel,
                "knowledgeBaseIds": body.knowledgeBaseIds,
                "queryRewrite": body.queryRewrite,
                "multiHop": body.multiHop,
            },
        },
    )
    return {
        "taskId": data.get("turnId"),
        "status": data.get("status", "queued"),
        "queuePosition": None,
    }


@router.post("/tasks/{task_id}/cancel")
async def cancel_chat_task(
    task_id: str,
    principal: Principal = Depends(require_tenant_permission("chat:ask")),
    ngent: NgentClient = Depends(get_ngent_client),
) -> dict:
    data = await ngent.request(
        "POST", f"/v1/turns/{task_id}/cancel", tenant_id=principal.active_tenant_id
    )
    return {"taskId": task_id, "status": data.get("status", "cancel_requested")}


@router.get("/tasks/{task_id}/position")
async def chat_task_position(task_id: str, _: Principal = Depends(require_tenant_permission("chat:ask"))) -> dict:
    return {"taskId": task_id, "position": None, "queueDepth": None}


@router.get("/tasks/{task_id}/events")
async def chat_task_events(
    task_id: str,
    principal: Principal = Depends(require_tenant_permission("chat:ask")),
    ngent: NgentClient = Depends(get_ngent_client),
) -> StreamingResponse:
    tenant_id = principal.active_tenant_id

    async def events():
        async for line in ngent.stream(
            "GET", f"/v1/turns/{task_id}/events", tenant_id=tenant_id
        ):
            yield f"{line}\n"

    return StreamingResponse(events(), media_type="text/event-stream")


def _thread_to_session(thread: dict) -> dict:
    return {
        "id": thread.get("threadId"),
        "title": thread.get("title"),
        "knowledgeBaseIds": thread.get("agentOptions", {}).get("knowledgeBaseIds", []),
        "createdAt": thread.get("createdAt"),
        "updatedAt": thread.get("updatedAt"),
        "isPinned": False,
    }
