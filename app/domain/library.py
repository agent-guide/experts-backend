from typing import Any, Literal

from pydantic import BaseModel, Field


LibraryFileType = Literal["image", "file"]
LibrarySort = Literal[
    "updatedAt_desc",
    "updatedAt_asc",
    "name_asc",
    "name_desc",
    "size_desc",
    "size_asc",
]
LibraryPreviewType = Literal["url", "text", "unsupported"]


class LibraryFile(BaseModel):
    id: str
    name: str
    mimeType: str | None = None
    type: LibraryFileType
    sizeBytes: int
    sizeLabel: str
    # Lifecycle (docs/LIBRARY_FILE_LIFECYCLE.md §3). expiresAt is set only for temporary files.
    lifecycle: Literal["temporary", "permanent"] = "permanent"
    expiresAt: str | None = None
    updatedAt: str
    createdAt: str
    previewSupported: bool


class LibraryFileListResponse(BaseModel):
    items: list[LibraryFile]
    total: int
    page: int
    pageSize: int


class LibraryUploadUrlRequest(BaseModel):
    fileName: str
    mimeType: str | None = None
    fileSizeBytes: int
    contentHash: str | None = None


class LibraryUploadUrlResponse(BaseModel):
    uploadSessionId: str
    fileId: str
    method: Literal["PUT"] = "PUT"
    uploadUrl: str
    headers: dict[str, str] = Field(default_factory=dict)
    objectKey: str
    expiresAt: str


class LibraryCompleteUploadRequest(BaseModel):
    uploadSessionId: str
    contentHash: str | None = None
    # docs/LIBRARY_FILE_LIFECYCLE.md §7. 'temporary' mints an unbound chat attachment (expires on
    # its retention window, bound to a session on first turn use); 'permanent' is a library file.
    lifecycle: Literal["temporary", "permanent"] = "permanent"


class LibraryDownloadResponse(BaseModel):
    method: Literal["GET"] = "GET"
    downloadUrl: str
    expiresAt: str


class LibraryPreviewResponse(BaseModel):
    previewType: LibraryPreviewType
    url: str | None = None
    content: str | None = None
    mimeType: str | None = None
    expiresAt: str | None = None


class LibraryDeletedResponse(BaseModel):
    id: str
    status: Literal["deleted"] = "deleted"


class LibraryFileRecord(BaseModel):
    id: str
    userId: str
    tenantId: str
    originalName: str
    safeName: str
    mimeType: str | None = None
    fileType: LibraryFileType
    extension: str | None = None
    sizeBytes: int
    storageBucket: str
    storageObjectKey: str
    contentHash: str | None = None
    previewSupported: bool
    metadata: dict[str, Any] = Field(default_factory=dict)
    # Chat temporary-file lifecycle (docs/LIBRARY_FILE_LIFECYCLE.md §3).
    source: Literal["library", "chat_upload"] = "library"
    lifecycle: Literal["temporary", "permanent"] = "permanent"
    expiresAt: str | None = None
    promotedAt: str | None = None
    chatSessionId: str | None = None
    createdAt: str
    updatedAt: str


class LibraryUploadSessionRecord(BaseModel):
    id: str
    fileId: str
    userId: str
    tenantId: str
    originalName: str
    safeName: str
    mimeType: str | None = None
    fileType: LibraryFileType
    extension: str | None = None
    fileSizeBytes: int
    storageBucket: str
    storageObjectKey: str
    contentHash: str | None = None
    status: str
    expiresAt: str
    completedAt: str | None = None
    # Chat-upload routing context (docs/LIBRARY_FILE_LIFECYCLE.md §4). Null for library uploads.
    chatSessionId: str | None = None
    createdAt: str
    updatedAt: str
