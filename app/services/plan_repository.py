from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from app.db import DatabaseConnection
from app.domain.plans import Plan, PlanEntitlements, PlanPrice
from app.services._sql import execute, fetch_all, fetch_one, json_param, rowcount


class PlanRepository:
    """Raw SQL data access for plans, prices, entitlements, and plan groups."""

    def __init__(self, connection: DatabaseConnection) -> None:
        self.connection = connection

    def list(self, *, active_only: bool = False) -> list[Plan]:
        where = "where status = 'active'" if active_only else ""
        rows = fetch_all(
            self.connection,
            f"""
            select id, code, name, level, description, type_label, subtitle, badge_label,
                   highlight_items, upgrade_rules, status, is_recommended,
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
                   highlight_items, upgrade_rules, status, is_recommended,
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
                   highlight_items, upgrade_rules, status, is_recommended,
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
              highlight_items, upgrade_rules, status, is_recommended, sort_order
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            "select id from tenant_subscriptions where plan_id = ? limit 1",
            (plan_id,),
        )
        return row is not None

    def replace_prices(self, plan_id: str, prices: list[dict[str, Any]]) -> None:
        execute(self.connection, "delete from plan_prices where plan_id = ?", (plan_id,))
        for price in prices:
            execute(
                self.connection,
                """
                insert into plan_prices (
                  id, plan_id, billing_period, currency, amount_cents,
                  discount_label, is_enabled
                )
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"plan_price_{uuid4().hex}",
                    plan_id,
                    price["billing_period"],
                    price["currency"],
                    price["amount_cents"],
                    price["discount_label"],
                    price["is_enabled"],
                ),
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
        execute(self.connection, "delete from plan_entitlements where plan_id = ?", (plan_id,))
        execute(
            self.connection,
            """
            insert into plan_entitlements (
              id, plan_id, monthly_question_limit, monthly_token_limit, seat_limit,
              single_turn_token_limit, model_tiers, features
            )
            values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"plan_entitlement_{uuid4().hex}",
                plan_id,
                monthly_question_limit,
                monthly_token_limit,
                seat_limit,
                single_turn_token_limit,
                json_param(self.connection, model_tiers),
                json_param(self.connection, features),
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
        execute(self.connection, "delete from plan_experts where plan_id = ?", (plan_id,))
        for expert_id in expert_ids:
            execute(
                self.connection,
                "insert into plan_experts (id, plan_id, expert_id) values (?, ?, ?)",
                (f"plan_expert_{uuid4().hex}", plan_id, expert_id),
            )

    def _expert_ids_by_plan(self, plan_ids: list[str]) -> dict[str, list[str]]:
        if not plan_ids:
            return {}
        placeholders = ", ".join(["?"] * len(plan_ids))
        rows = fetch_all(
            self.connection,
            f"""
            select plan_id, expert_id from plan_experts
            where plan_id in ({placeholders})
            order by plan_id, created_at asc, expert_id asc
            """,
            plan_ids,
        )
        grouped: dict[str, list[str]] = {}
        for row in rows:
            grouped.setdefault(str(row["plan_id"]), []).append(str(row["expert_id"]))
        return grouped

    def _map_plans(
        self, rows: list[dict[str, Any]], *, enabled_prices_only: bool = False
    ) -> list[Plan]:
        plan_ids = [str(row["id"]) for row in rows]
        prices = self._prices_by_plan(plan_ids, enabled_only=enabled_prices_only)
        entitlements = self._entitlements_by_plan(plan_ids)
        subscription_counts = self._subscription_counts_by_plan(plan_ids)
        expert_ids_by_plan = self._expert_ids_by_plan(plan_ids)
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
                prices=prices.get(str(row["id"]), []),
                entitlements=entitlements.get(str(row["id"])),
                expertIds=expert_ids_by_plan.get(str(row["id"]), []),
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
            from tenant_subscriptions
            where plan_id in ({placeholders})
              and status in ('active', 'trialing', 'past_due')
            group by plan_id
            """,
            plan_ids,
        )
        return {str(row["plan_id"]): int(row["count"]) for row in rows}

    def _prices_by_plan(
        self, plan_ids: list[str], *, enabled_only: bool = False
    ) -> dict[str, list[PlanPrice]]:
        if not plan_ids:
            return {}
        placeholders = ", ".join(["?"] * len(plan_ids))
        enabled_sql = "and is_enabled = true" if enabled_only else ""
        rows = fetch_all(
            self.connection,
            f"""
            select id, plan_id, billing_period, currency, amount_cents,
                   discount_label, is_enabled, created_at, updated_at
            from plan_prices
            where plan_id in ({placeholders}) {enabled_sql}
            order by plan_id, created_at asc, id asc
            """,
            plan_ids,
        )
        grouped: dict[str, list[PlanPrice]] = {}
        for row in rows:
            grouped.setdefault(str(row["plan_id"]), []).append(_map_price(row))
        return grouped

    def _entitlements_by_plan(self, plan_ids: list[str]) -> dict[str, PlanEntitlements]:
        if not plan_ids:
            return {}
        placeholders = ", ".join(["?"] * len(plan_ids))
        rows = fetch_all(
            self.connection,
            f"""
            select id, plan_id, monthly_question_limit, monthly_token_limit, seat_limit,
                   single_turn_token_limit, model_tiers, features, created_at, updated_at
            from plan_entitlements
            where plan_id in ({placeholders})
            """,
            plan_ids,
        )
        return {str(row["plan_id"]): _map_entitlements(row) for row in rows}


def _map_price(row: dict[str, Any]) -> PlanPrice:
    return PlanPrice(
        id=str(row["id"]),
        planId=str(row["plan_id"]),
        billingPeriod=str(row["billing_period"]),
        currency=str(row["currency"]),
        amountCents=int(row["amount_cents"]),
        discountLabel=str(row["discount_label"]) if row["discount_label"] is not None else None,
        isEnabled=bool(row["is_enabled"]),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _map_entitlements(row: dict[str, Any]) -> PlanEntitlements:
    return PlanEntitlements(
        id=str(row["id"]),
        planId=str(row["plan_id"]),
        monthlyQuestionLimit=int(row["monthly_question_limit"]),
        monthlyTokenLimit=int(row["monthly_token_limit"]),
        seatLimit=int(row["seat_limit"]),
        singleTurnTokenLimit=(
            int(row["single_turn_token_limit"])
            if row["single_turn_token_limit"] is not None
            else None
        ),
        modelTiers=_json_list(row["model_tiers"]),
        features=_json_dict(row["features"]),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


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
