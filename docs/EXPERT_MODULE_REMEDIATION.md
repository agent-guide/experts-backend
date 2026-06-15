# Expert 模块整改清单（commit `ad69cff` review）

本文件汇总对「Add the expert module」一次提交的架构 review 结论，并给出**可逐步落地**的整改步骤。
约定：说明用中文，所有代码 / SQL / 标识符 / 命令一律英文（遵循 `AGENTS.md`）。

涉及文件：
- `infra/sql/007_experts.sql`
- `app/domain/experts.py`
- `app/services/expert_service.py`
- `app/services/expert_category_service.py`
- `app/api/v1/routers/experts.py`
- `app/api/v1/routers/expert_categories.py`
- `app/api/v1/router.py`

每个改动完成后统一验证：

```bash
python -m pytest tests/test_app.py -q
ruff check app/ tests/
```

数据库结论：4 张表（`expert_categories` / `experts` / `expert_skills` / `expert_knowledge_bases`）
**设计合理，不精简**。`tags`/`guideQuestions` 用 jsonb、skills/KB 用 join 表的「自由字符串 vs 实体引用」
分法是有原则的；join 表在 SQLite+PG 双后端下提供 FK 完整性与可移植的反向查询。本清单不改表结构，
只修一个软删悬挂引用（P0-3）。

---

## 优先级总览

| 编号 | 问题 | 类型 | 优先级 |
|---|---|---|---|
| P0-1 | router tags 改成中文，并殃及所有既有模块 | 约定违反 | P0 |
| P0-2 | 缺少 repository 层，偏离 canonical 分层 | 架构一致性 | P0 |
| P0-3 | KB 软删导致 `knowledgeBaseIds` 悬挂引用 | 正确性 bug | P0 |
| P1-1 | 3 个 `/search/*` 端点 + 不带过滤的 `list` | 过度设计 | P1 |
| P1-2 | `delete()` 手动删子表，与 cascade 冗余 | 冗余 | P1 |
| P1-3 | `_json_string_list` 死代码分支 | 冗余 | P1 |
| P2-1 | `list()` 的 N+1（1+2N 次查询） | 性能 | P2 |
| P2-2 | 写入校验 N+1（逐 id 查询） | 性能 | P2 |
| P3-1 | tags/guideQuestions 静默去重（仅记录） | 观察 | P3 |

建议执行顺序：**P0-1 → P0-3 → P1-1 → P1-3 → P1-2 → P0-2 → P2 → P3**
（先做低风险的约定/bug 修复和 API 收敛，repository 重构放在 API 稳定后，最后做性能优化。）

---

## P0-1 — 还原 router tags 为英文

**问题**：`app/api/v1/router.py` 把新模块 tag 写成 `tags=["专家管理"]`，并顺手把 auth/users/rbac/...
所有既有模块的 tag 也改成了中文。违反「所有代码文字英文」，且夹带了与本功能无关的改动。

**落地步骤**：
1. 打开 `app/api/v1/router.py`。
2. 将所有 `tags=[...]` 改回英文，至少包括：
   - `expert_categories` → `tags=["expert-categories"]`
   - `experts` → `tags=["experts"]`
   - 还原 `auth/users/tenants/rbac/models/ops/chat/knowledge-bases/docs/builds/skills` 为原英文 tag
     （对照 `git show ad69cff -- app/api/v1/router.py` 的删除行即原值）。
3. 复核 diff 不再包含任何中文。

**验收**：`rg "tags=\[\"[^\x00-\x7F]" app/api/v1/router.py` 无输出；OpenAPI 中 tag 全英文。

---

## P0-3 — 修复 KB 软删的悬挂引用

**问题**：`knowledge_bases` 是软删（`deleted_at`），`expert_knowledge_bases` 的 `on delete cascade`
正常删除路径下不触发（仅 GC purge 时才真删）。因此一个已软删的 KB 仍会出现在某 expert 的
`knowledgeBaseIds` 中。`_list_knowledge_base_ids`（`expert_service.py:283`）未过滤 `deleted_at`。

**落地步骤**（推荐读时过滤，最低成本，符合「所有读过滤 `deleted_at is null`」约定）：
1. 编辑 `app/services/expert_service.py` 的 `_list_knowledge_base_ids`，join `knowledge_bases` 并过滤：

   ```sql
   select kb.id as knowledge_base_id
   from expert_knowledge_bases ekb
   inner join knowledge_bases kb on kb.id = ekb.knowledge_base_id
   where ekb.expert_id = ? and kb.deleted_at is null
   order by ekb.created_at asc, kb.id asc
   ```
2. （`expert_skills` 无需改：skills 是硬删，cascade 即时生效。）

**验收**：新增测试——创建 expert 关联某 KB → 软删该 KB → `GET /experts/{id}` 的
`knowledgeBaseIds` 不再包含该 KB。

---

## P1-1 — 收敛 search 端点

**问题**：`experts.py` 的 `GET /experts`（`list_experts`）不暴露任何过滤参数；却另有
`/search/name`、`/search/category`、`/search/status` 三个单条件端点。而 service 的
`list(name, category_id, status)` 本就支持组合过滤。当前拆法无法组合查询，且凭空多出 3 套路由。

**落地步骤**：
1. 改 `list_experts`，加可选 query 参数并透传：

   ```python
   @router.get("", response_model=ExpertListResponse)
   async def list_experts(
       name: str | None = Query(default=None),
       category_id: str | None = Query(default=None, alias="categoryId"),
       status: ExpertStatus | None = Query(default=None),
       principal: Principal = Depends(require_platform_permission("expert:read")),
       connection: DatabaseConnection = Depends(get_database),
   ) -> ExpertListResponse:
       return ExpertListResponse(
           items=ExpertService(connection).list(
               name=name, category_id=category_id, status=status
           )
       )
   ```
2. 删除 `search_experts_by_name` / `search_experts_by_category` / `search_experts_by_status` 三个端点。
3. `service.list()` 无需改（已支持组合过滤）。
4. 同步更新 `docs/api/experts.md` 与 `docs/api/openapi.json`（重新生成）。

**验收**：`GET /experts?status=published&categoryId=...` 可组合过滤；旧 `/search/*` 路由移除；测试更新。

> 注意：`/stats/summary` 必须仍定义在 `/{expert_id}` 之前，避免被路径参数吞掉（当前已正确）。

---

## P1-3 — 删除 `_json_string_list` 死代码

**问题**：`expert_service.py:338-351` 依次处理 `list` → `str`(json.loads) → `json_load()` 兜底。
但 `json_load` 只返回 `dict`（否则 `{}`），最后的 `if isinstance(parsed, list)` 永远为 False，是死分支。

**落地步骤**：
1. 简化为仅处理 list 与 str：

   ```python
   def _json_string_list(value: Any) -> list[str]:
       if isinstance(value, str):
           try:
               value = json.loads(value)
           except json.JSONDecodeError:
               return []
       if isinstance(value, list):
           return [str(item) for item in value if isinstance(item, str)]
       return []
   ```
2. 若 `json_load` 不再被本文件其它处使用，从 import 中移除。

**验收**：ruff 通过；tags/guideQuestions 在 SQLite(text) 与 PG(jsonb) 下读取结果一致（现有测试覆盖）。

---

## P1-2 — 去掉 `delete()` 的手动子表删除

**问题**：`expert_service.py:184-195` 在删 expert 前手动 `delete from expert_skills` /
`expert_knowledge_bases`。但两表均声明 `on delete cascade`，且 `app/db.py:60` 对 SQLite 也开了
`pragma foreign_keys = on`，双后端 cascade 均生效，手动删除冗余。

**落地步骤**：
1. 删除 `delete()` 中针对 `expert_skills` / `expert_knowledge_bases` 的两条手动 `execute`。
2. 保留 `delete from experts ... -> rowcount<=0 -> 404` 逻辑与 `commit()`。

**验收**：新增/沿用测试——删除 expert 后，其 `expert_skills` / `expert_knowledge_bases` 行被级联清除。

> 若团队倾向「显式优于隐式」而保留手动删除，则二选一：那就让删除**只**靠手动、并在 schema 注释说明
> cascade 仅作 purge/兜底——但不要两套都留着造成语义含糊。

---

## P0-2 — 补齐 repository 层

**问题**：`AGENTS.md` 规定 canonical 分层为
`domain → *_repository.py (raw SQL) → *_service.py (orchestration + commit) → router`。
现有 skills/knowledge_bases/chat/documents 均有 `*_repository.py`，但 expert 模块把原始 SQL 直接
写在 service 中，缺该层，是与项目自身架构最明显的不一致。

**落地步骤**（建议放在 P1 完成、API 稳定后做，避免反复改 SQL）：
1. 新建 `app/services/expert_repository.py`，迁入 `ExpertService` 中所有原始 SQL：
   `list_rows / get_row / insert / update / update_status / delete / list_skill_ids /
   list_knowledge_base_ids / replace_skills / replace_knowledge_bases / require_* 的查询`。
   参考 `app/services/skill_repository.py` 的方法粒度与命名。
2. 新建 `app/services/expert_category_repository.py`，迁入 `ExpertCategoryService` 的 SQL。
3. `ExpertService` / `ExpertCategoryService` 改为持有 repo，只保留编排、校验、`ApiError` 映射、`commit()`。
4. `is_unique_violation` 的捕获仍留在 service 层（与 skills 一致）。
5. 不改 router 与 domain。

**验收**：service 文件内不再出现 raw SQL 字符串；全部测试通过；与 skills 分层风格一致。

---

## P2-1 — 消除 `list()` 的 N+1

**问题**：`_map_expert` 对每行调用 `_list_skill_ids` + `_list_knowledge_base_ids`，列出 N 个 expert
共 `1 + 2N` 次查询。

**落地步骤**（任选其一，建议方案 A 可移植）：
- **方案 A（批量 + 内存分组，跨后端最稳）**：
  1. `list()` 先取得本页全部 `expert_id`。
  2. 一次 `select expert_id, skill_id from expert_skills where expert_id in (...)` 并按 expert 分组；
     KB 同理（注意 join `knowledge_bases` 过滤 `deleted_at is null`，见 P0-3）。
  3. `_map_expert` 改为从预取的 dict 取关联，不再单行查询。
- **方案 B（聚合 join）**：PG 用 `json_agg`，SQLite 用 `group_concat`——但两后端写法分叉，维护成本高，
  不优先。

**验收**：对 N 个 expert 的 `list`，查询次数与 N 解耦（≈ 常数次）；结果与改前一致；测试通过。

---

## P2-2 — 写入校验改批量

**问题**：`_require_skills` / `_require_knowledge_bases`（`expert_service.py:304-331`）逐 id
`select ... limit 1`，写路径上是 N+1。

**落地步骤**：
1. 改为单条 `where id in (...)`（KB 仍带 `deleted_at is null`），取回存在的 id 集合。
2. 与请求去重后的 id 集合求差，缺失则报对应 404，并在 `details` 里**一次性列出所有缺失 id**。

**验收**：新增测试——一次传入多个缺失 id，错误返回包含全部缺失项；正常路径不回归。

---

## P3-1 — 记录：tags/guideQuestions 静默去重

**问题**：`_unique_strings`（`expert_service.py:334`）对 `tags`/`guideQuestions` 静默去重并丢空串。
功能正确，但会无声修改用户输入。

**落地步骤**：
1. 暂不改行为；在 `docs/api/experts.md` 注明「tags / guideQuestions 会去重并忽略空字符串」。
2. 如产品要求严格校验，再考虑改为 422 报错（需产品确认，非本轮必做）。

---

## 执行中发现的两处偏差（已修正，记录备查）

落地过程中发现初版 review 有两个判断需要修正：

1. **运行时 SQLite 未开启 foreign_keys**（影响 P1-2 与 cascade 假设）。
   初版称「FK 在双后端均生效」是错的：`app/db.py` 只在 *migration* 连接上 `pragma
   foreign_keys = on`，而运行时连接工厂 `_open_sqlite` 没有，SQLite 默认每连接 FK 关闭。
   即运行时 SQLite 上 `ON DELETE CASCADE` 不会触发,手动子表删除其实是**有用的**。
   **决定（已确认）**：在 `_open_sqlite` 加 `pragma foreign_keys = on`，让 SQLite 与 PG 行为
   一致，cascade 真正生效，P1-2 删除手动删除才成立。全套测试通过。

2. **P0-1 远不止 router tags**。`app/main.py` 在本次提交里引入了**成套中文 OpenAPI 本地化**：
   `title`/`description`、`OPENAPI_TAGS`（标签名 + 描述）、约 60 个 `OPENAPI_OPERATION_SUMMARIES`、
   以及 `/health` 的中文 tag。仅改 router tags 会让 operation tag 与 `OPENAPI_TAGS` 标签名失配、
   分组错乱。
   **决定（已确认）**：全部改为英文，`OPENAPI_TAGS` 标签名与英文 router tags 对齐，删除已下线的
   3 个 search 端点 summary，`_localize_operation_summaries` 更名为 `_apply_operation_summaries`。

此外 P2-2 的错误 `details` 键由单数（`skillId`/`knowledgeBaseId`）改为复数列表
（`skillIds`/`knowledgeBaseIds`），一次性返回全部缺失 id。

---

## 收尾检查清单

- [x] P0-1 main.py + router tags 全英文（title/description/tags/summaries），无分组失配
- [x] P0-3 KB 软删不再出现在 `knowledgeBaseIds`（含回归测试）
- [x] P1-1 search 端点合并为查询参数，旧路由删除，API 文档更新
- [x] P1-3 `_json_string_list` 死代码移除
- [x] P1-2 `delete()` 去掉冗余手动删除 + `_open_sqlite` 开启运行时 FK
- [x] P0-2 expert / expert_category repository 层补齐，service 无 raw SQL
- [x] P2-1 / P2-2 N+1 消除（list 批量预取；写校验单条 IN）
- [x] P3-1 文档补充去重说明
- [x] `python -m pytest tests/test_app.py -q` 全绿（46 passed）
- [x] `ruff check app/ tests/` 无告警
- [x] `docs/api/openapi.json` 重新生成、与代码一致
