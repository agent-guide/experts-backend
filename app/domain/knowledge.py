from typing import Any, Literal

from pydantic import BaseModel, Field


# A knowledge base has a single lifecycle status. `active` means it is usable; `archived`
# means it is retired and rejects writes. Build readiness is intentionally NOT modeled yet:
# build is deferred, and a separate field would only add another status to reconcile.
KbStatus = Literal["active", "archived"]
FileType = Literal["pdf", "docx", "pptx", "xlsx", "md", "txt", "html", "csv", "json"]
ParseStatus = Literal["pending", "processing", "ready", "failed"]
IndexStatus = Literal["pending", "processing", "ready", "failed", "stale"]


# Knowledge bases -----------------------------------------------------------------


class CreateKnowledgeBaseRequest(BaseModel):
    name: str
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateKnowledgeBaseRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    metadata: dict[str, Any] | None = None


class KnowledgeBase(BaseModel):
    id: str
    # Creator attribution only. Access is governed by platform permissions, not ownership.
    ownerUserId: str | None = None
    ownerUserName: str | None = None
    name: str
    description: str | None = None
    status: KbStatus
    metadata: dict[str, Any] = Field(default_factory=dict)
    createdAt: str
    updatedAt: str


class KnowledgeBaseListResponse(BaseModel):
    items: list[KnowledgeBase]


# Documents -----------------------------------------------------------------------


class Document(BaseModel):
    id: str
    knowledgeBaseId: str
    fileName: str
    fileType: FileType
    mimeType: str | None = None
    fileSizeBytes: int
    storageKey: str
    contentHash: str | None = None
    parseStatus: ParseStatus
    indexStatus: IndexStatus
    metadata: dict[str, Any] = Field(default_factory=dict)
    createdAt: str
    updatedAt: str


class DocumentListResponse(BaseModel):
    items: list[Document]


class UpdateDocumentRequest(BaseModel):
    fileName: str | None = None
    metadata: dict[str, Any] | None = None


# Upload flow ---------------------------------------------------------------------


class UploadUrlRequest(BaseModel):
    fileName: str
    mimeType: str | None = None
    fileSizeBytes: int
    contentHash: str | None = None


class UploadUrlResponse(BaseModel):
    uploadSessionId: str
    documentId: str
    method: Literal["PUT"] = "PUT"
    uploadUrl: str
    headers: dict[str, str] = Field(default_factory=dict)
    objectKey: str
    expiresAt: str


class UploadUrlsRequest(BaseModel):
    files: list[UploadUrlRequest] = Field(min_length=1, max_length=50)


class UploadUrlsResponse(BaseModel):
    items: list[UploadUrlResponse]


class CompleteUploadRequest(BaseModel):
    uploadSessionId: str
    etag: str | None = None
    fileSizeBytes: int | None = None


class CompleteUploadsRequest(BaseModel):
    items: list[CompleteUploadRequest] = Field(min_length=1, max_length=50)


class CompleteUploadsResponse(BaseModel):
    items: list[Document]


class DownloadUrlResponse(BaseModel):
    method: Literal["GET"] = "GET"
    downloadUrl: str
    expiresAt: str


# Build (Phase 2 placeholder) -----------------------------------------------------


class BuildRequest(BaseModel):
    force: bool = False
    documentIds: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
