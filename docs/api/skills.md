# Skills API

Base path:

```text
/api/v1/skills
```

Skills are platform-managed assets. Metadata is stored in the `skills` database
table. Files are stored in the same local or MinIO object storage backend used
by documents and library files. Local storage is the default development
backend; production should explicitly set `EXPERT_NEXT_OBJECT_STORAGE_BACKEND=minio`.

Skills are **platform-global** (not tenant-scoped) and are referenced by their stable
`slug`. Write operations (`POST`, `PUT`, `DELETE`) require the `skill:write` platform
permission. Read operations (`GET` list, metadata, and file) require any authenticated
principal — every authenticated user can list skills and read all of their files, so do
not store secrets inside a skill package.

The `slug` is the durable identifier other resources reference (a future `experts`
entity will associate one knowledge base and a set of skills by slug), so treat it as
immutable once published — there is no rename endpoint.

## POST /

Upload a skill zip package.

Auth:

```text
Authorization: Bearer <accessToken>
```

Required platform permission:

```text
skill:write
```

Request:

```text
multipart/form-data
file=<skill.zip>
slug=<optional-slug>
```

The zip must contain `SKILL.md`. A single common root directory is accepted and
stripped during storage.

Ingest limits (exceeding any of these returns `400`):

- Archive size: 25 MB.
- File count: 500.
- Single uncompressed file: 10 MB.
- Total uncompressed size: 50 MB.

`SKILL.md` frontmatter should include:

```yaml
---
name: amazon-review-analyzer
description: Analyze Amazon review trends and customer feedback.
version: 1.0.0
allowed-tools:
  - Bash(python scripts/analyze_reviews.py:*)
tags:
  - amazon
  - reviews
---
```

Only `name` and `description` are required. `version`, `allowed-tools`, and `tags` are
optional. List values accept either block form (`- item`) or inline form (`[a, b]`).
`allowed-tools` is **opaque passthrough metadata** here — its format is enforced by the
agent runtime that consumes the skill, not by this API.

Response `201`:

```json
{
  "id": "skill_1",
  "slug": "amazon-review-analyzer",
  "name": "amazon-review-analyzer",
  "description": "Analyze Amazon review trends and customer feedback.",
  "version": "1.0.0",
  "allowedTools": ["Bash(python scripts/analyze_reviews.py:*)"],
  "filePaths": ["SKILL.md", "scripts/analyze_reviews.py"],
  "tags": ["amazon", "reviews"],
  "storageUri": "/skills/amazon-review-analyzer",
  "createdAt": "2026-06-03T00:00:00+00:00",
  "updatedAt": "2026-06-03T00:00:00+00:00"
}
```

`storageUri` is an internal storage pointer whose shape depends on the backend
(`/skills/<slug>` for local, `minio://<bucket>/skills/<slug>` for MinIO). The `skills`
object-key prefix is fixed by the API. Use the `GET /{slug}/file` endpoint to read files rather
than parsing this value.

The old `EXPERT_NEXT_SKILL_STORAGE_*` settings are no longer used. If a previous
deployment stored skill objects in a dedicated bucket such as `expert-skills`,
copy the existing `skills/...` objects into the configured shared object storage
bucket before enabling `EXPERT_NEXT_OBJECT_STORAGE_BACKEND=minio`.

Upload is atomic: the metadata row and the stored files are committed together. If the
slug already exists the request fails with `409` and nothing is written; if storage or
the database write fails the metadata is rolled back and any partial files are removed,
so a failed upload never leaves a partial skill behind.

## GET /

List skills.

Auth:

```text
Authorization: Bearer <accessToken>
```

Query parameters:

- `tags`: repeated or comma-separated tag filter.
- `search`: text search over skill metadata.
- `limit`: default `20`, min `1`, max `100`.
- `offset`: default `0`.

Example:

```text
GET /api/v1/skills?tags=amazon,reviews&search=review&limit=20&offset=0
```

Response `200`:

```json
{
  "items": [],
  "total": 0,
  "limit": 20,
  "offset": 0,
  "hasMore": false
}
```

`total` is the number of skills matching the filters (across all pages). `hasMore` is
`true` when `offset + len(items) < total`.

## GET /{slug}

Get skill metadata.

Auth:

```text
Authorization: Bearer <accessToken>
```

Response is a `Skill` object.

## PUT /{slug}

Update skill metadata.

Auth:

```text
Authorization: Bearer <accessToken>
```

Required platform permission:

```text
skill:write
```

Request:

```json
{
  "name": "amazon-review-analyzer",
  "description": "Updated description",
  "version": "1.0.1",
  "allowedTools": ["Bash(python scripts/analyze_reviews.py:*)"],
  "tags": ["amazon", "feedback"]
}
```

All fields are optional.

Response is the updated `Skill` object.

## DELETE /{slug}

Delete a skill metadata record and optionally its files.

Auth:

```text
Authorization: Bearer <accessToken>
```

Required platform permission:

```text
skill:write
```

Query parameters:

- `delete_files`: default `false`. When `true`, also deletes files from local or
  MinIO storage.

Deletion is unconditional — the API does not yet check whether the skill is referenced
elsewhere (e.g. by an expert). When `delete_files` is `false` the metadata is removed
but the stored files are left in place.

Response:

```text
204 No Content
```

## GET /{slug}/file

Read a skill file.

Auth:

```text
Authorization: Bearer <accessToken>
```

Query parameters:

- `path`: default `SKILL.md`. Must be one of the skill's `filePaths`.

The file is returned as-is (raw bytes), so binary assets are served unchanged. The
response `Content-Type` is derived from the file extension (`.md` →
`text/markdown; charset=utf-8`, other text types include `charset=utf-8`, unknown or
binary types fall back to `application/octet-stream`).

## Errors

All errors use the standard envelope `{ "code": ..., "message": ... }`.

| Status | Code | When |
| --- | --- | --- |
| 400 | `SKILL_INVALID_ZIP` | Uploaded file is not a valid zip archive. |
| 400 | `SKILL_INVALID_ZIP_PATH` | A zip entry has an unsafe path (traversal, absolute). |
| 400 | `SKILL_ZIP_TOO_LARGE` | Archive or total uncompressed size over the limit. |
| 400 | `SKILL_ZIP_TOO_MANY_FILES` | Archive contains more than 500 files. |
| 400 | `SKILL_ZIP_FILE_TOO_LARGE` | A single file exceeds the uncompressed size limit. |
| 400 | `SKILL_EMPTY_ZIP` | Archive contains no files. |
| 400 | `SKILL_MD_REQUIRED` | Archive is missing `SKILL.md` at the root. |
| 400 | `SKILL_INVALID_FRONTMATTER` | `SKILL.md` frontmatter block is not closed with `---`. |
| 400 | `SKILL_METADATA_REQUIRED` | Frontmatter is missing `name` or `description`. |
| 400 | `SKILL_INVALID_SLUG` | Slug is not lowercase letters, numbers, and hyphens. |
| 400 | `SKILL_INVALID_FILE_PATH` | `path` query parameter is unsafe. |
| 401 | `AUTH_UNAUTHORIZED` | Missing or invalid bearer token. |
| 403 | `AUTH_FORBIDDEN` | Caller lacks the `skill:write` platform permission. |
| 404 | `SKILL_NOT_FOUND` | No skill with the given slug. |
| 404 | `SKILL_FILE_NOT_FOUND` | File not in the skill, or missing from storage. |
| 409 | `SKILL_EXISTS` | A skill with the same slug already exists. |
