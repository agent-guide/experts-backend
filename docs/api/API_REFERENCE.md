# Amazon Experts Backend

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

### GET `/api/v1/chat/sessions`

- Summary: List Sessions

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| header | x-tenant-id | no | string \| null | - |
| header | Authorization | no | string \| null | - |
| body | application/json | no | Settings | - |

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
| body | application/json | yes | Body_create_session_api_v1_chat_sessions_post | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 201 | application/json | object |
| 422 | application/json | HTTPValidationError |

### GET `/api/v1/chat/sessions/{session_id}/messages`

- Summary: List Messages

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | session_id | yes | string | - |
| header | x-tenant-id | no | string \| null | - |
| header | Authorization | no | string \| null | - |
| body | application/json | no | Settings | - |

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
| body | application/json | yes | Body_rename_session_api_v1_chat_sessions__session_id__title_patch | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | object |
| 422 | application/json | HTTPValidationError |

### POST `/api/v1/chat/tasks`

- Summary: Create Chat Task

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| header | x-tenant-id | no | string \| null | - |
| header | Authorization | no | string \| null | - |
| body | application/json | yes | Body_create_chat_task_api_v1_chat_tasks_post | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 202 | application/json | object |
| 422 | application/json | HTTPValidationError |

### POST `/api/v1/chat/tasks/{task_id}/cancel`

- Summary: Cancel Chat Task

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | task_id | yes | string | - |
| header | x-tenant-id | no | string \| null | - |
| header | Authorization | no | string \| null | - |
| body | application/json | no | Settings | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | object |
| 422 | application/json | HTTPValidationError |

### GET `/api/v1/chat/tasks/{task_id}/events`

- Summary: Chat Task Events

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | task_id | yes | string | - |
| header | x-tenant-id | no | string \| null | - |
| header | Authorization | no | string \| null | - |
| body | application/json | no | Settings | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | - |
| 422 | application/json | HTTPValidationError |

### GET `/api/v1/chat/tasks/{task_id}/position`

- Summary: Chat Task Position

#### Input Parameters

| Location | Name | Required | Type | Description |
| --- | --- | --- | --- | --- |
| path | task_id | yes | string | - |
| header | x-tenant-id | no | string \| null | - |
| header | Authorization | no | string \| null | - |

#### Response

| Status | Content Type | Schema |
| --- | --- | --- |
| 200 | application/json | object |
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

## health

### GET `/health`

- Summary: Health

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

## rbac

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

## users

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

## Schemas

### `Body_create_chat_task_api_v1_chat_tasks_post`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| body | yes | ChatTaskRequest | - |
| settings | no | Settings | - |

### `Body_create_session_api_v1_chat_sessions_post`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| body | yes | CreateSessionRequest | - |
| settings | no | Settings | - |

### `Body_rename_session_api_v1_chat_sessions__session_id__title_patch`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| body | yes | RenameSessionRequest | - |
| settings | no | Settings | - |

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

### `ChatTaskRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| sessionId | yes | string | - |
| question | yes | string | - |
| knowledgeBaseIds | no | array[string] | - |
| llmModel | no | string \| null | - |
| queryRewrite | no | boolean \| null | - |
| multiHop | no | object \| null | - |

### `CompleteUploadRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| uploadSessionId | yes | string | - |
| etag | no | string \| null | - |
| fileSizeBytes | no | integer \| null | - |

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

### `Settings`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| app_env | no | string | - |
| jwt_secret | no | string | - |
| jwt_issuer | no | string | - |
| jwt_audience | no | string | - |
| access_token_ttl_seconds | no | integer | - |
| refresh_token_ttl_seconds | no | integer | - |
| platform_activation_token_ttl_seconds | no | integer | - |
| default_tenant_id | no | string | - |
| cors_origins | no | array[string] | - |
| database_url | no | string | - |
| database_auto_migrate | no | boolean | - |
| database_schema_dir | no | string | - |
| pageindex_base_url | no | string \| null | - |
| pageindex_api_key | no | string \| null | - |
| ngent_base_url | no | string \| null | - |
| ngent_auth_token | no | string \| null | - |
| ngent_client_id | no | string | - |
| ngent_default_agent | no | string | - |
| ngent_default_cwd | no | string | - |
| codex_home | no | string | - |
| codex_skills_dir | no | string \| null | - |
| skill_storage_backend | no | string | - |
| skill_storage_local_dir | no | string | - |
| skill_storage_prefix | no | string | - |
| minio_endpoint | no | string \| null | - |
| minio_access_key | no | string \| null | - |
| minio_secret_key | no | string \| null | - |
| minio_bucket | no | string \| null | - |
| minio_secure | no | boolean | - |
| presigned_url_ttl_seconds | no | integer | - |

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

### `TenantRole`

`{"type": "string", "enum": ["admin", "member"], "title": "TenantRole"}`

### `UpdateDocumentRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| fileName | no | string \| null | - |
| metadata | no | object \| null | - |

### `UpdateKnowledgeBaseRequest`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| name | no | string \| null | - |
| description | no | string \| null | - |
| metadata | no | object \| null | - |

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

### `ValidationError`

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| loc | yes | array[string \| integer] | - |
| msg | yes | string | - |
| type | yes | string | - |
