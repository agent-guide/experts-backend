from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from app.db import DatabaseConnection
from app.domain.plans import Plan, PlanEntitlements, PlanPrice
from app.services._sql import execute, fetch_all, fetch_one, json_param, rowcount


class PlanRepository:
    """Raw SQL data access for flattened plan configuration."""

    def __init__(self, connection: DatabaseConnection) -> None:
        self.connection = connection

    def list(self, *, active_only: bool = False) -> list[Plan]:
        where = "where status = 'active'" if active_only else ""
        rows = fetch_all(
            self.connection,
            f"""
            select id, code, name, level, description, type_label, subtitle, badge_label,
                   highlight_items, upgrade_rules, prices, entitlements, expert_ids, status, is_recommended,
                   sort_order, created_at, updated_at
            from plans
            {where}
            order by sort_order asc, level asc, created_at asc, id asc
            """,
        )
        return self._map_plans(rows, enabled_prices_only=active_only)

    def get(self, plan_id: str) -> Plan | None:
        row = fetch_one(
            self.connection,
            """
            select id, code, name, level, description, type_label, subtitle, badge_label,
                   highlight_items, upgrade_rules, prices, entitlements, expert_ids, status, is_recommended,
                   sort_order, created_at, updated_at
            from plans
            where id = ?
            limit 1
            """,
            (plan_id,),
        )
        plans = self._map_plans([row]) if row else []
        return plans[0] if plans else None

    def get_by_code(self, code: str) -> Plan | None:
        row = fetch_one(
            self.connection,
            """
            select id, code, name, level, description, type_label, subtitle, badge_label,
                   highlight_items, upgrade_rules, prices, entitlements, expert_ids, status, is_recommended,
                   sort_order, created_at, updated_at
            from plans
            where code = ?
            limit 1
            """,
            (code,),
        )
        plans = self._map_plans([row]) if row else []
        return plans[0] if plans else None

    def plan_id_by_code(self, code: str) -> str | None:
        row = fetch_one(
            self.connection,
            "select id from plans where code = ? limit 1",
            (code,),
        )
        return str(row["id"]) if row else None

    def insert(
        self,
        *,
        plan_id: str,
        code: str,
        name: str,
        level: int,
        description: str,
        type_label: str | None,
        subtitle: str | None,
        badge_label: str | None,
        highlight_items: list[str],
        upgrade_rules: dict[str, Any],
        status: str,
        is_recommended: bool,
        sort_order: int,
    ) -> None:
        execute(
            self.connection,
            """
            insert into plans (
              id, code, name, level, description, type_label, subtitle, badge_label,
              highlight_items, upgrade_rules, prices, entitlements, expert_ids,
              status, is_recommended, sort_order
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plan_id,
                code,
                name,
                level,
                description,
                type_label,
                subtitle,
                badge_label,
                json_param(self.connection, highlight_items),
                json_param(self.connection, upgrade_rules),
                json_param(self.connection, []),
                json_param(self.connection, None),
                json_param(self.connection, []),
                status,
                is_recommended,
                sort_order,
            ),
        )

    def update(
        self,
        plan_id: str,
        *,
        code: str,
        name: str,
        level: int,
        description: str,
        type_label: str | None,
        subtitle: str | None,
        badge_label: str | None,
        highlight_items: list[str],
        upgrade_rules: dict[str, Any],
        status: str,
        is_recommended: bool,
        sort_order: int,
    ) -> None:
        execute(
            self.connection,
            """
            update plans
            set code = ?,
                name = ?,
                level = ?,
                description = ?,
                type_label = ?,
                subtitle = ?,
                badge_label = ?,
                highlight_items = ?,
                upgrade_rules = ?,
                status = ?,
                is_recommended = ?,
                sort_order = ?,
                updated_at = CURRENT_TIMESTAMP
            where id = ?
            """,
            (
                code,
                name,
                level,
                description,
                type_label,
                subtitle,
                badge_label,
                json_param(self.connection, highlight_items),
                json_param(self.connection, upgrade_rules),
                status,
                is_recommended,
                sort_order,
                plan_id,
            ),
        )

    def clear_recommended_except(self, plan_id: str | None = None) -> None:
        if plan_id is None:
            execute(self.connection, "update plans set is_recommended = false")
            return
        execute(
            self.connection,
            """
            update plans
            set is_recommended = false
            where id <> ?
            """,
            (plan_id,),
        )

    def delete(self, plan_id: str) -> int:
        cursor = execute(self.connection, "delete from plans where id = ?", (plan_id,))
        return rowcount(cursor)

    def has_subscriptions(self, plan_id: str) -> bool:
        row = fetch_one(
            self.connection,
            "select id from subscriptions where plan_id = ? limit 1",
            (plan_id,),
        )
        return row is not None

    def replace_prices(self, plan_id: str, prices: list[dict[str, Any]]) -> None:
        rows = [
            {
                "id": f"plan_price_{uuid4().hex}",
                "planId": plan_id,
                "billingPeriod": price["billing_period"],
                "currency": price["currency"],
                "amountCents": price["amount_cents"],
                "discountLabel": price["discount_label"],
                "isEnabled": price["is_enabled"],
            }
            for price in prices
        ]
        execute(
            self.connection,
            """
            update plans
            set prices = ?, updated_at = CURRENT_TIMESTAMP
            where id = ?
            """,
            (json_param(self.connection, rows), plan_id),
        )

    def replace_entitlements(
        self,
        plan_id: str,
        *,
        monthly_question_limit: int,
        monthly_token_limit: int,
        seat_limit: int,
        single_turn_token_limit: int | None,
        model_tiers: list[str],
        features: dict[str, Any],
    ) -> None:
        execute(
            self.connection,
            """
            update plans
            set entitlements = ?, updated_at = CURRENT_TIMESTAMP
            where id = ?
            """,
            (
                json_param(
                    self.connection,
                    {
                        "id": f"plan_entitlement_{uuid4().hex}",
                        "planId": plan_id,
                        "monthlyQuestionLimit": monthly_question_limit,
                        "monthlyTokenLimit": monthly_token_limit,
                        "seatLimit": seat_limit,
                        "singleTurnTokenLimit": single_turn_token_limit,
                        "modelTiers": model_tiers,
                        "features": features,
                    },
                ),
                plan_id,
            ),
        )

    def existing_expert_ids(self, expert_ids: list[str]) -> set[str]:
        if not expert_ids:
            return set()
        placeholders = ", ".join(["?"] * len(expert_ids))
        rows = fetch_all(
            self.connection,
            f"select id from experts where id in ({placeholders})",
            expert_ids,
        )
        return {str(row["id"]) for row in rows}

    def replace_experts(self, plan_id: str, expert_ids: list[str]) -> None:
        execute(
            self.connection,
            """
            update plans
            set expert_ids = ?, updated_at = CURRENT_TIMESTAMP
            where id = ?
            """,
            (json_param(self.connection, expert_ids), plan_id),
        )

    def _map_plans(
        self, rows: list[dict[str, Any]], *, enabled_prices_only: bool = False
    ) -> list[Plan]:
        plan_ids = [str(row["id"]) for row in rows]
        subscription_counts = self._subscription_counts_by_plan(plan_ids)
        return [
            Plan(
                id=str(row["id"]),
                code=str(row["code"]),
                name=str(row["name"]),
                level=int(row["level"]),
                description=str(row["description"]),
                typeLabel=str(row["type_label"]) if row["type_label"] is not None else None,
                subtitle=str(row["subtitle"]) if row["subtitle"] is not None else None,
                badgeLabel=str(row["badge_label"]) if row["badge_label"] is not None else None,
                highlightItems=_json_list(row["highlight_items"]),
                upgradeRules=_json_dict(row["upgrade_rules"]),
                status=str(row["status"]),
                isRecommended=bool(row["is_recommended"]),
                sortOrder=int(row["sort_order"]),
                subscriptionCount=subscription_counts.get(str(row["id"]), 0),
                prices=[
                    price for price in _map_prices(row["prices"], str(row["id"]), row["created_at"], row["updated_at"])
                    if not enabled_prices_only or price.isEnabled
                ],
                entitlements=_map_entitlements_json(
                    row["entitlements"], str(row["id"]), row["created_at"], row["updated_at"]
                ),
                expertIds=_json_list(row["expert_ids"]),
                createdAt=str(row["created_at"]),
                updatedAt=str(row["updated_at"]),
            )
            for row in rows
        ]

    def _subscription_counts_by_plan(self, plan_ids: list[str]) -> dict[str, int]:
        if not plan_ids:
            return {}
        placeholders = ", ".join(["?"] * len(plan_ids))
        rows = fetch_all(
            self.connection,
            f"""
            select plan_id, count(*) as count
            from subscriptions
            where plan_id in ({placeholders})
              and status in ('active', 'trialing', 'past_due')
            group by plan_id
            """,
            plan_ids,
        )
        return {str(row["plan_id"]): int(row["count"]) for row in rows}

def _map_prices(value: Any, plan_id: str, created_at: Any, updated_at: Any) -> list[PlanPrice]:
    parsed = _json_any(value)
    if not isinstance(parsed, list):
        return []
    prices: list[PlanPrice] = []
    for index, item in enumerate(parsed):
        if not isinstance(item, dict):
            continue
        prices.append(
            PlanPrice(
                id=str(item.get("id") or f"{plan_id}_price_{index}"),
                planId=str(item.get("planId") or plan_id),
                billingPeriod=str(item.get("billingPeriod") or "monthly"),
                currency=str(item.get("currency") or "CNY"),
                amountCents=int(item.get("amountCents") or 0),
                discountLabel=(
                    str(item["discountLabel"]) if item.get("discountLabel") is not None else None
                ),
                isEnabled=bool(item.get("isEnabled", True)),
                createdAt=str(item.get("createdAt") or created_at),
                updatedAt=str(item.get("updatedAt") or updated_at),
            )
        )
    return prices


def _map_entitlements_json(
    value: Any, plan_id: str, created_at: Any, updated_at: Any
) -> PlanEntitlements | None:
    parsed = _json_any(value)
    if not isinstance(parsed, dict):
        return None
    return PlanEntitlements(
        id=str(parsed.get("id") or f"plan_entitlement_{plan_id}"),
        planId=str(parsed.get("planId") or plan_id),
        monthlyQuestionLimit=int(parsed.get("monthlyQuestionLimit") or 0),
        monthlyTokenLimit=int(parsed.get("monthlyTokenLimit") or 0),
        seatLimit=int(parsed.get("seatLimit") or 1),
        singleTurnTokenLimit=(
            int(parsed["singleTurnTokenLimit"])
            if parsed.get("singleTurnTokenLimit") is not None
            else None
        ),
        modelTiers=_json_list(parsed.get("modelTiers")),
        features=_json_dict(parsed.get("features")),
        createdAt=str(parsed.get("createdAt") or created_at),
        updatedAt=str(parsed.get("updatedAt") or updated_at),
    )


def _json_any(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return value


def _json_list(value: Any) -> list[str]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return []
    if isinstance(value, list):
        return [str(item) for item in value if isinstance(item, str)]
    return []


def _json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}
