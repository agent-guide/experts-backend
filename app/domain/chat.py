from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    title: str | None = None
    knowledgeBaseIds: list[str] = Field(default_factory=list)


class ChatTaskRequest(BaseModel):
    sessionId: str
    question: str
    knowledgeBaseIds: list[str] = Field(default_factory=list)
    llmModel: str | None = None
    queryRewrite: bool | None = None
    multiHop: dict | None = None


class RenameSessionRequest(BaseModel):
    title: str


class PinSessionRequest(BaseModel):
    isPinned: bool = True
