from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    title: str | None = None
    knowledgeBaseIds: list[str] = Field(default_factory=list)


class ChatTurnRequest(BaseModel):
    # ngent's turn API takes only the prompt text; model / knowledge-base / retrieval
    # options are not forwarded (see ChatService.stream_turn). Do not re-add fields here
    # without wiring them into the outgoing payload, or callers will think they take effect.
    question: str


class RenameSessionRequest(BaseModel):
    title: str


class PinSessionRequest(BaseModel):
    isPinned: bool = True


class ResolvePermissionRequest(BaseModel):
    # Mirrors ngent POST /v1/permissions/{permissionId}: one of outcome/optionId is required.
    outcome: str | None = None
    optionId: str | None = None


class ChatSession(BaseModel):
    id: str
    title: str | None = None
    knowledgeBaseIds: list[str] = Field(default_factory=list)
    isPinned: bool = False
    createdAt: str
    updatedAt: str


class ChatTurn(BaseModel):
    id: str
    sessionId: str
    requestText: str
    responseText: str | None = None
    model: str | None = None
    status: str
    stopReason: str | None = None
    errorMessage: str | None = None
    createdAt: str
    completedAt: str | None = None
