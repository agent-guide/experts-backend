from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.core.errors import ApiError
from app.db import DatabaseConnection
from app.domain.plans import CurrentSubscriptionResponse, Plan
from app.services.plan_repository import PlanRepository
from app.services.subscription_repository import SubscriptionRepository


class SubscriptionService:
    def __init__(self, connection: DatabaseConnection) -> None:
        self.connection = connection
        self.repo = SubscriptionRepository(connection)
        self.plan_repo = PlanRepository(connection)

    def current_subscription(self, tenant_id: str | None) -> CurrentSubscriptionResponse:
        if not tenant_id:
            raise ApiError(400, "TENANT_REQUIRED", "Active tenant is required")

        subscription = self.repo.get_current(tenant_id)
        if subscription is None:
            subscription = self._create_default_free_subscription(tenant_id)

        snapshot = self.repo.get_current_snapshot(subscription.id)
        if snapshot is None:
            plan = self.plan_repo.get(subscription.planId)
            if not plan:
                raise ApiError(404, "PLAN_NOT_FOUND", "Plan not found")
            snapshot = self._create_snapshot(subscription.id, plan, subscription.billingPeriod)

        self.connection.commit()
        return CurrentSubscriptionResponse(subscription=subscription, snapshot=snapshot)

    def _create_default_free_subscription(self, tenant_id: str):
        plan = self.plan_repo.get_by_code("free")
        if not plan:
            raise ApiError(500, "FREE_PLAN_MISSING", "Free plan is not configured")

        now = _now_iso()
        subscription_id = f"tenant_subscription_{uuid4().hex}"
        self.repo.insert_subscription(
            subscription_id=subscription_id,
            tenant_id=tenant_id,
            plan_id=plan.id,
            status="active",
            billing_period="free",
            current_period_start=now,
            current_period_end=None,
        )
        subscription = self.repo.get_current(tenant_id)
        if subscription is None:
            raise ApiError(500, "SUBSCRIPTION_CREATE_FAILED", "Subscription create failed")
        self._create_snapshot(subscription_id, plan, "free")
        return subscription

    def _create_snapshot(self, subscription_id: str, plan: Plan, billing_period: str):
        now = _now_iso()
        price = _select_price(plan, billing_period)
        entitlements = plan.entitlements
        entitlements_snapshot: dict[str, Any] = {
            "monthlyQuestionLimit": (
                entitlements.monthlyQuestionLimit if entitlements is not None else 0
            ),
            "monthlyTokenLimit": entitlements.monthlyTokenLimit if entitlements is not None else 0,
            "seatLimit": entitlements.seatLimit if entitlements is not None else 1,
            "singleTurnTokenLimit": (
                entitlements.singleTurnTokenLimit if entitlements is not None else None
            ),
            "modelTiers": entitlements.modelTiers if entitlements is not None else [],
            "features": entitlements.features if entitlements is not None else {},
            "expertGroups": [
                {"id": group.id, "code": group.code, "name": group.name}
                for group in plan.expertGroups
            ],
        }
        snapshot_id = f"subscription_snapshot_{uuid4().hex}"
        self.repo.insert_snapshot(
            snapshot_id=snapshot_id,
            subscription_id=subscription_id,
            plan_code=plan.code,
            plan_name=plan.name,
            billing_period=billing_period,
            price_snapshot=price,
            entitlements_snapshot=entitlements_snapshot,
            starts_at=now,
            ends_at=None,
        )
        snapshot = self.repo.get_current_snapshot(subscription_id)
        if snapshot is None:
            raise ApiError(500, "SNAPSHOT_CREATE_FAILED", "Subscription snapshot create failed")
        return snapshot


def _select_price(plan: Plan, billing_period: str) -> dict[str, Any]:
    for price in plan.prices:
        if price.billingPeriod == billing_period and price.isEnabled:
            return {
                "billingPeriod": price.billingPeriod,
                "currency": price.currency,
                "amountCents": price.amountCents,
                "discountLabel": price.discountLabel,
            }
    return {
        "billingPeriod": billing_period,
        "currency": "CNY",
        "amountCents": 0,
        "discountLabel": None,
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
