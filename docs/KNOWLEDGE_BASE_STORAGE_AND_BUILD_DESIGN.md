# Knowledge Base Storage and Build Design

## 1. 背景

知识库与文档能力需要由平台 API 统一管理，并为后续检索/索引后端保留扩展点：

- 知识库信息由本项目数据库管理。
- 文档原文存储在 MinIO/S3。
- 文档上传不经过 API 服务中转，优先采用前端直传 MinIO。
- 构建知识库由独立 build 操作触发，从 MinIO 下载文档后执行构建。
- 检索/索引后端只作为未来可选的构建 provider，而不是 API 与数据模型的依赖。

本方案不兼容旧 `/api/v1/documents/*`、`/api/v1/uploads/*` 或
`/api/v1/knowledge-bases/{id}/documents` 路径。所有文档操作统一收敛到
`/api/v1/knowledge-bases/{knowledge_base_id}/docs/*`。

## 2. 设计目标

### 2.1 目标

- 使用 PostgreSQL 作为知识库、文档、上传会话、构建任务的权威元数据存储。
- 使用 MinIO/S3 存储文档原文。
- 前端通过 API 获取 presigned URL 后直接上传 MinIO，API 只负责控制面。
- build 操作与上传操作解耦，文档变化只标记知识库为 `stale`，不会自动重建。
- build provider 可插拔，支持先用空实现占位，后续接入 Qdrant 或自研
  RAG pipeline。

### 2.2 非目标

- 不保留旧文档 API 的兼容层。
- 不迁移外部索引系统中已有的知识库与文档数据；本项目数据库即为唯一权威源。
- 当前阶段 build 只提供占位接口，不实现任何真实构建逻辑（不创建构建任务、不生成快照、不解析/切分/向量化）。
- 当前阶段不要求 API 服务接收大文件正文并转发 MinIO。

## 3. 总体架构

```text
Client / Web Console
        |
        | 1. request upload URL
        v
Expert API
        |
        +-- PostgreSQL
        |      +-- knowledge_bases
        |      +-- documents
        |      +-- upload_sessions
        |      +-- knowledge_base_builds
        |
        +-- MinIO / S3
        |      +-- original documents
        |
        +-- Build Worker
               +-- download documents from MinIO
               +-- parse / chunk / index
               +-- Qdrant / custom provider
```

API 服务是控制面：

- 校验权限。
- 生成 object key。
- 签发 MinIO presigned URL。
- 校验上传完成结果。
- 写入数据库元数据。
- （后续真实 build 阶段）创建 build 记录；当前阶段 build 仅为占位接口，不创建记录。

MinIO 是文档原文存储面。前端只能拿到某个对象、短有效期的临时上传权限。

## 4. API 设计

### 4.1 Knowledge Bases

```text
POST   /api/v1/knowledge-bases
GET    /api/v1/knowledge-bases
GET    /api/v1/knowledge-bases/{knowledge_base_id}
PATCH  /api/v1/knowledge-bases/{knowledge_base_id}
DELETE /api/v1/knowledge-bases/{knowledge_base_id}
```

知识库元数据由本项目数据库管理，不代理外部索引系统。

### 4.2 Docs

```text
POST   /api/v1/knowledge-bases/{knowledge_base_id}/docs/upload-url
POST   /api/v1/knowledge-bases/{knowledge_base_id}/docs/complete-upload
GET    /api/v1/knowledge-bases/{knowledge_base_id}/docs
GET    /api/v1/knowledge-bases/{knowledge_base_id}/docs/{document_id}
PATCH  /api/v1/knowledge-bases/{knowledge_base_id}/docs/{document_id}
DELETE /api/v1/knowledge-bases/{knowledge_base_id}/docs/{document_id}
GET    /api/v1/knowledge-bases/{knowledge_base_id}/docs/{document_id}/download-url
```

文档 API 必须带 `knowledge_base_id`，服务端必须校验 `document_id` 属于该知识库。

### 4.3 Build

```text
POST   /api/v1/knowledge-bases/{knowledge_base_id}/build
GET    /api/v1/knowledge-bases/{knowledge_base_id}/builds
GET    /api/v1/knowledge-bases/{knowledge_base_id}/builds/{build_id}
POST   /api/v1/knowledge-bases/{knowledge_base_id}/builds/{build_id}/cancel
```

当前阶段 `build` 相关接口仅为占位（stub），不实现任何逻辑：

- 调用后不创建 `knowledge_base_builds` 记录、不生成 `input_snapshot`、不改变 `knowledge_bases.build_status`。
- 返回固定的占位响应（例如 `501 Not Implemented`，或带 `status: "not_implemented"` 的 stub body），仅用于占住路由与契约。
- 第 7.4 / 8 / 9 节为后续实现的设计预留，当前不落地（不建表、不写 worker、不接 provider）。

### 4.4 Removed APIs

以下路径不再保留：

```text
/api/v1/documents/*
/api/v1/uploads/*
/api/v1/knowledge-bases/{knowledge_base_id}/documents
```

## 5. MinIO 直传流程

### 5.1 申请上传 URL

```text
POST /api/v1/knowledge-bases/{knowledge_base_id}/docs/upload-url
```

Request:

```json
{
  "fileName": "guide.pdf",
  "mimeType": "application/pdf",
  "fileSizeBytes": 102400,
  "contentHash": "sha256_optional"
}
```

后端处理：

1. 鉴权（必做，见 §10）：要求平台 principal + `doc:create`（tenant 角色无此权限，到不了此接口）；
   加载 KB 记录，校验存在且未归档（归档拒写）。无 scope/owner 资源级判断，访问只看权限位。
2. 校验文件名、文件大小；将 `mimeType`/扩展名映射到 `documents.file_type` 允许的枚举（白名单），
   不在枚举内直接拒绝（见 §7.5）。
3. 创建 `document_id` 与 `upload_session_id`，并把 `document_id` 写入 `upload_sessions`
   （需要新增列，见 §7.5）。
4. 由后端生成 MinIO object key（依赖 `document_id`）。
5. 创建 `upload_sessions` 记录，状态为 `initiated`。
6. 生成短有效期 presigned PUT URL。
7. 返回上传信息。

Response:

```json
{
  "uploadSessionId": "upl_123",
  "documentId": "doc_123",
  "method": "PUT",
  "uploadUrl": "https://minio.example.com/expert-docs/...",
  "headers": {
    "Content-Type": "application/pdf"
  },
  "objectKey": "knowledge-bases/kb_123/documents/doc_123/guide.pdf",
  "expiresAt": "2026-06-03T10:10:00Z"
}
```

### 5.2 前端直传 MinIO

前端使用返回的 `uploadUrl` 直接上传文件：

```text
PUT {uploadUrl}
Content-Type: application/pdf
```

Body 为文件二进制内容。

API 服务不接收文件正文，也不转发文件流量。

### 5.3 完成上传

```text
POST /api/v1/knowledge-bases/{knowledge_base_id}/docs/complete-upload
```

Request:

```json
{
  "uploadSessionId": "upl_123",
  "etag": "minio-etag",
  "fileSizeBytes": 102400
}
```

后端处理：

1. 鉴权：同 §5.1（平台 principal + `doc:create`，仅权限位 + 未归档校验）。
2. 校验 `upload_session` 存在、未过期、状态为 `initiated`。
3. 校验 `upload_session.knowledge_base_id` 与路径参数一致。
4. 对 MinIO object 执行 HEAD，确认对象存在。
5. **大小强校验**：HEAD 返回的 `Content-Length` 必须等于 `upload_sessions.file_size_bytes`
   （upload-url 阶段记录、用于额度/限额判断的值）。presigned PUT 本身不限制实际写入大小，
   客户端可用同一个 URL 上传超出声明大小的文件，因此这里必须比对。
   不一致则：置 `upload_sessions.status = failed`、删除该对象（或进入清理队列）、**不创建 document**、返回错误。
   一律以 HEAD 为准，**不信任前端传入的 `fileSizeBytes`**（仅可用于交叉核对）。
6. 单文件 PUT 的 ETag 是对象 MD5，并非 sha256，无法据此校验 `contentHash`；
   `contentHash` 的真正校验推迟到 build 下载阶段（见 §11）。
7. 创建或确认 `documents` 记录（填充 §7.5 要求的占位/默认字段）。
8. 更新 `upload_sessions.status = completed`、`completed_at`。
9. 返回文档对象。（build 落地后再在此处触发"标记需重建"，当前不涉及任何 build 状态。）

Response:

```json
{
  "id": "doc_123",
  "knowledgeBaseId": "kb_123",
  "fileName": "guide.pdf",
  "fileType": "pdf",
  "mimeType": "application/pdf",
  "fileSizeBytes": 102400,
  "storageKey": "knowledge-bases/kb_123/documents/doc_123/guide.pdf",
  "parseStatus": "pending",
  "indexStatus": "pending",
  "createdAt": "2026-06-03T10:00:00Z"
}
```

## 6. Object Key 规范

Object key 必须由后端生成，不允许前端自由传入。

推荐格式（**不含 tenant 前缀**——kb/doc 是平台侧资源，与 tenant 无任何关系）：

```text
knowledge-bases/{knowledge_base_id}/documents/{document_id}/{safe_file_name}
```

示例：

```text
knowledge-bases/kb_123/documents/doc_123/guide.pdf
```

要求：

- `safe_file_name` 需要去除路径分隔符和控制字符。
- 同一个 `document_id` 对应唯一 object key。
- 删除文档时通过数据库中的 `storage_key` 定位对象。
- 构建时只从数据库读取 `storage_key`，不扫描 bucket。

删除语义（明确）：DELETE 文档采用**软删除**——置 `documents.deleted_at`，并标记
`knowledge_bases.build_status = stale`；MinIO 对象由后台任务按 `storage_key` 异步物理删除，
不在请求路径内同步删除，也不信任前端传入的 key。

删除后的检索安全（强约束）：软删除是逻辑删除，旧的 `active_build_id` 索引里仍残留该文档的
chunk。因此**检索侧（chat/search）必须按引用文档的 `documents.deleted_at is null` 过滤**，
丢弃任何指向已删除文档的命中结果。这样删除可立即生效、无需等待重建；重建只是顺带清掉残留索引。
不允许"重建前旧内容仍可被检索命中"的窗口（这既是删除语义问题，也是权限/安全问题）。

## 7. 数据模型

> **三个贯穿全节的决策（已落地）：**
>
> 1. **kb/doc 与 tenant 零关系**：`knowledge_bases` / `documents` / `upload_sessions`
>    **不含 `tenant_id`**。KB 归属由 `owner_user_id` 表达；tenant 仅通过 chat 消费。
>    对象 key 也不带 tenant 前缀（见 §6）。
> 2. **最终 schema 直接写进幂等定义，无迁移历史**：`app/db.py` 的迁移器**每次启动重跑
>    所有 `.sql`**、且无"已应用迁移"表，靠 `create table if not exists` 的幂等性。无条件
>    `drop table + create table` 会在每次重启时清空数据。因此最终 schema 直接写进
>    `002_knowledge_bases.sql` / `003_documents.sql`（documents、upload_sessions）的
>    create-if-not-exists 定义，每个文件即对应表的最终形态——没有增量补丁文件。下文凡提到
>    "drop & recreate"，对开发期均指**重建数据库**（清库后按当前 `.sql` 重新迁移）。
> 3. **`knowledge_bases` 收敛为最小形态**：删除 `scope` / `visibility` / `build_provider` /
>    `build_status` / `active_build_id` / `last_built_at`。理由——所有 KB 都属于平台侧，权限不在
>    业务表里管理（如需共享规则另立表）；build 细节"想清楚了再加"，当前只需一个 `status`
>    （`active` / `archived`）回答"能不能用"。`owner_user_id` 仅作创建者归属，不参与访问控制。
>    访问完全由路由上的平台权限位决定。本节下文 §7.1 的 build 字段、§8/§9 的 build 流程均为
>    **后续 build 阶段的前瞻设计**，尚未落地。

### 7.1 knowledge_bases

**已落地的最小形态**（事实来源在本地 DB，不再透传外部索引系统）：

```sql
create table if not exists knowledge_bases (
  id text primary key,
  owner_user_id text references users(id) on delete set null,
  name text,
  description text,
  status text not null default 'active' check (status in ('active', 'archived')),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

字段说明：

```text
status: active | archived  -- 唯一生命周期/可用性状态。active=可用，archived=已归档（拒写）
owner_user_id: 创建者归属，不参与访问控制
metadata: 业务标签等
```

> **后续 build 阶段的前瞻设计（尚未落地）：** 当 build 真正落地时再按需补列，候选包括
> `build_status`（如 `not_built` / `building` / `ready` / `failed`）、`active_build_id`
> （当前可用于检索的成功构建版本）、`last_built_at`、`build_provider` 等。届时要重新评估
> 是否把"已构建/可检索"并入单一 `status`，还是新开列——以"查哪个状态都清楚"为准。下面 §8/§9
> 描述的就是这一前瞻流程。

### 7.2 documents

`documents` 表承载文档元数据。最终形态直接定义在 `infra/sql/003_documents.sql`（见 §7.5）。
相对旧表的关键变化：

```text
新增: content_hash, object_bucket, object_version, deleted_at, metadata
删除: storage_url, chunk_strategy, chunk_strategy_version, chunk_config
默认: parse_status/index_status = pending
```

状态建议：

```text
parse_status: pending | processing | ready | failed
index_status: pending | processing | ready | failed | stale
```

上传完成后默认：

```text
parse_status = pending
index_status = pending
```

文档变更、删除或重新上传后：

```text
knowledge_bases.build_status = stale
```

### 7.3 upload_sessions

现有 `upload_sessions` 表大体可复用，但缺 `document_id`（流程必需）等列，需按 §7.5 补充。
完整推荐字段：

```text
id
knowledge_base_id
document_id
actor_user_id
upload_mode
file_name
file_type
content_type
file_size_bytes
object_bucket
object_key
status
expires_at
completed_at
created_at
updated_at
```

状态：

```text
initiated | completed | aborted | expired | failed
```

当前阶段可只实现 `single_put`，大文件再扩展 multipart。

### 7.4 knowledge_base_builds（后续实现，当前不创建）

> 本表属于 build 真实实现阶段。当前阶段 build 仅为占位接口，**不创建此表**。
> 以下为后续接入 worker/provider 时的目标设计。

后续新增构建记录表：

```sql
create table if not exists knowledge_base_builds (
  id text primary key,
  knowledge_base_id text not null references knowledge_bases(id) on delete cascade,
  provider text not null,
  status text not null check (status in ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
  requested_by text not null references users(id),
  document_count integer not null default 0,
  input_snapshot jsonb not null default '{}'::jsonb,
  output_metadata jsonb not null default '{}'::jsonb,
  error_message text,
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_kb_builds_kb_created
  on knowledge_base_builds (knowledge_base_id, created_at desc);
```

`input_snapshot` 记录构建时使用的文档集合：

```json
{
  "documents": [
    {
      "id": "doc_1",
      "storageKey": "knowledge-bases/kb_1/documents/doc_1/a.pdf",
      "contentHash": "sha256...",
      "fileSizeBytes": 102400
    }
  ]
}
```

构建任务必须使用快照，不能在执行中动态扫描 MinIO 或重新查询不稳定文档集合。

### 7.5 相对旧模型的破坏性变更清单

`infra/sql/002`、`003` 定义了 `knowledge_bases` / `documents` / `upload_sessions` 表的最终形态。
旧的 `ingestion_jobs` / `document_chunks` 已彻底移除。

**实现方式：不考虑兼容，schema 直接收敛到 `002`/`003` 的最终定义，开发期清库重建即可。**

`documents` 表（003）的 `not null` 且无默认值列，与新上传流程冲突，处理方式：

```text
storage_url             -> 删除。只用 storage_key (+ object_bucket) 定位对象。
chunk_strategy          -> 删除。chunk 策略推迟到 build 阶段决定。
chunk_strategy_version  -> 删除。
chunk_config            -> 删除。
file_type (CHECK 枚举)  -> 保留枚举 pdf|docx|pptx|xlsx|md|txt|html|csv|json。
                           upload-url 收任意 mimeType，须在签发前做白名单映射，否则 complete 阶段违反 CHECK。
```

`documents` 重建后新增（§7.2）：`content_hash`、`object_bucket`、`object_version`、
`deleted_at`、`metadata`；`parse_status`/`index_status` 给默认 `pending`，`index_status` 增加 `stale`。
`object_bucket` 当前来自单一配置（`settings.minio_bucket`），但**持久化且 `not null`**，
以便未来换 bucket/多环境时历史对象仍可定位。

`upload_sessions` 重建并新增：

```text
document_id    -> §5.1/§6 要求上传阶段即分配 document_id 并用它拼 object key。
                  注意：documents 行在 complete-upload 才插入，故 document_id 此处不设外键。
object_bucket  -> 新增。
```

`ingestion_jobs` / `document_chunks` 属于旧 ingestion 模型，由 build/provider 模型取代，
本次已直接清理：`003` 中不再有它们的建表语句，存量开发库清库重建即可消除，build 阶段重新设计。

> 这些都是破坏性 schema 变更。已确认无需兼容存量数据，开发期清库重建。

## 8. Build 流程（后续实现，当前仅占位接口）

> 本节为 build 真实实现阶段的设计预留。当前阶段 `POST /build` 等接口只返回占位响应，
> **不执行下述任何步骤**（不创建 build 记录、不写快照、不改 `build_status`、无 worker）。
> 保留本节是为了固定后续实现方向。

### 8.1 触发构建（后续实现）

```text
POST /api/v1/knowledge-bases/{knowledge_base_id}/build
```

Request:

```json
{
  "provider": "none",
  "force": false,
  "documentIds": ["doc_1", "doc_2"],
  "config": {}
}
```

字段说明：

```text
provider: 可选，默认使用 knowledge_bases.build_provider
force: 即使知识库不是 stale 也重新构建
documentIds: 可选，为空表示构建整个知识库
config: provider-specific 构建参数
```

后续真实实现步骤（**非当前阶段**；当前阶段见 §4.3，接口只返回 stub，不执行以下任何步骤）：

1. 校验用户有 `kb:build` 权限。
2. 查询知识库下未删除文档。
3. 如果传入 `documentIds`，校验这些文档全部属于该知识库。
4. 创建 `knowledge_base_builds` 记录。
5. 写入 `input_snapshot`。
6. 将 build 状态置为 `queued`。
7. 将 `knowledge_bases.build_status` 置为 `queued`。
8. 返回 build 记录。

Response:

```json
{
  "id": "build_123",
  "knowledgeBaseId": "kb_123",
  "provider": "none",
  "status": "queued",
  "documentCount": 3,
  "createdAt": "2026-06-03T10:00:00Z"
}
```

### 8.2 Worker 执行

未来真实构建时，worker 执行：

1. 拉取 `knowledge_base_builds.status = queued` 的任务。
2. 设置 build 状态为 `running`。
3. 读取 `input_snapshot.documents`。
4. 从 MinIO 下载每个 `storageKey`。
5. 解析文档。
6. 切分 chunk。
7. 生成 embedding 或其他索引结构。
8. 写入向量库或其他索引后端。
9. 更新文档 `parse_status`、`index_status`。
10. 构建成功后更新：

```text
knowledge_base_builds.status = succeeded
knowledge_bases.build_status = ready
knowledge_bases.active_build_id = build_id
knowledge_bases.last_built_at = now()
```

失败时更新：

```text
knowledge_base_builds.status = failed
knowledge_base_builds.error_message = ...
knowledge_bases.build_status = failed
```

如果知识库在构建过程中又发生文档变更，当前 build 可以继续完成，但完成后需要比较
文档版本或变更时间；若已发生新变更，则知识库最终应保持 `stale`，不能覆盖为
`ready`。

### 8.3 真实实现时需处理的设计点（review 结论）

- **stale 守卫需要可比较的版本水位**：schema 目前没有 KB 级单调版本，无法判断"build 期间是否又有变更"。
  需在 build 开始时捕获水位（如 `max(documents.updated_at)`），或给 `knowledge_bases` 加自增
  `content_version`，完成时比对，不一致则保持 `stale`。
- **并发 build 互斥**：§8.1 未阻止对同一 KB 同时排多个 build。需加约束（如"同一 KB 同时只能有一个
  queued/running build"，用状态检查或 partial unique index 实现）。
- **`active_build_id` 加外键**：建议 `knowledge_bases.active_build_id` 引用
  `knowledge_base_builds(id)`，而非裸 `text`。
- **两套状态词汇对齐**：`knowledge_bases.build_status`（含 `building`）与
  `knowledge_base_builds.status`（含 `running`）是两个枚举；其中 KB 的 `building` 在流程里从未被设置。
  实现时补全 KB 状态机：worker 置 build 记录为 `running` 的同时，应把 KB 置为 `building`。
- **检索侧从零接入**：当前 `chat.py` / `domain/chat.py` 没有 KB 检索代码，Phase 4 是新增而非改引用。

## 9. Provider 抽象（后续实现）

> 同样属于 build 真实实现阶段，当前不落地。具体检索/索引后端在此阶段接入。

构建 provider 建议抽象为：

```text
KnowledgeBaseBuildProvider
  - NoneBuildProvider
  - QdrantBuildProvider
  - CustomBuildProvider
```

API 层只创建 build 记录，不直接调用外部索引系统。

Provider 输入：

```text
build_id
knowledge_base_id
documents snapshot
config
```

Provider 输出：

```text
status
output_metadata
error_message
```

外部索引后端后续作为 provider 接入，而不是作为知识库 API 的代理目标。

## 10. 权限模型

建议权限：

```text
kb:create
kb:read
kb:update
kb:delete
kb:build

doc:create
doc:read
doc:update
doc:delete
```

权限命名采用统一的两段式 `resource:action`（与 `app/domain/auth.py` 现有权限一致），不使用
`kb:doc:*` 三段式：当前鉴权为精确字符串匹配（无前缀/通配继承），三段式不带来任何层级语义，
反而破坏一致性。文档与 KB 的从属关系由 URL 嵌套（`/knowledge-bases/{id}/docs/*`）和资源级
鉴权（校验 `document_id` 属于该 KB）保证，不靠权限名表达。

**核心原则：kb/doc 是平台侧资源，tenant 角色不能直接操作**（与 `USER_TENANT_RBAC_DESIGN.md`
一致）。`kb:*` / `doc:*` 只授予平台角色：`expert` 创建/更新/删除，`operator` 只读并管理
entitlement，`admin` 全权。tenant 角色不持有任何 `kb:*` / `doc:*`，只通过产品工作流（chat）消费。
因此本文所有 docs/build 接口都必须经过 `require_platform_principal` + 平台权限，tenant principal
根本到不了这些接口。

与现有 `auth.py` 的差异需要同步调整角色映射（仅平台角色）：

```text
doc:upload   -> doc:create
doc:reindex  -> 移除（reindex 归入后续 build 流程）
新增 doc:read / doc:update
新增 kb:build（属于后续 build 实现阶段，当前占位接口可暂不强制）
```

**访问完全由路由上的平台权限位决定，不引入 `scope` / `visibility` / owner 的资源级判断**
（见 §7 决策 #3）。KB 都属于平台侧，谁能操作只看是否持有对应 `kb:*` / `doc:*` 权限；
`owner_user_id` 仅作创建者归属。若将来需要"按可见性对 tenant 暴露"等共享规则，另立专表，
不回写业务表。`platform:kb_publish_official` 与 `POST /knowledge-bases/official` 一并移除。

所有 docs 接口都需要校验：

- principal 是平台 principal，且具备对应 `doc:*` / `kb:*` 权限。
- KB 存在且未归档（归档 KB 拒写，`409 KB_ARCHIVED`）。
- `document_id` 是否属于路径中的 `knowledge_base_id`。

> 实现说明：`app/api/deps.py` 的 `require_platform_permission` 保证"平台侧 + 动作级"。
> 在此之上，`app/services/kb_authz.py` 的 `authorize_kb_access(principal, kb, action)`
> 仅做生命周期校验（归档 KB 拒写）——按决策 #3，不再有 owner/scope 资源级判断。
> `document_id` 归属由仓储层按 `(knowledge_base_id, document_id)` 联合查询保证。
> （注意：这里不是 tenant 隔离问题——tenant 本就无权调用这些接口。）

## 11. 安全要求

MinIO 直传必须满足：

- Bucket 不开放匿名写权限。
- Presigned URL 有短有效期，建议 5 到 15 分钟。
- Object key 必须由后端生成。
- `complete-upload` 必须 HEAD MinIO object 校验对象存在和大小。
- 文件类型、大小限制由 API 在签发 URL 前校验。
- 删除文档不能信任前端传入 object key，只能使用数据库中的 `storage_key`。
- 下载 URL 也应通过 API 签发短有效期 presigned GET URL。
- ETag 不等于内容哈希：单文件 PUT 的 ETag 是对象 MD5，不能用来校验前端声明的 sha256
  `contentHash`。完整性校验只能在 build 下载阶段重算，complete-upload 仅以 HEAD 的存在性与大小为准。

孤儿对象与会话回收：前端拿到 presigned URL 后可能从不调用 complete-upload，导致 MinIO 出现孤儿对象、
`upload_sessions` 停在 `initiated`。需要后台清理任务：将超过 `expires_at` 的会话置为 `expired`，
并删除其对应的未完成 MinIO 对象。同理，软删除文档（`deleted_at`）的对象也由后台任务物理回收。

如果未来需要内容安全扫描，可以在 `complete-upload` 后创建扫描任务。扫描完成前，
文档仍可保持 `parse_status = pending` 或额外增加 `scan_status`。

## 12. 大文件与 Multipart

当前阶段建议先实现单文件 presigned PUT。

大文件后续扩展：

```text
POST /api/v1/knowledge-bases/{knowledge_base_id}/docs/multipart/initiate
POST /api/v1/knowledge-bases/{knowledge_base_id}/docs/multipart/part-urls
POST /api/v1/knowledge-bases/{knowledge_base_id}/docs/multipart/complete
POST /api/v1/knowledge-bases/{knowledge_base_id}/docs/multipart/abort
```

multipart 仍遵循同样原则：

- API 只签发 URL 和管理状态。
- 前端直接上传 parts 到 MinIO。
- complete 时 API 校验 parts 并完成 MinIO multipart upload。
- 完成后写入或确认 `documents` 元数据。

## 13. 实施计划

### Phase 1: DB 与 API 收敛

- schema 已收敛到 `infra/sql/002`/`003` 的最终定义（`documents` / `upload_sessions` /
  `knowledge_bases`，见 §7.5）；开发期清库重建即可。
- 删除旧 `/documents/*`、`/uploads/*` 路由。
- 同步更新 API 文档：删除/替换 `docs/api/documents.md`、`docs/api/uploads.md`，修订
  `docs/api/knowledge-bases.md` 中旧的 `/{id}/documents` 段，并更新 `docs/api/README.md` 的链接
  （现仍指向已移除接口，见第 4 条 review）。
- KB CRUD 改为读写本项目数据库（不再透传外部索引系统）。
- 同步调整 `app/domain/auth.py` 权限映射（§10：`doc:upload→doc:create`、移除 `doc:reindex`、
  新增 `doc:read`/`doc:update`）。
- 实现统一的资源级鉴权 `authorize_kb_access`，并在所有 docs 流程第 1 步调用（§10）。
- 新增 `/knowledge-bases/{id}/docs/*` 路由。
- 实现 presigned PUT 上传流程。
- 实现 docs list/get/delete（软删除）/download-url。
- 文档上传完成、删除、更新后标记 `knowledge_bases.build_status = stale`。
- 增加孤儿对象与过期会话回收任务（§11）。

### Phase 2: Build 占位接口

- 新增 `/knowledge-bases/{id}/build` 与 build 查询/取消接口的**路由占位**。
- 接口返回固定 stub 响应（如 `501`），**不建 `knowledge_base_builds` 表、不写快照、不改状态**。
- 仅用于固定 API 契约，前端可据此预留按钮但不触发真实构建。

### Phase 3: Build 真实实现（Worker 与 Provider）

- 新增 `knowledge_base_builds` 表。
- build 接口改为真正创建任务、写入 `input_snapshot`、置 `queued`。
- 增加 build worker。
- 实现 `NoneBuildProvider`，再接入其他 provider。
- 构建成功后更新 `active_build_id` 与 `last_built_at`。

### Phase 4: 检索接入

- Chat/search 使用 `knowledge_bases.active_build_id` 定位可用索引。
- 当 KB 为 `stale` 时，可继续使用上一版 `active_build_id`，但响应中可提示知识库有未构建变更。
- **检索结果必须按 `documents.deleted_at is null` 过滤引用文档**（见 §6），确保已软删除文档的
  残留 chunk 不会被命中。

## 14. 关键决策

- 不兼容旧文档 API。
- 不通过 API 服务中转上传文件。
- MinIO object key 由后端统一生成。
- 文档上传完成只代表原文可用，不代表知识库已构建。
- complete-upload 以 MinIO HEAD 大小为准，且必须等于 session 记录大小，否则拒绝并清理。
- 文档软删除立即生效：检索侧按 `deleted_at is null` 过滤，不等重建。
- kb/doc 为平台侧资源，tenant 角色不能直接操作，仅经 chat 消费。
- `object_bucket` 持久化且 `not null`（当前单 bucket 来自配置）。
- 当前阶段 build 仅占位接口，不建表、不写记录、不改状态。
- build 是显式操作，从 MinIO 下载文档构建索引（后续阶段）。
- 检索/索引 provider 不是知识库管理的单一事实来源。
