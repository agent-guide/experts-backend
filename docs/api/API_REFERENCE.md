# Amazon Experts Backend API

Version: `0.1.0`

This document is generated from the FastAPI OpenAPI schema.

## auth

### POST `/api/v1/auth/login`

- Summary: Login

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| body | application/json | yes | LoginRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | object |
| 422 | application/json | HTTPValidationError |

### POST `/api/v1/auth/logout`

- Summary: Logout

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| body | application/json | yes | LogoutRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 204 | - | Successful Response |
| 422 | application/json | HTTPValidationError |

### POST `/api/v1/auth/refresh`

- Summary: Refresh

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| body | application/json | yes | RefreshRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | object |
| 422 | application/json | HTTPValidationError |

## builds

### POST `/api/v1/knowledge-bases/{knowledge_base_id}/build`

- Summary: Trigger Build

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | knowledge_base_id | yes | string | - |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | BuildRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 501 | application/json | object |
| 422 | application/json | HTTPValidationError |

### GET `/api/v1/knowledge-bases/{knowledge_base_id}/builds`

- Summary: List Builds

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | knowledge_base_id | yes | string | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 501 | application/json | object |
| 422 | application/json | HTTPValidationError |

### GET `/api/v1/knowledge-bases/{knowledge_base_id}/builds/{build_id}`

- Summary: Get Build

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | knowledge_base_id | yes | string | - |
| path | build_id | yes | string | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 501 | application/json | object |
| 422 | application/json | HTTPValidationError |

### POST `/api/v1/knowledge-bases/{knowledge_base_id}/builds/{build_id}/cancel`

- Summary: Cancel Build

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | knowledge_base_id | yes | string | - |
| path | build_id | yes | string | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 501 | application/json | object |
| 422 | application/json | HTTPValidationError |

## chat

### POST `/api/v1/chat/permissions/{permission_id}`

- Summary: Resolve Permission

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | permission_id | yes | string | - |
| header | x-tenant-id | no | string \| null | - |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | ResolvePermissionRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | object |
| 422 | application/json | HTTPValidationError |

### GET `/api/v1/chat/sessions`

- Summary: List Sessions

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| query | status | no | string | - |
| header | x-tenant-id | no | string \| null | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | object |
| 422 | application/json | HTTPValidationError |

### POST `/api/v1/chat/sessions`

- Summary: Create Session

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| header | x-tenant-id | no | string \| null | - |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | CreateSessionRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 201 | application/json | object |
| 422 | application/json | HTTPValidationError |

### DELETE `/api/v1/chat/sessions/{session_id}`

- Summary: Delete Session

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | session_id | yes | string | - |
| header | x-tenant-id | no | string \| null | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | object |
| 422 | application/json | HTTPValidationError |

### GET `/api/v1/chat/sessions/{session_id}`

- Summary: Get Session

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | session_id | yes | string | - |
| header | x-tenant-id | no | string \| null | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | object |
| 422 | application/json | HTTPValidationError |

### PATCH `/api/v1/chat/sessions/{session_id}/archive`

- Summary: Archive Session

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | session_id | yes | string | - |
| header | x-tenant-id | no | string \| null | - |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | ArchiveSessionRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | object |
| 422 | application/json | HTTPValidationError |

### GET `/api/v1/chat/sessions/{session_id}/messages`

- Summary: List Messages

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | session_id | yes | string | - |
| header | x-tenant-id | no | string \| null | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | object |
| 422 | application/json | HTTPValidationError |

### PATCH `/api/v1/chat/sessions/{session_id}/pin`

- Summary: Pin Session

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | session_id | yes | string | - |
| header | x-tenant-id | no | string \| null | - |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | PinSessionRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | object |
| 422 | application/json | HTTPValidationError |

### PATCH `/api/v1/chat/sessions/{session_id}/title`

- Summary: Rename Session

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | session_id | yes | string | - |
| header | x-tenant-id | no | string \| null | - |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | RenameSessionRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | object |
| 422 | application/json | HTTPValidationError |

### GET `/api/v1/chat/sessions/{session_id}/transcript`

- Summary: Get Transcript

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | session_id | yes | string | - |
| header | x-tenant-id | no | string \| null | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | object |
| 422 | application/json | HTTPValidationError |

### POST `/api/v1/chat/sessions/{session_id}/turns`

- Summary: Create Turn

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | session_id | yes | string | - |
| header | x-tenant-id | no | string \| null | - |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | ChatTurnRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | - |
| 422 | application/json | HTTPValidationError |

### POST `/api/v1/chat/turns/{turn_id}/cancel`

- Summary: Cancel Turn

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | turn_id | yes | string | - |
| header | x-tenant-id | no | string \| null | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | object |
| 422 | application/json | HTTPValidationError |

### GET `/api/v1/chat/turns/{turn_id}/events`

- Summary: Turn Events

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | turn_id | yes | string | - |
| query | after | no | integer \| null | - |
| header | x-tenant-id | no | string \| null | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | - |
| 422 | application/json | HTTPValidationError |

## docs

### GET `/api/v1/knowledge-bases/{knowledge_base_id}/docs`

- Summary: List Documents

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | knowledge_base_id | yes | string | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | DocumentListResponse |
| 422 | application/json | HTTPValidationError |

### POST `/api/v1/knowledge-bases/{knowledge_base_id}/docs/complete-upload`

- Summary: Complete Upload

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | knowledge_base_id | yes | string | - |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | CompleteUploadRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 201 | application/json | Document |
| 422 | application/json | HTTPValidationError |

### POST `/api/v1/knowledge-bases/{knowledge_base_id}/docs/complete-uploads`

- Summary: Complete Uploads

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | knowledge_base_id | yes | string | - |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | CompleteUploadsRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | CompleteUploadsResponse |
| 422 | application/json | HTTPValidationError |

### POST `/api/v1/knowledge-bases/{knowledge_base_id}/docs/upload-url`

- Summary: Create Upload Url

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | knowledge_base_id | yes | string | - |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | UploadUrlRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | UploadUrlResponse |
| 422 | application/json | HTTPValidationError |

### POST `/api/v1/knowledge-bases/{knowledge_base_id}/docs/upload-urls`

- Summary: Create Upload Urls

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | knowledge_base_id | yes | string | - |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | UploadUrlsRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | UploadUrlsResponse |
| 422 | application/json | HTTPValidationError |

### DELETE `/api/v1/knowledge-bases/{knowledge_base_id}/docs/{document_id}`

- Summary: Delete Document

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | knowledge_base_id | yes | string | - |
| path | document_id | yes | string | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 204 | - | Successful Response |
| 422 | application/json | HTTPValidationError |

### GET `/api/v1/knowledge-bases/{knowledge_base_id}/docs/{document_id}`

- Summary: Get Document

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | knowledge_base_id | yes | string | - |
| path | document_id | yes | string | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | Document |
| 422 | application/json | HTTPValidationError |

### PATCH `/api/v1/knowledge-bases/{knowledge_base_id}/docs/{document_id}`

- Summary: Update Document

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | knowledge_base_id | yes | string | - |
| path | document_id | yes | string | - |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | UpdateDocumentRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | Document |
| 422 | application/json | HTTPValidationError |

### GET `/api/v1/knowledge-bases/{knowledge_base_id}/docs/{document_id}/download-url`

- Summary: Get Download Url

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | knowledge_base_id | yes | string | - |
| path | document_id | yes | string | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | DownloadUrlResponse |
| 422 | application/json | HTTPValidationError |

## expert-categories

### GET `/api/v1/expert-categories`

- Summary: List Expert Categories

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | ExpertCategoryListResponse |
| 422 | application/json | HTTPValidationError |

### POST `/api/v1/expert-categories`

- Summary: Create Expert Category

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | CreateExpertCategoryRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 201 | application/json | ExpertCategory |
| 422 | application/json | HTTPValidationError |

### DELETE `/api/v1/expert-categories/{category_id}`

- Summary: Delete Expert Category

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | category_id | yes | string | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 204 | - | Successful Response |
| 422 | application/json | HTTPValidationError |

### GET `/api/v1/expert-categories/{category_id}`

- Summary: Get Expert Category

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | category_id | yes | string | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | ExpertCategory |
| 422 | application/json | HTTPValidationError |

### PATCH `/api/v1/expert-categories/{category_id}`

- Summary: Update Expert Category

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | category_id | yes | string | - |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | UpdateExpertCategoryRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | ExpertCategory |
| 422 | application/json | HTTPValidationError |

## expert-market

### GET `/api/v1/expert-market/categories`

- Summary: List Market Categories

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | ExpertMarketCategoryListResponse |
| 422 | application/json | HTTPValidationError |

### GET `/api/v1/expert-market/experts`

- Summary: List Market Experts

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| query | categoryId | no | string \| null | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | ExpertMarketExpertListResponse |
| 422 | application/json | HTTPValidationError |

### GET `/api/v1/expert-market/experts/{expert_id}`

- Summary: Get Market Expert

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | expert_id | yes | string | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | ExpertMarketExpert |
| 422 | application/json | HTTPValidationError |

## experts

### GET `/api/v1/experts`

- Summary: List Experts

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| query | name | no | string \| null | - |
| query | categoryId | no | string \| null | - |
| query | status | no | string \| null | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | ExpertListResponse |
| 422 | application/json | HTTPValidationError |

### POST `/api/v1/experts`

- Summary: Create Expert

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | CreateExpertRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 201 | application/json | Expert |
| 422 | application/json | HTTPValidationError |

### GET `/api/v1/experts/stats/summary`

- Summary: Get Expert Stats

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | ExpertStatsResponse |
| 422 | application/json | HTTPValidationError |

### DELETE `/api/v1/experts/{expert_id}`

- Summary: Delete Expert

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | expert_id | yes | string | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 204 | - | Successful Response |
| 422 | application/json | HTTPValidationError |

### GET `/api/v1/experts/{expert_id}`

- Summary: Get Expert

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | expert_id | yes | string | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | Expert |
| 422 | application/json | HTTPValidationError |

### PATCH `/api/v1/experts/{expert_id}`

- Summary: Update Expert

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | expert_id | yes | string | - |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | UpdateExpertRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | Expert |
| 422 | application/json | HTTPValidationError |

### PATCH `/api/v1/experts/{expert_id}/status`

- Summary: Update Expert Status

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | expert_id | yes | string | - |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | UpdateExpertStatusRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | Expert |
| 422 | application/json | HTTPValidationError |

## health

### GET `/health`

- Summary: Health check

#### Input Parameters

No input parameters.

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | object |

## knowledge-bases

### GET `/api/v1/knowledge-bases`

- Summary: List Knowledge Bases

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | KnowledgeBaseListResponse |
| 422 | application/json | HTTPValidationError |

### POST `/api/v1/knowledge-bases`

- Summary: Create Knowledge Base

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | CreateKnowledgeBaseRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 201 | application/json | KnowledgeBase |
| 422 | application/json | HTTPValidationError |

### DELETE `/api/v1/knowledge-bases/{knowledge_base_id}`

- Summary: Delete Knowledge Base

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | knowledge_base_id | yes | string | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 204 | - | Successful Response |
| 422 | application/json | HTTPValidationError |

### GET `/api/v1/knowledge-bases/{knowledge_base_id}`

- Summary: Get Knowledge Base

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | knowledge_base_id | yes | string | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | KnowledgeBase |
| 422 | application/json | HTTPValidationError |

### PATCH `/api/v1/knowledge-bases/{knowledge_base_id}`

- Summary: Update Knowledge Base

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | knowledge_base_id | yes | string | - |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | UpdateKnowledgeBaseRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | KnowledgeBase |
| 422 | application/json | HTTPValidationError |

## library

### GET `/api/v1/library/files`

- Summary: List Files

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| query | keyword | no | string \| null | - |
| query | type | no | string | - |
| query | page | no | integer | - |
| query | pageSize | no | integer | - |
| query | sort | no | string | - |
| header | x-tenant-id | no | string \| null | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | LibraryFileListResponse |
| 422 | application/json | HTTPValidationError |

### POST `/api/v1/library/files`

- Summary: Upload File

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| header | x-tenant-id | no | string \| null | - |
| header | Authorization | no | string \| null | - |
| body | multipart/form-data | yes | Body_upload_file_api_v1_library_files_post | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 201 | application/json | LibraryFile |
| 422 | application/json | HTTPValidationError |

### DELETE `/api/v1/library/files/{file_id}`

- Summary: Delete File

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | file_id | yes | string | - |
| header | x-tenant-id | no | string \| null | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | LibraryDeletedResponse |
| 422 | application/json | HTTPValidationError |

### GET `/api/v1/library/files/{file_id}/download`

- Summary: Download File

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | file_id | yes | string | - |
| header | x-tenant-id | no | string \| null | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | LibraryDownloadResponse |
| 422 | application/json | HTTPValidationError |

### GET `/api/v1/library/files/{file_id}/preview`

- Summary: Preview File

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | file_id | yes | string | - |
| header | x-tenant-id | no | string \| null | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | LibraryPreviewResponse |
| 422 | application/json | HTTPValidationError |

## models

### GET `/api/v1/models/embedding`

- Summary: Get Embedding Model

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| header | x-tenant-id | no | string \| null | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | object |
| 422 | application/json | HTTPValidationError |

### GET `/api/v1/models/llm`

- Summary: List Llm Models

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| header | x-tenant-id | no | string \| null | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | object |
| 422 | application/json | HTTPValidationError |

## ops

### GET `/api/v1/ops/metrics`

- Summary: Metrics

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | object |
| 422 | application/json | HTTPValidationError |

### POST `/api/v1/ops/storage/gc`

- Summary: Run Storage Gc
- Description: Run the object-storage garbage collection passes and report what each reclaimed.

The reclamation methods on DocumentService are otherwise only reachable from code; this is the
operational entry point (call it from a cron via the `system:ops` permission). Each pass is
idempotent and best-effort by object key, so repeated runs are safe and a partial failure is
retried on the next call. See KNOWLEDGE_BASE_STORAGE_AND_BUILD_DESIGN.md section 11.

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | object |
| 422 | application/json | HTTPValidationError |

## plan-market

### GET `/api/v1/plan-market/current-subscription`

- Summary: Get Current Subscription

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | CurrentSubscriptionResponse |
| 422 | application/json | HTTPValidationError |

### GET `/api/v1/plan-market/plans`

- Summary: List Market Plans

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | PlanListResponse |
| 422 | application/json | HTTPValidationError |

## plans

### GET `/api/v1/plans`

- Summary: List Plans

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | PlanListResponse |
| 422 | application/json | HTTPValidationError |

### POST `/api/v1/plans`

- Summary: Create Plan

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | CreatePlanRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 201 | application/json | Plan |
| 422 | application/json | HTTPValidationError |

### DELETE `/api/v1/plans/{plan_id}`

- Summary: Delete Plan

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | plan_id | yes | string | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 204 | - | Successful Response |
| 422 | application/json | HTTPValidationError |

### GET `/api/v1/plans/{plan_id}`

- Summary: Get Plan

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | plan_id | yes | string | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | Plan |
| 422 | application/json | HTTPValidationError |

### PATCH `/api/v1/plans/{plan_id}`

- Summary: Update Plan

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | plan_id | yes | string | - |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | UpdatePlanRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | Plan |
| 422 | application/json | HTTPValidationError |

### PUT `/api/v1/plans/{plan_id}/entitlements`

- Summary: Replace Plan Entitlements

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | plan_id | yes | string | - |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | ReplacePlanEntitlementsRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | Plan |
| 422 | application/json | HTTPValidationError |

### PUT `/api/v1/plans/{plan_id}/experts`

- Summary: Replace Plan Experts

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | plan_id | yes | string | - |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | ReplacePlanExpertsRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | Plan |
| 422 | application/json | HTTPValidationError |

### PUT `/api/v1/plans/{plan_id}/prices`

- Summary: Replace Plan Prices

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | plan_id | yes | string | - |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | ReplacePlanPricesRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | Plan |
| 422 | application/json | HTTPValidationError |

## rbac

### GET `/api/v1/rbac/platform/roles`

- Summary: List Platform Roles

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | ListPlatformRolesResponse |
| 422 | application/json | HTTPValidationError |

### POST `/api/v1/rbac/platform/users/{user_id}/roles`

- Summary: Grant Platform Role

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | user_id | yes | string | - |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | GrantPlatformRoleRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 204 | - | Successful Response |
| 422 | application/json | HTTPValidationError |

### DELETE `/api/v1/rbac/platform/users/{user_id}/roles/{role}`

- Summary: Revoke Platform Role

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | user_id | yes | string | - |
| path | role | yes | PlatformRole | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 204 | - | Successful Response |
| 422 | application/json | HTTPValidationError |

### GET `/api/v1/rbac/tenant/users`

- Summary: List Tenant Users

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| header | x-tenant-id | no | string \| null | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | ListUsersResponse |
| 422 | application/json | HTTPValidationError |

### DELETE `/api/v1/rbac/tenant/users/{user_id}`

- Summary: Revoke Tenant Member

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | user_id | yes | string | - |
| header | x-tenant-id | no | string \| null | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 204 | - | Successful Response |
| 422 | application/json | HTTPValidationError |

### POST `/api/v1/rbac/tenant/users/{user_id}/roles`

- Summary: Grant Tenant Role

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | user_id | yes | string | - |
| header | x-tenant-id | no | string \| null | - |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | GrantTenantRoleRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 204 | - | Successful Response |
| 422 | application/json | HTTPValidationError |

## skills

### GET `/api/v1/skills`

- Summary: List Skills

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| query | tags | no | array[string] | - |
| query | search | no | string \| null | - |
| query | limit | no | integer | - |
| query | offset | no | integer | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | SkillListResponse |
| 422 | application/json | HTTPValidationError |

### POST `/api/v1/skills`

- Summary: Upload Skill

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| header | Authorization | no | string \| null | - |
| body | multipart/form-data | yes | Body_upload_skill_api_v1_skills_post | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 201 | application/json | Skill |
| 422 | application/json | HTTPValidationError |

### DELETE `/api/v1/skills/{slug}`

- Summary: Delete Skill

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | slug | yes | string | - |
| query | delete_files | no | boolean | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 204 | - | Successful Response |
| 422 | application/json | HTTPValidationError |

### GET `/api/v1/skills/{slug}`

- Summary: Get Skill

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | slug | yes | string | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | Skill |
| 422 | application/json | HTTPValidationError |

### PUT `/api/v1/skills/{slug}`

- Summary: Update Skill

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | slug | yes | string | - |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | SkillMetadataUpdate | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | Skill |
| 422 | application/json | HTTPValidationError |

### GET `/api/v1/skills/{slug}/file`

- Summary: Get Skill File

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | slug | yes | string | - |
| query | path | no | string | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | - |
| 422 | application/json | HTTPValidationError |

## storage

### GET `/api/v1/storage/objects/{token}`

- Summary: Get Object

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | token | yes | string | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | - |
| 422 | application/json | HTTPValidationError |

### PUT `/api/v1/storage/objects/{token}`

- Summary: Put Object

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | token | yes | string | - |
| header | content-type | no | string \| null | - |
| header | content-length | no | integer \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 204 | - | Successful Response |
| 422 | application/json | HTTPValidationError |

## tenants

### GET `/api/v1/tenants`

- Summary: List Tenants

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| query | search | no | string \| null | - |
| query | type | no | string \| null | - |
| query | subscriptionType | no | string \| null | - |
| query | subscriptionStatus | no | string \| null | - |
| query | sort | no | string \| null | - |
| query | page | no | integer | - |
| query | pageSize | no | integer | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | TenantListResponse |
| 422 | application/json | HTTPValidationError |

### POST `/api/v1/tenants`

- Summary: Create Tenant

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | CreateTenantRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 201 | application/json | Tenant |
| 422 | application/json | HTTPValidationError |

### GET `/api/v1/tenants/{tenant_id}`

- Summary: Get Tenant

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | tenant_id | yes | string | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | Tenant |
| 422 | application/json | HTTPValidationError |

### PATCH `/api/v1/tenants/{tenant_id}`

- Summary: Update Tenant

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | tenant_id | yes | string | - |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | UpdateTenantRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | Tenant |
| 422 | application/json | HTTPValidationError |

### GET `/api/v1/tenants/{tenant_id}/members`

- Summary: List Tenant Members

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | tenant_id | yes | string | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | TenantMemberListResponse |
| 422 | application/json | HTTPValidationError |

### POST `/api/v1/tenants/{tenant_id}/members`

- Summary: Add Tenant Member

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | tenant_id | yes | string | - |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | AddTenantMemberRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 201 | application/json | TenantMember |
| 422 | application/json | HTTPValidationError |

### DELETE `/api/v1/tenants/{tenant_id}/members/{user_id}`

- Summary: Remove Tenant Member

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | tenant_id | yes | string | - |
| path | user_id | yes | string | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 204 | - | Successful Response |
| 422 | application/json | HTTPValidationError |

### PATCH `/api/v1/tenants/{tenant_id}/members/{user_id}`

- Summary: Update Tenant Member

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | tenant_id | yes | string | - |
| path | user_id | yes | string | - |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | UpdateTenantMemberRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | TenantMember |
| 422 | application/json | HTTPValidationError |

### PATCH `/api/v1/tenants/{tenant_id}/status`

- Summary: Update Tenant Status

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | tenant_id | yes | string | - |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | UpdateTenantStatusRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | Tenant |
| 422 | application/json | HTTPValidationError |

### PATCH `/api/v1/tenants/{tenant_id}/subscription`

- Summary: Update Tenant Subscription

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | tenant_id | yes | string | - |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | UpdateTenantSubscriptionRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | Tenant |
| 422 | application/json | HTTPValidationError |

## users

### GET `/api/v1/users`

- Summary: List Users

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| query | search | no | string \| null | - |
| query | subscriptionStatus | no | string \| null | - |
| query | subscriptionType | no | string \| null | - |
| query | sort | no | string \| null | - |
| query | page | no | integer | - |
| query | pageSize | no | integer | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | ListManagedUsersResponse |
| 422 | application/json | HTTPValidationError |

### GET `/api/v1/users/platform`

- Summary: List Platform Users

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | ListUsersResponse |
| 422 | application/json | HTTPValidationError |

### POST `/api/v1/users/platform`

- Summary: Create Platform User

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | CreatePlatformUserRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 201 | application/json | CreatePlatformUserResponse |
| 422 | application/json | HTTPValidationError |

### POST `/api/v1/users/platform/activate`

- Summary: Activate Platform User

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| body | application/json | yes | PlatformUserActivateRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | object |
| 422 | application/json | HTTPValidationError |

### POST `/api/v1/users/register`

- Summary: Register

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| body | application/json | yes | RegisterRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 201 | application/json | object |
| 422 | application/json | HTTPValidationError |

### GET `/api/v1/users/{user_id}`

- Summary: Get User

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | user_id | yes | string | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | UserDetail |
| 422 | application/json | HTTPValidationError |

### PATCH `/api/v1/users/{user_id}`

- Summary: Update User

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | user_id | yes | string | - |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | UpdateUserRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | UserDetail |
| 422 | application/json | HTTPValidationError |

### PATCH `/api/v1/users/{user_id}/status`

- Summary: Update User Status

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | user_id | yes | string | - |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | UpdateUserStatusRequest | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | UserDetail |
| 422 | application/json | HTTPValidationError |

### GET `/api/v1/users/{user_id}/tenants`

- Summary: List User Tenants

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | user_id | yes | string | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | ListUserTenantsResponse |
| 422 | application/json | HTTPValidationError |

## Schemas

### `AddTenantMemberRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| userId | yes | string | - |
| role | no | TenantRole | - |

### `ArchiveSessionRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| archived | no | boolean | - |

### `BatchItemError`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| code | yes | string | - |
| message | yes | string | - |
| details | no | object | - |

### `Body_upload_file_api_v1_library_files_post`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| file | yes | string | - |

### `Body_upload_skill_api_v1_skills_post`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| file | yes | string | - |
| slug | no | string \| null | - |

### `BuildRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| force | no | boolean | - |
| documentIds | no | array[string] | - |
| config | no | object | - |

### `ChatTurnRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| question | yes | string | - |
| webSearchEnabled | no | boolean \| null | Routes ACP turns to the search prefix with search_mode=auto when true; otherwise uses the default prefix with search_mode=off. |

### `CompleteUploadRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| uploadSessionId | yes | string | - |
| etag | no | string \| null | - |
| fileSizeBytes | no | integer \| null | - |

### `CompleteUploadResult`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| uploadSessionId | yes | string | - |
| status | yes | string | - |
| document | no | Document \| null | - |
| error | no | BatchItemError \| null | - |

### `CompleteUploadsRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| items | yes | array[CompleteUploadRequest] | - |

### `CompleteUploadsResponse`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| items | yes | array[CompleteUploadResult] | - |

### `CreateExpertCategoryRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| name | yes | string | - |
| description | no | string \| null | - |

### `CreateExpertRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| name | yes | string | - |
| categoryId | yes | string | - |
| abilityIntro | yes | string | - |
| tags | no | array[string] | - |
| status | no | string | - |
| skillIds | no | array[string] | - |
| knowledgeBaseIds | no | array[string] | - |
| guideQuestions | no | array[string] | - |
| summonButtonText | no | string \| null | - |

### `CreateKnowledgeBaseRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| name | yes | string | - |
| description | no | string \| null | - |
| metadata | no | object | - |

### `CreatePlanRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| code | no | string \| null | - |
| name | yes | string | - |
| level | yes | integer | - |
| description | yes | string | - |
| typeLabel | no | string \| null | - |
| subtitle | no | string \| null | - |
| badgeLabel | no | string \| null | - |
| highlightItems | no | array[string] | - |
| upgradeRules | no | object | - |
| status | no | string | - |
| isRecommended | no | boolean | - |
| sortOrder | no | integer | - |

### `CreatePlatformUserRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| email | yes | string | - |
| name | yes | string | - |
| roles | no | array[PlatformRole] | - |

### `CreatePlatformUserResponse`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| id | yes | string | - |
| email | yes | string | - |
| name | yes | string | - |
| status | yes | string | - |
| platformRoles | yes | array[PlatformRole] | - |
| activationToken | yes | string | - |
| activationExpiresAt | yes | string | - |

### `CreateSessionRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| title | no | string \| null | - |

### `CreateTenantRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| name | yes | string | - |
| slug | no | string \| null | - |
| ownerUserId | yes | string | - |

### `CurrentSubscriptionResponse`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| subscription | yes | TenantSubscription | - |
| snapshot | yes | SubscriptionEntitlementSnapshot | - |

### `Document`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| id | yes | string | - |
| knowledgeBaseId | yes | string | - |
| fileName | yes | string | - |
| fileType | yes | string | - |
| mimeType | no | string \| null | - |
| fileSizeBytes | yes | integer | - |
| storageKey | yes | string | - |
| contentHash | no | string \| null | - |
| parseStatus | yes | string | - |
| indexStatus | yes | string | - |
| metadata | no | object | - |
| createdAt | yes | string | - |
| updatedAt | yes | string | - |

### `DocumentListResponse`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| items | yes | array[Document] | - |

### `DownloadUrlResponse`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| method | no | string | - |
| downloadUrl | yes | string | - |
| expiresAt | yes | string | - |

### `Expert`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| id | yes | string | - |
| name | yes | string | - |
| categoryId | yes | string | - |
| categoryName | yes | string | - |
| abilityIntro | yes | string | - |
| tags | no | array[string] | - |
| status | yes | string | - |
| skillIds | no | array[string] | - |
| knowledgeBaseIds | no | array[string] | - |
| guideQuestions | no | array[string] | - |
| summonButtonText | no | string \| null | - |
| createdAt | yes | string | - |
| updatedAt | yes | string | - |

### `ExpertCategory`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| id | yes | string | - |
| name | yes | string | - |
| description | no | string \| null | - |
| createdAt | yes | string | - |
| updatedAt | yes | string | - |

### `ExpertCategoryListResponse`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| items | yes | array[ExpertCategory] | - |

### `ExpertListResponse`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| items | yes | array[Expert] | - |

### `ExpertMarketCategory`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| id | yes | string | - |
| name | yes | string | - |
| description | no | string \| null | - |

### `ExpertMarketCategoryListResponse`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| items | yes | array[ExpertMarketCategory] | - |

### `ExpertMarketExpert`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| id | yes | string | - |
| name | yes | string | - |
| categoryId | yes | string | - |
| categoryName | yes | string | - |
| abilityIntro | yes | string | - |
| tags | no | array[string] | - |
| guideQuestions | no | array[string] | - |
| summonButtonText | no | string \| null | - |

### `ExpertMarketExpertListResponse`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| items | yes | array[ExpertMarketExpert] | - |

### `ExpertStatsResponse`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| total | yes | integer | - |
| published | yes | integer | - |
| draft | yes | integer | - |
| unlisted | yes | integer | - |

### `GrantPlatformRoleRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| role | yes | PlatformRole | - |

### `GrantTenantRoleRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| role | yes | TenantRole | - |

### `HTTPValidationError`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| detail | no | array[ValidationError] | - |

### `KnowledgeBase`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| id | yes | string | - |
| ownerUserId | no | string \| null | - |
| ownerUserName | no | string \| null | - |
| name | yes | string | - |
| description | no | string \| null | - |
| status | yes | string | - |
| metadata | no | object | - |
| createdAt | yes | string | - |
| updatedAt | yes | string | - |

### `KnowledgeBaseListResponse`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| items | yes | array[KnowledgeBase] | - |

### `LibraryDeletedResponse`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| id | yes | string | - |
| status | no | string | - |

### `LibraryDownloadResponse`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| method | no | string | - |
| downloadUrl | yes | string | - |
| expiresAt | yes | string | - |

### `LibraryFile`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| id | yes | string | - |
| name | yes | string | - |
| mimeType | no | string \| null | - |
| type | yes | string | - |
| sizeBytes | yes | integer | - |
| sizeLabel | yes | string | - |
| updatedAt | yes | string | - |
| createdAt | yes | string | - |
| previewSupported | yes | boolean | - |

### `LibraryFileListResponse`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| items | yes | array[LibraryFile] | - |
| total | yes | integer | - |
| page | yes | integer | - |
| pageSize | yes | integer | - |

### `LibraryPreviewResponse`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| previewType | yes | string | - |
| url | no | string \| null | - |
| content | no | string \| null | - |
| mimeType | no | string \| null | - |
| expiresAt | no | string \| null | - |

### `ListManagedUsersResponse`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| items | yes | array[UserSummary] | - |
| total | no | integer | - |
| page | no | integer | - |
| pageSize | no | integer | - |

### `ListPlatformRolesResponse`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| items | yes | array[PlatformRoleSummary] | - |

### `ListUserTenantsResponse`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| items | yes | array[UserTenantSummary] | - |

### `ListUsersResponse`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| items | yes | array[UserAccessSummary] | - |

### `LoginRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| email | yes | string | - |
| password | yes | string | - |
| tenantId | no | string \| null | - |

### `LogoutRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| refreshToken | yes | string | - |

### `PinSessionRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| isPinned | no | boolean | - |

### `Plan`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| id | yes | string | - |
| code | yes | string | - |
| name | yes | string | - |
| level | yes | integer | - |
| description | yes | string | - |
| typeLabel | no | string \| null | - |
| subtitle | no | string \| null | - |
| badgeLabel | no | string \| null | - |
| highlightItems | no | array[string] | - |
| upgradeRules | no | object | - |
| status | yes | string | - |
| isRecommended | yes | boolean | - |
| sortOrder | yes | integer | - |
| subscriptionCount | no | integer | - |
| prices | no | array[PlanPrice] | - |
| entitlements | no | PlanEntitlements \| null | - |
| expertIds | no | array[string] | - |
| createdAt | yes | string | - |
| updatedAt | yes | string | - |

### `PlanEntitlements`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| id | yes | string | - |
| planId | yes | string | - |
| monthlyQuestionLimit | yes | integer | - |
| monthlyTokenLimit | yes | integer | - |
| seatLimit | yes | integer | - |
| singleTurnTokenLimit | no | integer \| null | - |
| modelTiers | no | array[string] | - |
| features | no | object | - |
| createdAt | yes | string | - |
| updatedAt | yes | string | - |

### `PlanListResponse`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| items | yes | array[Plan] | - |

### `PlanPrice`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| id | yes | string | - |
| planId | yes | string | - |
| billingPeriod | yes | string | - |
| currency | yes | string | - |
| amountCents | yes | integer | - |
| discountLabel | no | string \| null | - |
| isEnabled | yes | boolean | - |
| createdAt | yes | string | - |
| updatedAt | yes | string | - |

### `PlatformRole`

`{"type": "string", "enum": ["admin", "expert", "operator"], "title": "PlatformRole"}`

### `PlatformRoleSummary`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| role | yes | PlatformRole | - |
| name | yes | string | - |
| permissions | yes | array[string] | - |

### `PlatformUserActivateRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| token | yes | string | - |
| newPassword | yes | string | - |
| name | no | string \| null | - |

### `RefreshRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| refreshToken | yes | string | - |
| tenantId | no | string \| null | - |

### `RegisterRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| email | yes | string | - |
| password | yes | string | - |
| name | yes | string | - |

### `RenameSessionRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| title | yes | string | - |

### `ReplacePlanEntitlementsRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| monthlyQuestionLimit | yes | integer | - |
| monthlyTokenLimit | yes | integer | - |
| seatLimit | yes | integer | - |
| singleTurnTokenLimit | no | integer \| null | - |
| modelTiers | no | array[string] | - |
| features | no | object | - |

### `ReplacePlanExpertsRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| expertIds | no | array[string] | - |

### `ReplacePlanPriceRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| billingPeriod | yes | string | - |
| currency | yes | string | - |
| amountCents | yes | integer | - |
| discountLabel | no | string \| null | - |
| isEnabled | no | boolean | - |

### `ReplacePlanPricesRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| items | no | array[ReplacePlanPriceRequest] | - |

### `ResolvePermissionRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| outcome | no | string \| null | - |
| optionId | no | string \| null | - |

### `Skill`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| id | yes | string | - |
| slug | yes | string | - |
| name | yes | string | - |
| description | yes | string | - |
| version | no | string \| null | - |
| allowedTools | no | array[string] | - |
| filePaths | no | array[string] | - |
| tags | no | array[string] | - |
| storageUri | yes | string | - |
| createdAt | yes | string | - |
| updatedAt | yes | string | - |

### `SkillListResponse`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| items | yes | array[Skill] | - |
| total | yes | integer | - |
| limit | yes | integer | - |
| offset | yes | integer | - |
| hasMore | yes | boolean | - |

### `SkillMetadataUpdate`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| name | no | string \| null | - |
| description | no | string \| null | - |
| version | no | string \| null | - |
| allowedTools | no | array[string] \| null | - |
| tags | no | array[string] \| null | - |

### `SubscriptionEntitlementSnapshot`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| id | yes | string | - |
| subscriptionId | yes | string | - |
| planCode | yes | string | - |
| planName | yes | string | - |
| billingPeriod | yes | string | - |
| priceSnapshot | no | object | - |
| entitlementsSnapshot | no | object | - |
| startsAt | yes | string | - |
| endsAt | no | string \| null | - |
| createdAt | yes | string | - |

### `Tenant`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| id | yes | string | - |
| type | yes | string | - |
| name | yes | string | - |
| slug | yes | string | - |
| ownerUserId | no | string \| null | - |
| ownerUserName | no | string \| null | - |
| ownerUserEmail | no | string \| null | - |
| status | yes | string | - |
| memberCount | yes | integer | - |
| currentSubscription | no | TenantSubscriptionSummary \| null | - |
| currentPlan | no | TenantPlanSummary \| null | - |
| monthlyUsage | no | TenantMonthlyUsageSummary | - |
| orderSummary | no | TenantOrderSummary | - |
| members | no | array[TenantMember] | - |
| createdAt | yes | string | - |
| updatedAt | yes | string | - |

### `TenantListResponse`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| items | yes | array[Tenant] | - |
| total | no | integer | - |
| page | no | integer | - |
| pageSize | no | integer | - |

### `TenantMember`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| userId | yes | string | - |
| email | yes | string | - |
| name | yes | string | - |
| status | yes | string | - |
| role | yes | TenantRole | - |
| joinedAt | yes | string | - |

### `TenantMemberListResponse`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| items | yes | array[TenantMember] | - |

### `TenantMonthlyUsageSummary`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| questionUsed | no | integer | - |
| questionLimit | no | integer | - |
| tokenUsed | no | integer | - |
| tokenLimit | no | integer | - |
| questionUsagePercent | no | number | - |
| tokenUsagePercent | no | number | - |
| status | no | string | - |
| isServicePaused | no | boolean | - |

### `TenantOrderItem`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| orderNo | yes | string | - |
| planName | no | string \| null | - |
| billingPeriod | no | string \| null | - |
| amountCents | no | integer | - |
| paidAt | no | string \| null | - |
| status | yes | string | - |

### `TenantOrderSummary`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| totalAmountCents | no | integer | - |
| orderCount | no | integer | - |
| recentOrders | no | array[TenantOrderItem] | - |

### `TenantPlanSummary`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| id | yes | string | - |
| code | yes | string | - |
| name | yes | string | - |
| typeLabel | no | string \| null | - |
| billingPeriod | yes | string | - |
| priceLabel | no | string \| null | - |
| priceSnapshot | no | object | - |
| entitlementsSnapshot | no | object | - |

### `TenantRole`

`{"type": "string", "enum": ["admin", "member"], "title": "TenantRole"}`

### `TenantSubscription`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| id | yes | string | - |
| tenantId | yes | string | - |
| planId | yes | string | - |
| status | yes | string | - |
| billingPeriod | yes | string | - |
| currentPeriodStart | yes | string | - |
| currentPeriodEnd | no | string \| null | - |
| cancelAtPeriodEnd | yes | boolean | - |
| createdAt | yes | string | - |
| updatedAt | yes | string | - |

### `TenantSubscriptionSummary`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| subscriptionId | yes | string | - |
| planId | yes | string | - |
| planCode | yes | string | - |
| planName | yes | string | - |
| billingPeriod | yes | string | - |
| status | yes | string | - |
| rawStatus | yes | string | - |
| currentPeriodStart | yes | string | - |
| currentPeriodEnd | no | string \| null | - |
| daysUntilExpiry | no | integer \| null | - |
| cancelAtPeriodEnd | yes | boolean | - |
| autoRenew | yes | boolean | - |
| priceLabel | no | string \| null | - |

### `UpdateDocumentRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| fileName | no | string \| null | - |
| metadata | no | object \| null | - |

### `UpdateExpertCategoryRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| name | no | string \| null | - |
| description | no | string \| null | - |

### `UpdateExpertRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| name | no | string \| null | - |
| categoryId | no | string \| null | - |
| abilityIntro | no | string \| null | - |
| tags | no | array[string] \| null | - |
| skillIds | no | array[string] \| null | - |
| knowledgeBaseIds | no | array[string] \| null | - |
| guideQuestions | no | array[string] \| null | - |
| summonButtonText | no | string \| null | - |

### `UpdateExpertStatusRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| status | yes | string | - |

### `UpdateKnowledgeBaseRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| name | no | string \| null | - |
| description | no | string \| null | - |
| metadata | no | object \| null | - |

### `UpdatePlanRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| code | no | string \| null | - |
| name | no | string \| null | - |
| level | no | integer \| null | - |
| description | no | string \| null | - |
| typeLabel | no | string \| null | - |
| subtitle | no | string \| null | - |
| badgeLabel | no | string \| null | - |
| highlightItems | no | array[string] \| null | - |
| upgradeRules | no | object \| null | - |
| status | no | string \| null | - |
| isRecommended | no | boolean \| null | - |
| sortOrder | no | integer \| null | - |

### `UpdateTenantMemberRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| role | yes | TenantRole | - |

### `UpdateTenantRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| name | no | string \| null | - |
| slug | no | string \| null | - |
| ownerUserId | no | string \| null | - |

### `UpdateTenantStatusRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| status | yes | string | - |

### `UpdateTenantSubscriptionRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| planId | yes | string | - |
| billingPeriod | yes | string | - |
| status | no | string | - |
| currentPeriodStart | no | string \| null | - |
| currentPeriodEnd | no | string \| null | - |
| cancelAtPeriodEnd | no | boolean | - |

### `UpdateUserRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| name | no | string \| null | - |

### `UpdateUserStatusRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| status | yes | string | - |

### `UploadUrlRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| fileName | yes | string | - |
| mimeType | no | string \| null | - |
| fileSizeBytes | yes | integer | - |
| contentHash | no | string \| null | - |

### `UploadUrlResponse`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| uploadSessionId | yes | string | - |
| documentId | yes | string | - |
| method | no | string | - |
| uploadUrl | yes | string | - |
| headers | no | object | - |
| objectKey | yes | string | - |
| expiresAt | yes | string | - |

### `UploadUrlResult`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| fileName | yes | string | - |
| status | yes | string | - |
| uploadSessionId | no | string \| null | - |
| documentId | no | string \| null | - |
| method | no | string \| null | - |
| uploadUrl | no | string \| null | - |
| headers | no | object \| null | - |
| objectKey | no | string \| null | - |
| expiresAt | no | string \| null | - |
| upload | no | UploadUrlResponse \| null | - |
| error | no | BatchItemError \| null | - |

### `UploadUrlsRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| files | yes | array[UploadUrlRequest] | - |

### `UploadUrlsResponse`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| items | yes | array[UploadUrlResult] | - |

### `UserAccessSummary`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| id | yes | string | - |
| email | yes | string | - |
| name | yes | string | - |
| status | yes | string | - |
| activeTenantId | no | string \| null | - |
| tenantRoles | yes | array[TenantRole] | - |
| tenantPermissions | yes | array[string] | - |
| platformRoles | yes | array[PlatformRole] | - |
| platformPermissions | yes | array[string] | - |
| createdAt | yes | string | - |
| updatedAt | yes | string | - |

### `UserDetail`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| id | yes | string | - |
| email | yes | string | - |
| name | yes | string | - |
| status | yes | string | - |
| platformRoles | yes | array[PlatformRole] | - |
| platformPermissions | yes | array[string] | - |
| tenants | yes | array[UserTenantSummary] | - |
| currentSubscription | no | UserSubscriptionSummary \| null | - |
| monthlyUsage | no | UserMonthlyUsageSummary | - |
| orderSummary | no | UserOrderSummary | - |
| usageLifetime | no | UserLifetimeUsageSummary | - |
| createdAt | yes | string | - |
| updatedAt | yes | string | - |

### `UserLifetimeUsageSummary`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| startDate | no | string \| null | - |
| usageDays | no | integer | - |
| stopped | no | boolean | - |

### `UserMonthlyUsageSummary`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| questionUsed | no | integer | - |
| questionLimit | no | integer | - |
| tokenUsed | no | integer | - |
| tokenLimit | no | integer | - |
| questionUsagePercent | no | number | - |
| tokenUsagePercent | no | number | - |
| status | no | string | - |
| isServicePaused | no | boolean | - |

### `UserOrderItem`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| orderNo | yes | string | - |
| planName | no | string \| null | - |
| billingPeriod | no | string \| null | - |
| amountCents | no | integer | - |
| paidAt | no | string \| null | - |
| status | yes | string | - |

### `UserOrderSummary`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| totalAmountCents | no | integer | - |
| orderCount | no | integer | - |
| recentOrders | no | array[UserOrderItem] | - |

### `UserSubscriptionSummary`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| subscriptionId | no | string \| null | - |
| planId | no | string \| null | - |
| planCode | no | string \| null | - |
| planName | no | string \| null | - |
| billingPeriod | no | string \| null | - |
| status | no | string \| null | - |
| statusLabel | no | string \| null | - |
| currentPeriodStart | no | string \| null | - |
| currentPeriodEnd | no | string \| null | - |
| daysUntilExpiry | no | integer \| null | - |
| cancelAtPeriodEnd | no | boolean | - |
| autoRenew | no | boolean | - |
| priceLabel | no | string \| null | - |
| currentOrderNo | no | string \| null | - |
| paymentMethod | no | string \| null | - |
| tenantId | no | string \| null | - |
| tenantName | no | string \| null | - |

### `UserSummary`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| id | yes | string | - |
| email | yes | string | - |
| name | yes | string | - |
| status | yes | string | - |
| platformRoles | yes | array[PlatformRole] | - |
| tenantCount | yes | integer | - |
| currentSubscription | no | UserSubscriptionSummary \| null | - |
| monthlyUsage | no | UserMonthlyUsageSummary | - |
| orderSummary | no | UserOrderSummary | - |
| usageLifetime | no | UserLifetimeUsageSummary | - |
| createdAt | yes | string | - |
| updatedAt | yes | string | - |

### `UserTenantSummary`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| id | yes | string | - |
| name | yes | string | - |
| type | yes | string | - |
| slug | yes | string | - |
| status | yes | string | - |
| role | yes | TenantRole | - |
| joinedAt | yes | string | - |

### `ValidationError`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| loc | yes | array[string \| integer] | - |
| msg | yes | string | - |
| type | yes | string | - |
| input | no | {"title": "Input"} | - |
| ctx | no | object | - |
