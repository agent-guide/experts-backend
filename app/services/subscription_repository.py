from __future__ import annotations

from typing import Any

from app.db import DatabaseConnection
from app.domain.plans import TenantSubscription
from app.services._sql import execute, fetch_one


class SubscriptionRepository:
    """Raw SQL data access for subscriptions."""

    def __init__(self, connection: DatabaseConnection) -> None:
        self.connection = connection

    def get_current(self, tenant_id: str) -> TenantSubscription | None:
        row = fetch_one(
            self.connection,
            """
            select id, tenant_id, plan_id, status, billing_period, current_period_start,
                   current_period_end, cancel_at_period_end, created_at, updated_at
            from subscriptions
            where tenant_id = ?
              and status in ('active', 'trialing', 'past_due')
              and (current_period_end is null or current_period_end > CURRENT_TIMESTAMP)
            order by current_period_start desc, created_at desc
            limit 1
            """,
            (tenant_id,),
        )
        return _map_subscription(row) if row else None

    def insert_subscription(
        self,
        *,
        subscription_id: str,
        tenant_id: str,
        plan_id: str,
        status: str,
        billing_period: str,
        current_period_start: str,
        current_period_end: str | None,
    ) -> None:
        execute(
            self.connection,
            """
            insert into subscriptions (
              id, tenant_id, plan_id, status, billing_period,
              current_period_start, current_period_end
            )
            values (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                subscription_id,
                tenant_id,
                plan_id,
                status,
                billing_period,
                current_period_start,
                current_period_end,
            ),
        )


def _map_subscription(row: dict[str, Any]) -> TenantSubscription:
    return TenantSubscription(
        id=str(row["id"]),
        tenantId=str(row["tenant_id"]),
        planId=str(row["plan_id"]),
        status=str(row["status"]),
        billingPeriod=str(row["billing_period"]),
        currentPeriodStart=str(row["current_period_start"]),
        currentPeriodEnd=(
            str(row["current_period_end"]) if row["current_period_end"] is not None else None
        ),
        cancelAtPeriodEnd=bool(row["cancel_at_period_end"]),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )
