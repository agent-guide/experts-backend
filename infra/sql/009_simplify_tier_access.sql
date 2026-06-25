-- Drop old group infrastructure.
DROP TABLE IF EXISTS plan_expert_groups;
DROP TABLE IF EXISTS expert_group_members;
DROP TABLE IF EXISTS expert_groups;

-- Direct plan-to-expert association.
CREATE TABLE IF NOT EXISTS plan_experts (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    expert_id TEXT NOT NULL REFERENCES experts(id) ON DELETE CASCADE,
    created_at TEXT DEFAULT (CURRENT_TIMESTAMP),
    UNIQUE(plan_id, expert_id)
);

CREATE INDEX IF NOT EXISTS idx_plan_experts_plan ON plan_experts (plan_id);
CREATE INDEX IF NOT EXISTS idx_plan_experts_expert ON plan_experts (expert_id);
