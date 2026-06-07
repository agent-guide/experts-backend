# Experts API

Expert management is platform-scoped. Expert categories are the taxonomy used
by experts; each expert belongs to exactly one category.

## Expert Categories

Base path:

```text
/api/v1/expert-categories
```

All endpoints require:

```text
Authorization: Bearer <accessToken>
```

Read permission:

```text
expert:read
```

Write permission:

```text
expert:write
```

## Category Shape

```json
{
  "id": "expert_cat_123",
  "name": "Amazon Operations",
  "description": "Marketplace operations experts",
  "createdAt": "2026-06-03T00:00:00+00:00",
  "updatedAt": "2026-06-03T00:00:00+00:00"
}
```

## GET /

List expert categories. Required permission: `expert:read`.

Response `200`:

```json
{
  "items": [
    {
      "id": "expert_cat_123",
      "name": "Amazon Operations",
      "description": "Marketplace operations experts",
      "createdAt": "2026-06-03T00:00:00+00:00",
      "updatedAt": "2026-06-03T00:00:00+00:00"
    }
  ]
}
```

## GET /{category_id}

Get an expert category. Required permission: `expert:read`.

Response `200`: the category shape.

Errors:

```text
404 EXPERT_CATEGORY_NOT_FOUND
```

## POST /

Create an expert category. Required permission: `expert:write`.

Request:

```json
{
  "name": "Amazon Operations",
  "description": "Marketplace operations experts"
}
```

Response `201`: the category shape.

Errors:

```text
409 EXPERT_CATEGORY_NAME_EXISTS
```

## PATCH /{category_id}

Update an expert category. Required permission: `expert:write`.

Request:

```json
{
  "name": "Amazon Growth",
  "description": "Growth-focused experts"
}
```

All fields are optional. `description` is retained when omitted.

Response `200`: the category shape.

Errors:

```text
404 EXPERT_CATEGORY_NOT_FOUND
409 EXPERT_CATEGORY_NAME_EXISTS
```

## DELETE /{category_id}

Delete an expert category. Required permission: `expert:write`.

Response:

```text
204 No Content
```

Errors:

```text
404 EXPERT_CATEGORY_NOT_FOUND
409 EXPERT_CATEGORY_IN_USE
```

`EXPERT_CATEGORY_IN_USE` protects categories that are still referenced by
experts.

## Experts

Base path:

```text
/api/v1/experts
```

All endpoints require:

```text
Authorization: Bearer <accessToken>
```

Read permission:

```text
expert:read
```

Write permission:

```text
expert:write
```

## Expert Shape

```json
{
  "id": "expert_123",
  "name": "Amazon Listing Expert",
  "categoryId": "expert_cat_123",
  "categoryName": "Amazon Operations",
  "abilityIntro": "Helps optimize Amazon listings and reviews.",
  "tags": ["listing", "reviews"],
  "status": "draft",
  "skillIds": ["skill_1", "skill_2"],
  "knowledgeBaseIds": ["kb_1", "kb_2"],
  "guideQuestions": [
    "How can I improve my listing?",
    "Why did my review get removed?",
    "How do I optimize keywords?"
  ],
  "summonButtonText": "Ask this expert",
  "createdAt": "2026-06-03T00:00:00+00:00",
  "updatedAt": "2026-06-03T00:00:00+00:00"
}
```

Status values:

- `published` = published
- `draft` = draft
- `unlisted` = unlisted

## GET /api/v1/experts

List experts. Required permission: `expert:read`.

Response `200`:

```json
{
  "items": [
    {
      "id": "expert_123",
      "name": "Amazon Listing Expert",
      "categoryId": "expert_cat_123",
      "categoryName": "Amazon Operations",
      "abilityIntro": "Helps optimize Amazon listings and reviews.",
      "tags": ["listing", "reviews"],
      "status": "draft",
      "skillIds": ["skill_1"],
      "knowledgeBaseIds": ["kb_1"],
      "guideQuestions": [],
      "summonButtonText": "Ask this expert",
      "createdAt": "2026-06-03T00:00:00+00:00",
      "updatedAt": "2026-06-03T00:00:00+00:00"
    }
  ]
}
```

## GET /api/v1/experts/search/name

Search experts by name. Required permission: `expert:read`.

Query parameters:

| Parameter | Required | Description |
| --- | --- | --- |
| `name` | yes | Case-insensitive partial expert name. |

Example:

```text
GET /api/v1/experts/search/name?name=listing
```

Response `200`: the expert list shape.

## GET /api/v1/experts/search/category

Search experts by category. Required permission: `expert:read`.

Query parameters:

| Parameter | Required | Description |
| --- | --- | --- |
| `categoryId` | yes | Expert category ID. |

Example:

```text
GET /api/v1/experts/search/category?categoryId=expert_cat_123
```

Response `200`: the expert list shape.

## GET /api/v1/experts/search/status

Search experts by status. Required permission: `expert:read`.

Query parameters:

| Parameter | Required | Description |
| --- | --- | --- |
| `status` | yes | `published`, `draft`, or `unlisted`. |

Example:

```text
GET /api/v1/experts/search/status?status=published
```

Response `200`: the expert list shape.

## GET /api/v1/experts/stats/summary

Return dashboard statistics for expert status cards. Required permission:
`expert:read`.

Response `200`:

```json
{
  "total": 4,
  "published": 2,
  "draft": 1,
  "unlisted": 1
}
```

Field mapping:

- `total` = 专家总数
- `published` = 已上架
- `draft` = 草稿
- `unlisted` = 已下架

## GET /api/v1/experts/{expert_id}

Get an expert. Required permission: `expert:read`.

Response `200`: the expert shape.

Errors:

```text
404 EXPERT_NOT_FOUND
```

## POST /api/v1/experts

Create an expert. Required permission: `expert:write`.

Request:

```json
{
  "name": "Amazon Listing Expert",
  "categoryId": "expert_cat_123",
  "abilityIntro": "Helps optimize Amazon listings and reviews.",
  "tags": ["listing", "reviews"],
  "status": "draft",
  "skillIds": ["skill_1", "skill_2"],
  "knowledgeBaseIds": ["kb_1", "kb_2"],
  "guideQuestions": [
    "How can I improve my listing?",
    "Why did my review get removed?",
    "How do I optimize keywords?"
  ],
  "summonButtonText": "Ask this expert"
}
```

`status` defaults to `draft`. `tags`, `skillIds`, `knowledgeBaseIds`, and
`guideQuestions` default to empty arrays. `guideQuestions` accepts at most three
items.

Response `201`: the expert shape.

Errors:

```text
404 EXPERT_CATEGORY_NOT_FOUND
404 SKILL_NOT_FOUND
404 KB_NOT_FOUND
422 validation error
```

## PATCH /api/v1/experts/{expert_id}

Update an expert. Required permission: `expert:write`.

Request:

```json
{
  "name": "Updated Expert",
  "categoryId": "expert_cat_456",
  "abilityIntro": "Updated intro.",
  "tags": ["updated"],
  "skillIds": ["skill_2"],
  "knowledgeBaseIds": ["kb_3"],
  "guideQuestions": [],
  "summonButtonText": "Start"
}
```

All fields are optional. Passing `skillIds` or `knowledgeBaseIds` replaces that
relationship set. Passing `guideQuestions` replaces the guide question list.

Response `200`: the expert shape.

Errors:

```text
404 EXPERT_NOT_FOUND
404 EXPERT_CATEGORY_NOT_FOUND
404 SKILL_NOT_FOUND
404 KB_NOT_FOUND
422 validation error
```

## PATCH /api/v1/experts/{expert_id}/status

Switch expert status. Required permission: `expert:write`.

Request:

```json
{
  "status": "published"
}
```

Response `200`: the expert shape.

Errors:

```text
404 EXPERT_NOT_FOUND
422 validation error
```

## DELETE /api/v1/experts/{expert_id}

Delete an expert. Required permission: `expert:write`.

Response:

```text
204 No Content
```

Deleting an expert cascades its `expert_skills` and `expert_knowledge_bases`
relationships.

Errors:

```text
404 EXPERT_NOT_FOUND
```
