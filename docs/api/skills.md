# Skills API

Base path:

```text
/api/v1/skills
```

Skills are platform-managed assets. Metadata is stored in the `skills` database
table. Files are stored in the configured local or MinIO skill storage backend.

## POST /

Upload a skill zip package.

Auth:

```text
Authorization: Bearer <accessToken>
```

Required platform permission:

```text
skill:publish
```

Request:

```text
multipart/form-data
file=<skill.zip>
slug=<optional-slug>
```

The zip must contain `SKILL.md`. A single common root directory is accepted and
stripped during storage.

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
  "storageUri": "skills/amazon-review-analyzer",
  "createdAt": "2026-06-03T00:00:00+00:00",
  "updatedAt": "2026-06-03T00:00:00+00:00"
}
```

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
  "limit": 20,
  "offset": 0
}
```

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
skill:publish
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
skill:publish
```

Query parameters:

- `delete_files`: default `false`. When `true`, also deletes files from local or
  MinIO storage.

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

- `path`: default `SKILL.md`.

Response content type:

```text
text/markdown; charset=utf-8
```
