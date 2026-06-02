from typing import Any, Literal

from pydantic import BaseModel, Field


Visibility = Literal["private", "tenant_public", "official_public"]


class CreateKnowledgeBaseRequest(BaseModel):
    name: str
    description: str | None = None
    visibility: Visibility = "private"
    defaultChunkStrategy: str | None = None
    defaultChunkConfig: dict[str, Any] = Field(default_factory=dict)


class UpdateKnowledgeBaseRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    visibility: Visibility | None = None
    defaultChunkStrategy: str | None = None
    defaultChunkConfig: dict[str, Any] | None = None


class InitiateUploadRequest(BaseModel):
    knowledgeBaseId: str
    fileName: str
    fileSizeBytes: int
    contentType: str | None = None


class CompleteUploadRequest(BaseModel):
    uploadSessionId: str
    etag: str | None = None
    fileSizeBytes: int | None = None


class MultipartPartsRequest(BaseModel):
    uploadSessionId: str
    partNumbers: list[int]


class CompleteMultipartRequest(BaseModel):
    uploadSessionId: str
    parts: list[dict]
    etag: str | None = None
    fileSizeBytes: int | None = None


class AbortMultipartRequest(BaseModel):
    uploadSessionId: str
