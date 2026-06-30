from typing import Literal

from pydantic import BaseModel, Field

ChatSessionStatus = Literal["active", "archived"]


class CreateSessionRequest(BaseModel):
    title: str | None = None


class ChatTurnRequest(BaseModel):
    # The public turn payload is intentionally narrow. Do not re-add model / retrieval options
    # without wiring them into the outgoing ACP payload, or callers will think they take effect.
    question: str
    webSearchEnabled: bool | None = Field(
        default=None,
        description=(
            "Routes ACP turns to the search prefix with search_mode=auto when true; "
            "otherwise uses the default prefix with search_mode=off."
        ),
    )
    attachmentFileIds: list[str] | None = Field(
        default=None,
        description=(
            "Completed library_files ids referenced by this turn (docs/LIBRARY_FILE_LIFECYCLE.md "
            "§7.3). Each is authorized per §5; a temporary file must belong to this session and not "
            "be expired."
        ),
    )


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
    # Per-turn attachment provenance snapshot (docs/LIBRARY_FILE_LIFECYCLE.md §9). Self-contained,
    # so it survives the referenced file being expired and GC-removed.
    attachments: list[dict] = Field(default_factory=list)
    createdAt: str
    completedAt: str | None = None
