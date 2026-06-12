# Experts API

Expert management is platform-scoped. Expert categories are the taxonomy used
by experts; each expert belongs to exactly one category.

Expert groups are authorization groups used by plans. They are separate from
expert categories: categories are for marketplace taxonomy, while groups are for
plan access control.

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
  "groupId": "expert_group_basic",
  "groupName": "基础专家组",
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

Query parameters (all optional, combinable):

| Parameter | Description |
| --- | --- |
| `name` | Case-insensitive partial expert name. |
| `categoryId` | Expert category ID. |
| `status` | `published`, `draft`, or `unlisted`. |

Example:

```text
GET /api/v1/experts?categoryId=expert_cat_123&status=published
```

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

- `total` = total number of experts
- `published` = published count
- `draft` = draft count
- `unlisted` = unlisted count

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
  "groupId": "expert_group_basic",
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
items. `tags`, `skillIds`, `knowledgeBaseIds`, and `guideQuestions` are
de-duplicated and empty strings are dropped, preserving first-seen order.
`groupId` is optional. When provided, the backend validates the expert group and
adds the new expert to that group as its primary authorization group.

Response `201`: the expert shape.

Errors:

```text
404 EXPERT_CATEGORY_NOT_FOUND
404 EXPERT_GROUP_NOT_FOUND
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
  "groupId": "expert_group_professional",
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
Passing `groupId` switches the expert's primary authorization group. Passing
`groupId: null` clears the primary group. Omitting `groupId` leaves the current
group unchanged.

Response `200`: the expert shape.

Errors:

```text
404 EXPERT_NOT_FOUND
404 EXPERT_CATEGORY_NOT_FOUND
404 EXPERT_GROUP_NOT_FOUND
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

## Expert Groups

Base path:

```text
/api/v1/expert-groups
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

## Expert Group Shape

```json
{
  "id": "expert_group_basic",
  "code": "basic",
  "name": "基础专家组",
  "description": "Free 版及以上可访问",
  "sortOrder": 10,
  "expertIds": ["expert_123"],
  "createdAt": "2026-06-12T00:00:00+00:00",
  "updatedAt": "2026-06-12T00:00:00+00:00"
}
```

The database supports many-to-many membership: one expert can belong to multiple
groups, and one group can contain many experts. Product UX may still choose to
limit each expert to one primary authorization group in Phase 1.

## GET /

List expert groups. Required permission: `expert:read`.

Response `200`:

```json
{
  "items": [
    {
      "id": "expert_group_basic",
      "code": "basic",
      "name": "基础专家组",
      "description": "Free 版及以上可访问",
      "sortOrder": 10,
      "expertIds": [],
      "createdAt": "2026-06-12T00:00:00+00:00",
      "updatedAt": "2026-06-12T00:00:00+00:00"
    }
  ]
}
```

## GET /{group_id}

Get an expert group. Required permission: `expert:read`.

Response `200`: the expert group shape.

Errors:

```text
404 EXPERT_GROUP_NOT_FOUND
```

## POST /

Create an expert group. Required permission: `expert:write`.

Request:

```json
{
  "code": "team_group",
  "name": "Team Group",
  "description": "Team experts",
  "sortOrder": 55
}
```

Response `201`: the expert group shape.

Errors:

```text
409 EXPERT_GROUP_CODE_EXISTS
422 validation error
```

## PATCH /{group_id}

Update an expert group. Required permission: `expert:write`.

Request:

```json
{
  "code": "advanced",
  "name": "高级专家组",
  "description": "Max 版及以上可访问",
  "sortOrder": 30
}
```

All fields are optional. `description` is retained when omitted.

Response `200`: the expert group shape.

Errors:

```text
404 EXPERT_GROUP_NOT_FOUND
409 EXPERT_GROUP_CODE_EXISTS
422 validation error
```

## PUT /{group_id}/experts

Replace the experts in an expert group. Required permission: `expert:write`.

Request:

```json
{
  "expertIds": ["expert_1", "expert_2"]
}
```

Response `200`: the expert group shape.

Errors:

```text
404 EXPERT_GROUP_NOT_FOUND
404 EXPERT_NOT_FOUND
```

## DELETE /{group_id}

Delete an expert group. Required permission: `expert:write`.

Response:

```text
204 No Content
```

Errors:

```text
404 EXPERT_GROUP_NOT_FOUND
409 EXPERT_GROUP_IN_USE
```

`EXPERT_GROUP_IN_USE` protects groups that are still referenced by plans.
