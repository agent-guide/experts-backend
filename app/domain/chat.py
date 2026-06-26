from typing import Literal

from pydantic import BaseModel

ChatSessionStatus = Literal["active", "archived"]


class CreateSessionRequest(BaseModel):
    title: str | None = None


class ChatTurnRequest(BaseModel):
    # The public turn payload is intentionally narrow. Do not re-add model / retrieval options
    # without wiring them into the outgoing ACP payload, or callers will think they take effect.
    question: str


class RenameSessionRequest(BaseModel):
    title: str


class PinSessionRequest(BaseModel):
    isPinned: bool = True


class ArchiveSessionRequest(BaseModel):
    archived: bool = True


class ResolvePermissionRequest(BaseModel):
    # One of outcome/optionId is required.
    outcome: str | None = None
    optionId: str | None = None


class ChatSession(BaseModel):
    id: str
    title: str | None = None
    status: ChatSessionStatus = "active"
    isPinned: bool = False
    createdAt: str
    updatedAt: str


class ChatTurn(BaseModel):
    id: str
    sessionId: str
    requestText: str
    reasoningText: str | None = None
    responseText: str | None = None
    model: str | None = None
    status: str
    stopReason: str | None = None
    errorMessage: str | None = None
    createdAt: str
    completedAt: str | None = None
