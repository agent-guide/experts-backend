from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.core.errors import ApiError
from app.db import DatabaseConnection
from app.domain.plans import CurrentSubscriptionResponse
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

        plan = self.plan_repo.get(subscription.planId)
        if not plan:
            raise ApiError(404, "PLAN_NOT_FOUND", "Plan not found")

        self.connection.commit()
        return CurrentSubscriptionResponse(subscription=subscription, plan=plan)

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
        return subscription


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
