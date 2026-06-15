# Amazon Experts Backend API

Version: `0.1.0`

This document is generated from the FastAPI OpenAPI schema.

## auth

### POST `/api/v1/auth/login`

- Summary: User login

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

- Summary: Refresh access token

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

- Summary: Trigger a knowledge base build

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

- Summary: List knowledge base builds

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

- Summary: Get knowledge base build details

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

- Summary: Cancel a knowledge base build

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

- Summary: Resolve a chat permission request

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

- Summary: List chat sessions

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

### POST `/api/v1/chat/sessions`

- Summary: Create a chat session

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

- Summary: Delete a chat session

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

- Summary: Get chat session details

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

### GET `/api/v1/chat/sessions/{session_id}/messages`

- Summary: List chat messages

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

- Summary: Pin or unpin a chat session

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

- Summary: Rename a chat session

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

### POST `/api/v1/chat/sessions/{session_id}/turns`

- Summary: Create and stream a chat turn

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

- Summary: Cancel a chat turn

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

- Summary: Stream chat turn events

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

- Summary: List knowledge base documents

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

- Summary: Complete a document upload

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

- Summary: Complete document uploads

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

- Summary: Create a document upload URL

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

- Summary: Create document upload URLs

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

- Summary: Delete a document

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

- Summary: Get document details

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

- Summary: Update document metadata

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

- Summary: Get a document download URL

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

- Summary: List expert categories

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

- Summary: Create an expert category

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

- Summary: Delete an expert category

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

- Summary: Get expert category details

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

- Summary: Update an expert category

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

- Summary: List public expert categories

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

- Summary: List public experts

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

- Summary: Get public expert details

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

- Summary: List experts

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

- Summary: Create an expert

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

- Summary: Get expert statistics

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

- Summary: Delete an expert

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

- Summary: Get expert details

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

- Summary: Update an expert

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

- Summary: Update expert status

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

- Summary: List knowledge bases

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

- Summary: Create a knowledge base

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

- Summary: Delete a knowledge base

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

- Summary: Get knowledge base details

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

- Summary: Update a knowledge base

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

## models

### GET `/api/v1/models/embedding`

- Summary: Get embedding model info

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

- Summary: List LLM models

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

- Summary: Get system metrics

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

- Summary: Run object storage GC
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

## rbac

### GET `/api/v1/rbac/platform/roles`

- Summary: List platform roles

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

- Summary: Grant platform role

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

- Summary: Revoke platform role

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

- Summary: List current tenant users

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

- Summary: Remove current tenant member

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

- Summary: Grant or update tenant role

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

- Summary: List skills

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

- Summary: Upload a skill

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

- Summary: Delete a skill

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

- Summary: Get skill details

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

- Summary: Update a skill

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

- Summary: Get a skill file

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

## tenants

### GET `/api/v1/tenants`

- Summary: List tenants

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | TenantListResponse |
| 422 | application/json | HTTPValidationError |

### POST `/api/v1/tenants`

- Summary: Create a tenant

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

- Summary: Get tenant details

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

- Summary: Update tenant

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

- Summary: List tenant members

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

- Summary: Add a tenant member

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

- Summary: Remove a tenant member

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

- Summary: Update tenant member role

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

- Summary: Update tenant status

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

## users

### GET `/api/v1/users`

- Summary: List regular users

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | ListManagedUsersResponse |
| 422 | application/json | HTTPValidationError |

### GET `/api/v1/users/platform`

- Summary: List platform users

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

- Summary: Create a platform user

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

- Summary: Activate a platform user

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

- Summary: Register a regular user

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

- Summary: Get user details

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

- Summary: Update user profile

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

- Summary: Update user status

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

- Summary: List the user's tenants

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

### `BatchItemError`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| code | yes | string | - |
| message | yes | string | - |
| details | no | object | - |

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
| knowledgeBaseIds | no | array[string] | - |

### `CreateTenantRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| name | yes | string | - |
| slug | no | string \| null | - |
| ownerUserId | yes | string | - |

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

### `ListManagedUsersResponse`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| items | yes | array[UserSummary] | - |

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

### `Tenant`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| id | yes | string | - |
| type | yes | string | - |
| name | yes | string | - |
| slug | yes | string | - |
| ownerUserId | no | string \| null | - |
| ownerUserName | no | string \| null | - |
| status | yes | string | - |
| memberCount | yes | integer | - |
| createdAt | yes | string | - |
| updatedAt | yes | string | - |

### `TenantListResponse`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| items | yes | array[Tenant] | - |

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

### `TenantRole`

`{"type": "string", "enum": ["admin", "member"], "title": "TenantRole"}`

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
| createdAt | yes | string | - |
| updatedAt | yes | string | - |

### `UserSummary`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| id | yes | string | - |
| email | yes | string | - |
| name | yes | string | - |
| status | yes | string | - |
| platformRoles | yes | array[PlatformRole] | - |
| tenantCount | yes | integer | - |
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
