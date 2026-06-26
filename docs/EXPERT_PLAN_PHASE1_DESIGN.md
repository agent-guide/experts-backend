# 专家套餐第一阶段后端设计

## 目标

本文档定义专家系统套餐的第一阶段后端设计。第一阶段重点建设套餐配置、专家分组授权、租户订阅状态和权益快照。

目标是让前端能够管理和展示套餐，同时为后续聊天拦截、用量统计、套餐升级和支付接入打好基础。

## 当前后端背景

后端当前已经具备：

- 平台创建和维护的专家、分类、Skill、知识库。
- 专家市场接口，只对登录用户开放，并且只展示已发布专家。
- 租户和成员体系，支持个人租户和团队租户。
- 按租户和用户隔离的 Chat 会话与 turn 记录。
- RBAC 权限体系，支持平台侧管理权限。

后端当前还没有：

- 套餐定义。
- 套餐价格。
- 套餐权益。
- 专家授权分组。
- 租户订阅。
- 权益快照。
- 用量统计。
- 订单和支付。

## 第一阶段范围

第一阶段包含：

- 管理端套餐 CRUD。
- 管理端专家分组 CRUD。
- 将专家加入专家分组。
- 将专家分组授权给套餐。
- 面向用户端的启用套餐列表查询。
- 租户当前订阅查询。
- 为新租户或首次访问的租户创建默认免费订阅。
- 创建和读取订阅权益快照。

第一阶段不包含：

- 支付渠道接入。
- 升级差价计算。
- 月度用量限制。
- Token 计量。
- Chat 运行时强制拦截。
- 席位上限强制拦截。
- 模型运行时强制拦截。
- 账单和发票。

这些能力应在数据模型稳定后分阶段实现。

## 设计原则

套餐应绑定租户，而不是只绑定用户。当前后端已经把租户作为 Chat、成员关系和隔离边界。个人用户可以使用个人租户，团队和企业可以使用团队租户。

专家授权分组应独立于专家分类。专家分类是市场展示和内容组织概念，专家分组是访问控制概念。复用专家分类做套餐权限会把 UI 分类和权限控制混在一起。

专家和专家授权分组在数据库层面建议设计为多对多关系。一个专家未来可能同时属于基础体验分组、行业能力分组、企业定制分组等多个授权集合；一个分组也会包含多个专家。多对多结构的实现成本低，但能避免后续出现组合授权、活动包、企业专属包时重构表结构。

第一阶段的产品交互可以先按“一名专家只选择一个主授权分组”来使用，降低管理端复杂度。也就是说，数据库保留多对多扩展能力，service 层或管理端表单可以先限制每个专家最多属于一个套餐等级分组。后续如果需要让专家同时加入多个授权集合，只需放开业务校验，不需要改数据库结构。

套餐修改不应静默改变当前订阅用户的权益。租户订阅应保存当前周期的权益快照，这样即使管理员后续修改基础套餐，历史订阅仍然可以解释和追溯。

第一阶段应保持配置优先。不要在 Chat、Token 和支付能力尚未接入时假装限制已经完整生效。

## 数据库表

### `plans`

保存套餐主定义。

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | text | 是 | 主键，建议生成格式为 `plan_*`。 |
| `code` | text | 是 | 稳定系统编码，例如 `free`、`pro`、`max`、`business`。唯一。 |
| `name` | text | 是 | 展示名称。 |
| `level` | integer | 是 | 套餐等级，用于判断升级顺序。数值越大等级越高。 |
| `description` | text | 是 | 用户端展示的套餐描述。 |
| `status` | text | 是 | `active` 或 `disabled`。 |
| `is_recommended` | boolean | 是 | 是否展示“最受欢迎”标签。 |
| `sort_order` | integer | 是 | 用户端展示顺序。 |
| `created_at` | timestamptz | 是 | 默认 `now()`。 |
| `updated_at` | timestamptz | 是 | 默认 `now()`。 |

约束：

- `code` 唯一。
- `level` 唯一。
- `status` 只能是 `active`、`disabled`。
- 同一时间只允许一个套餐被推荐。第一阶段建议在 service 层实现，兼容 SQLite 和 PostgreSQL。

### `plan_prices`

保存每个套餐支持的计费选项。

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | text | 是 | 主键，建议生成格式为 `plan_price_*`。 |
| `plan_id` | text | 是 | 外键到 `plans(id)`，`on delete cascade`。 |
| `billing_period` | text | 是 | `free`、`monthly`、`yearly` 或 `sales`。 |
| `currency` | text | 是 | 例如 `CNY` 或 `USD`。 |
| `amount_cents` | integer | 是 | 最小货币单位。免费套餐为 `0`。 |
| `discount_label` | text | 否 | 展示文案，例如年付优惠说明。 |
| `is_enabled` | boolean | 是 | 是否可选择或展示。 |
| `created_at` | timestamptz | 是 | 默认 `now()`。 |
| `updated_at` | timestamptz | 是 | 默认 `now()`。 |

约束：

- `(plan_id, billing_period, currency)` 唯一。
- `billing_period` 只能是 `free`、`monthly`、`yearly`、`sales`。
- `amount_cents >= 0`。

### `plan_entitlements`

保存套餐当前权益配置。

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | text | 是 | 主键，建议生成格式为 `plan_entitlement_*`。 |
| `plan_id` | text | 是 | 外键到 `plans(id)`，`on delete cascade`。唯一。 |
| `monthly_question_limit` | integer | 是 | 每月问答额度。 |
| `monthly_token_limit` | integer | 是 | 每月 Token 额度。 |
| `seat_limit` | integer | 是 | 租户成员席位额度。 |
| `single_turn_token_limit` | integer | 否 | 可选的单次对话 Token 上限。 |
| `model_tiers` | jsonb | 是 | 例如 `["core", "enhanced"]`。 |
| `features` | jsonb | 是 | 功能开关，例如团队管理、API 调用等。 |
| `created_at` | timestamptz | 是 | 默认 `now()`。 |
| `updated_at` | timestamptz | 是 | 默认 `now()`。 |

约束：

- `plan_id` 唯一。
- 各类额度必须大于等于 `0`。
- `seat_limit >= 1`。

### `expert_groups`

保存专家授权分组。

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | text | 是 | 主键，建议生成格式为 `expert_group_*`。 |
| `code` | text | 是 | 稳定编码，例如 `basic`、`professional`、`advanced`、`enterprise_custom`。唯一。 |
| `name` | text | 是 | 展示名称。 |
| `description` | text | 否 | 管理端说明。 |
| `sort_order` | integer | 是 | 管理端或用户端展示顺序。 |
| `created_at` | timestamptz | 是 | 默认 `now()`。 |
| `updated_at` | timestamptz | 是 | 默认 `now()`。 |

### `expert_group_members`

保存专家和授权分组的关联关系。

该表按多对多关系设计：一个专家可以加入多个授权分组，一个授权分组也可以包含多个专家。第一阶段如果产品规则希望保持简单，可以在 service 层限制同一专家只能加入一个主授权分组，但不建议在数据库层用 `expert_id` 唯一约束锁死一对一关系。

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | text | 是 | 主键，建议生成格式为 `expert_group_member_*`。 |
| `group_id` | text | 是 | 外键到 `expert_groups(id)`，`on delete cascade`。 |
| `expert_id` | text | 是 | 外键到 `experts(id)`，`on delete cascade`。 |
| `created_at` | timestamptz | 是 | 默认 `now()`。 |

约束：

- `(group_id, expert_id)` 唯一。

### `plan_expert_groups`

保存套餐可访问的专家分组。

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | text | 是 | 主键，建议生成格式为 `plan_expert_group_*`。 |
| `plan_id` | text | 是 | 外键到 `plans(id)`，`on delete cascade`。 |
| `group_id` | text | 是 | 外键到 `expert_groups(id)`，`on delete cascade`。 |
| `created_at` | timestamptz | 是 | 默认 `now()`。 |

约束：

- `(plan_id, group_id)` 唯一。

### `tenant_subscriptions`

保存租户订阅记录。第一阶段只负责创建和读取订阅，支付驱动的状态流转后置。

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | text | 是 | 主键，建议生成格式为 `tenant_subscription_*`。 |
| `tenant_id` | text | 是 | 外键到 `tenants(id)`，`on delete cascade`。 |
| `plan_id` | text | 是 | 外键到 `plans(id)`，`on delete restrict`。 |
| `status` | text | 是 | `active`、`trialing`、`past_due`、`cancelled` 或 `expired`。 |
| `billing_period` | text | 是 | `free`、`monthly`、`yearly` 或 `sales`。 |
| `current_period_start` | timestamptz | 是 | 当前权益周期开始时间。 |
| `current_period_end` | timestamptz | 否 | 免费开放订阅可为空。 |
| `cancel_at_period_end` | boolean | 是 | 默认 `false`。 |
| `created_at` | timestamptz | 是 | 默认 `now()`。 |
| `updated_at` | timestamptz | 是 | 默认 `now()`。 |

约束：

- `status` 只能是允许值。
- `billing_period` 只能是 `free`、`monthly`、`yearly`、`sales`。
- 一个租户同一时间只应有一个当前有效订阅。第一阶段建议在 service 层保证，避免 SQLite 和 PostgreSQL 的部分索引差异。

### `subscription_entitlement_snapshots`

保存订阅周期内实际生效的权益快照。

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | text | 是 | 主键，建议生成格式为 `subscription_snapshot_*`。 |
| `subscription_id` | text | 是 | 外键到 `tenant_subscriptions(id)`，`on delete cascade`。 |
| `plan_code` | text | 是 | 从 `plans.code` 拷贝。 |
| `plan_name` | text | 是 | 从 `plans.name` 拷贝。 |
| `billing_period` | text | 是 | 从订阅记录拷贝。 |
| `price_snapshot` | jsonb | 是 | 购买或激活时的价格和币种。 |
| `entitlements_snapshot` | jsonb | 是 | 套餐限制、模型等级、功能开关、专家分组等。 |
| `starts_at` | timestamptz | 是 | 快照生效开始时间。 |
| `ends_at` | timestamptz | 否 | 快照生效结束时间。 |
| `created_at` | timestamptz | 是 | 默认 `now()`。 |

## 默认种子数据

第一阶段应在缺失时初始化四个套餐：

- `free`
- `pro`
- `max`
- `business`

也应在缺失时初始化基础专家分组：

- `basic`
- `professional`
- `advanced`
- `enterprise_custom`

种子 SQL 必须幂等，因为当前迁移 runner 会在每次启动时重新运行所有 SQL 文件。

## API 设计

### 管理端套餐接口

读取使用平台权限 `plan:read`，写入使用平台权限 `plan:write`。如果第一阶段暂时不想新增权限字符串，可以开发期临时复用 `system:ops`，但发布前建议替换为独立套餐权限。

建议接口：

- `GET /api/v1/plans`
- `POST /api/v1/plans`
- `GET /api/v1/plans/{plan_id}`
- `PATCH /api/v1/plans/{plan_id}`
- `DELETE /api/v1/plans/{plan_id}`
- `PUT /api/v1/plans/{plan_id}/prices`
- `PUT /api/v1/plans/{plan_id}/entitlements`
- `PUT /api/v1/plans/{plan_id}/expert-groups`

删除行为：

- 已存在订阅记录的套餐不能硬删除。
- `free` 套餐不能删除。
- 已停用套餐仍然对管理端可见，但不应出现在用户端购买或套餐列表中。

### 管理端专家分组接口

使用平台权限 `expert:read` 和 `expert:write`，因为专家分组属于专家管理的一部分。

建议接口：

- `GET /api/v1/expert-groups`
- `POST /api/v1/expert-groups`
- `GET /api/v1/expert-groups/{group_id}`
- `PATCH /api/v1/expert-groups/{group_id}`
- `DELETE /api/v1/expert-groups/{group_id}`
- `PUT /api/v1/expert-groups/{group_id}/experts`

删除行为：

- 被套餐引用的专家分组不能删除。
- 已包含专家的分组从数据库角度可以级联删除关联关系，但管理端交互应优先引导显式清理。

### 用户端套餐接口

要求登录，使用 `require_principal`，但不要求特定平台权限。

建议接口：

- `GET /api/v1/plan-market/plans`
- `GET /api/v1/plan-market/current-subscription`

`plan-market/plans` 只返回启用套餐和启用价格。

`current-subscription` 返回当前租户的有效订阅和当前权益快照。如果租户没有订阅，service 应创建默认免费订阅和快照。

## 领域模型

Pydantic 模型字段使用 camelCase，保持当前后端约定。

重要响应模型：

- `Plan`
- `PlanPrice`
- `PlanEntitlements`
- `ExpertGroup`
- `PlanListResponse`
- `ExpertGroupListResponse`
- `TenantSubscription`
- `SubscriptionEntitlementSnapshot`
- `CurrentSubscriptionResponse`

重要请求模型：

- `CreatePlanRequest`
- `UpdatePlanRequest`
- `ReplacePlanPricesRequest`
- `ReplacePlanEntitlementsRequest`
- `ReplacePlanExpertGroupsRequest`
- `CreateExpertGroupRequest`
- `UpdateExpertGroupRequest`
- `ReplaceExpertGroupMembersRequest`

## Service 层职责

`PlanRepository` 只负责原始 SQL。

`PlanService` 负责：

- 校验套餐编码唯一。
- 校验套餐等级唯一。
- 保证同一时间只有一个推荐套餐。
- 禁止删除 `free` 套餐。
- 禁止删除已有订阅记录的套餐。
- 事务性替换套餐价格。
- 事务性替换套餐权益。
- 事务性替换套餐专家分组。
- mutation 成功后提交事务。

`ExpertGroupRepository` 只负责原始 SQL。

`ExpertGroupService` 负责：

- 校验分组编码唯一。
- 替换成员前校验专家 id 是否存在。
- 禁止删除已被套餐引用的分组。
- 事务性替换分组成员。
- mutation 成功后提交事务。

`SubscriptionRepository` 只负责原始 SQL。

`SubscriptionService` 负责：

- 查询租户当前订阅。
- 在缺失时创建默认免费订阅。
- 根据当前套餐、价格、权益和专家分组创建权益快照。
- 返回当前订阅对应的有效快照。

## 快照结构

`entitlements_snapshot` 应足够自包含，方便后续执行权限校验：

```json
{
  "monthlyQuestionLimit": 1000,
  "monthlyTokenLimit": 2000000,
  "seatLimit": 1,
  "singleTurnTokenLimit": null,
  "modelTiers": ["core", "enhanced"],
  "features": {
    "teamManagement": false,
    "apiAccess": false,
    "privateDeployment": false
  },
  "expertGroups": [
    {
      "id": "expert_group_basic",
      "code": "basic",
      "name": "基础专家组"
    }
  ]
}
```

`price_snapshot` 应保存所选计费周期：

```json
{
  "billingPeriod": "yearly",
  "currency": "CNY",
  "amountCents": 99900,
  "discountLabel": "Save 20% yearly"
}
```

## 校验规则

套餐校验：

- `code` 必须稳定且小写。
- `level` 必须为正数。
- `sortOrder` 必须大于等于 `0`。
- 已停用套餐不能出现在用户端套餐列表中。
- 同一时间只能有一个推荐套餐。

价格校验：

- 免费套餐可以使用 `free` 计费周期，价格为 `0`。
- 付费套餐应至少有一个启用价格，或者使用 `sales` 联系销售计费周期。
- `amountCents` 必须大于等于 `0`。

权益校验：

- `monthlyQuestionLimit` 必须大于等于 `0`。
- `monthlyTokenLimit` 必须大于等于 `0`。
- `seatLimit` 必须大于等于 `1`。
- `modelTiers` 必须是已知字符串列表。
- `features` 必须是 JSON 对象。

订阅校验：

- 一个租户同一时间只应有一个当前有效订阅。
- 只为 active 租户创建默认免费订阅。
- 快照创建后应视为不可变。

## 迁移注意事项

当前项目迁移 runner 会在每次启动时重新执行所有 SQL 文件，并且没有 applied-migrations 表。

迁移文件必须：

- 使用 `create table if not exists`。
- 使用幂等索引。
- 禁止无条件 `drop table`。
- SQL 注释中不要出现分号。
- 如需补列，每条语句只添加一个 `alter table add column if not exists`。
- 同时兼容 SQLite 和 PostgreSQL。

建议新增文件：

- `infra/sql/008_plans.sql`

## 测试计划

第一阶段应补充以下测试：

- 套餐 CRUD 权限。
- 套餐列表排序。
- 同一时间只能有一个推荐套餐。
- 已停用套餐不出现在用户端套餐市场。
- `free` 套餐不能删除。
- 已有订阅的套餐不能删除。
- 专家分组 CRUD 权限。
- 专家分组成员替换。
- 套餐专家分组替换。
- 当前订阅接口自动创建免费订阅。
- 当前订阅接口返回权益快照。
- 套餐权益修改后，已有快照保持不变。

实现完成前运行：

```bash
python -m pytest tests/test_app.py -q
ruff check app/ tests/
```

## 后续阶段

第二阶段增加运行时权限控制：

- 专家市场根据当前订阅快照过滤专家。
- 召唤专家时，如果专家不在租户权益快照授权范围内，则拒绝请求。
- 增加套餐访问校验服务方法。

第三阶段增加用量统计：

- `usage_periods`
- `usage_events`
- 在 `ChatService.stream_turn` 中增加问答次数限制。
- 等上游计算后端暴露 Token usage 后增加 Token 统计。

第四阶段增加商业闭环：

- 订单。
- 支付。
- 升级差价。
- 续费。
- 联系销售流程。
- 到期和降级任务。
