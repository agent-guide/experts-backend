from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.core.errors import ApiError
from app.db import DatabaseConnection
from app.domain.auth import TenantRole
from app.domain.plans import Plan
from app.domain.tenants import (
    AddTenantMemberRequest,
    CreateTenantRequest,
    Tenant,
    TenantMember,
    TenantMonthlyUsageSummary,
    TenantOrderSummary,
    TenantPlanSummary,
    TenantSubscriptionSummary,
    UpdateTenantMemberRequest,
    UpdateTenantSubscriptionRequest,
    UpdateTenantRequest,
)
from app.services._sql import (
    execute,
    fetch_all,
    fetch_one,
    is_unique_violation,
    rowcount,
)
from app.services.plan_repository import PlanRepository
from app.services.subscription_service import SubscriptionService


class TenantService:
    def __init__(self, connection: DatabaseConnection) -> None:
        self.connection = connection
        self.plan_repo = PlanRepository(connection)
        self.subscription_service = SubscriptionService(connection)

    def list(
        self,
        *,
        search: str | None = None,
        tenant_type: str | None = None,
        subscription_type: str | None = None,
        subscription_status: str | None = None,
        sort: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Tenant], int]:
        rows = fetch_all(
            self.connection,
            """
            select
              t.id,
              t.type,
              t.name,
              t.slug,
              t.owner_user_id,
              owner.name as owner_user_name,
              owner.email as owner_user_email,
              t.status,
              t.created_at,
              t.updated_at,
              count(tm.id) as member_count
            from tenants t
            left join users owner on owner.id = t.owner_user_id
            left join tenant_members tm on tm.tenant_id = t.id
            group by
              t.id, t.type, t.name, t.slug, t.owner_user_id, owner.name, owner.email,
              t.status, t.created_at, t.updated_at
            order by t.created_at desc, t.id asc
            """,
        )
        items = [self._hydrate_tenant(_map_tenant(row), include_members=False) for row in rows]
        items = _filter_tenants(
            items,
            search=search,
            tenant_type=tenant_type,
            subscription_type=subscription_type,
            subscription_status=subscription_status,
        )
        items = _sort_tenants(items, sort)
        total = len(items)
        start = (page - 1) * page_size
        return items[start : start + page_size], total

    def get(self, tenant_id: str) -> Tenant:
        row = self._tenant_row(tenant_id)
        if not row:
            raise ApiError(404, "TENANT_NOT_FOUND", "Tenant not found")
        tenant = _map_tenant(row)
        return self._hydrate_tenant(tenant, include_members=tenant.type == "team")

    def create(self, request: CreateTenantRequest) -> Tenant:
        owner = self._require_user(request.ownerUserId)
        tenant_id = f"tenant_{uuid4().hex}"
        slug = request.slug or _tenant_slug(request.name)
        try:
            execute(
                self.connection,
                """
                insert into tenants (id, type, name, slug, owner_user_id, status)
                values (?, 'team', ?, ?, ?, 'active')
                """,
                (tenant_id, request.name, slug, owner["id"]),
            )
            self._upsert_member(tenant_id, str(owner["id"]), TenantRole.ADMIN)
            self.connection.commit()
        except Exception as exc:
            if is_unique_violation(exc):
                raise ApiError(409, "TENANT_SLUG_EXISTS", "Tenant slug already exists") from exc
            raise
        return self.get(tenant_id)

    def update(self, tenant_id: str, request: UpdateTenantRequest) -> Tenant:
        current = self.get(tenant_id)
        next_name = request.name if request.name is not None else current.name
        next_slug = request.slug if request.slug is not None else current.slug
        next_owner_id = (
            request.ownerUserId if request.ownerUserId is not None else current.ownerUserId
        )

        if next_owner_id is not None:
            self._require_user(next_owner_id)

        try:
            execute(
                self.connection,
                """
                update tenants
                set name = ?, slug = ?, owner_user_id = ?, updated_at = CURRENT_TIMESTAMP
                where id = ?
                """,
                (next_name, next_slug, next_owner_id, tenant_id),
            )
            if next_owner_id is not None and next_owner_id != current.ownerUserId:
                self._upsert_member(tenant_id, next_owner_id, TenantRole.ADMIN)
            self.connection.commit()
        except Exception as exc:
            if is_unique_violation(exc):
                raise ApiError(409, "TENANT_SLUG_EXISTS", "Tenant slug already exists") from exc
            raise
        return self.get(tenant_id)

    def update_status(self, tenant_id: str, status: str) -> Tenant:
        self.get(tenant_id)
        execute(
            self.connection,
            """
            update tenants
            set status = ?, updated_at = CURRENT_TIMESTAMP
            where id = ?
            """,
            (status, tenant_id),
        )
        self.connection.commit()
        return self.get(tenant_id)

    def update_subscription(
        self, tenant_id: str, request: UpdateTenantSubscriptionRequest
    ) -> Tenant:
        self.get(tenant_id)
        plan = self.plan_repo.get(request.planId)
        if not plan:
            raise ApiError(404, "PLAN_NOT_FOUND", "Plan not found")
        billing_period = request.billingPeriod
        _require_enabled_price(plan, billing_period)
        now = _now_iso()
        current_period_start = request.currentPeriodStart or now
        subscription_id = f"tenant_subscription_{uuid4().hex}"
        execute(
            self.connection,
            """
            update tenant_subscriptions
            set status = 'cancelled',
                current_period_end = coalesce(current_period_end, CURRENT_TIMESTAMP),
                updated_at = CURRENT_TIMESTAMP
            where tenant_id = ?
              and status in ('active', 'trialing', 'past_due')
            """,
            (tenant_id,),
        )
        execute(
            self.connection,
            """
            insert into tenant_subscriptions (
              id, tenant_id, plan_id, status, billing_period,
              current_period_start, current_period_end, cancel_at_period_end
            )
            values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                subscription_id,
                tenant_id,
                plan.id,
                request.status,
                billing_period,
                current_period_start,
                request.currentPeriodEnd,
                request.cancelAtPeriodEnd,
            ),
        )
        self.subscription_service._create_snapshot(subscription_id, plan, billing_period)
        self.connection.commit()
        return self.get(tenant_id)

    def list_members(self, tenant_id: str) -> list[TenantMember]:
        self._require_team_tenant(tenant_id)
        return self._list_members_raw(tenant_id)

    def _list_members_raw(self, tenant_id: str) -> list[TenantMember]:
        rows = fetch_all(
            self.connection,
            """
            select
              u.id as user_id,
              u.email,
              u.name,
              u.status,
              tm.role,
              tm.created_at as joined_at
            from tenant_members tm
            inner join users u on u.id = tm.user_id
            where tm.tenant_id = ?
            order by tm.created_at desc, u.id asc
            """,
            (tenant_id,),
        )
        return [_map_member(row) for row in rows]

    def add_member(self, tenant_id: str, request: AddTenantMemberRequest) -> TenantMember:
        self._require_team_tenant(tenant_id)
        self._require_user(request.userId)
        self._upsert_member(tenant_id, request.userId, request.role)
        self.connection.commit()
        return self._require_member(tenant_id, request.userId)

    def update_member(
        self, tenant_id: str, user_id: str, request: UpdateTenantMemberRequest
    ) -> TenantMember:
        self._require_team_tenant(tenant_id)
        current = self._require_member(tenant_id, user_id)
        if (
            current.role == TenantRole.ADMIN
            and request.role != TenantRole.ADMIN
            and self._count_tenant_admins(tenant_id) <= 1
        ):
            raise ApiError(409, "TENANT_LAST_ADMIN", "Cannot demote the last tenant admin")
        self._upsert_member(tenant_id, user_id, request.role)
        self.connection.commit()
        return self._require_member(tenant_id, user_id)

    def remove_member(self, tenant_id: str, user_id: str) -> None:
        self._require_team_tenant(tenant_id)
        current = self._require_member(tenant_id, user_id)
        if current.role == TenantRole.ADMIN and self._count_tenant_admins(tenant_id) <= 1:
            raise ApiError(409, "TENANT_LAST_ADMIN", "Cannot remove the last tenant admin")
        cursor = execute(
            self.connection,
            "delete from tenant_members where tenant_id = ? and user_id = ?",
            (tenant_id, user_id),
        )
        if rowcount(cursor) <= 0:
            raise ApiError(404, "MEMBER_NOT_FOUND", "User is not a member of this tenant")
        self.connection.commit()

    def _tenant_row(self, tenant_id: str) -> dict[str, Any] | None:
        return fetch_one(
            self.connection,
            """
            select
              t.id,
              t.type,
              t.name,
              t.slug,
              t.owner_user_id,
              owner.name as owner_user_name,
              owner.email as owner_user_email,
              t.status,
              t.created_at,
              t.updated_at,
              count(tm.id) as member_count
            from tenants t
            left join users owner on owner.id = t.owner_user_id
            left join tenant_members tm on tm.tenant_id = t.id
            where t.id = ?
            group by
              t.id, t.type, t.name, t.slug, t.owner_user_id, owner.name, owner.email,
              t.status, t.created_at, t.updated_at
            limit 1
            """,
            (tenant_id,),
        )

    def _require_user(self, user_id: str) -> dict[str, Any]:
        row = fetch_one(
            self.connection,
            "select id from users where id = ? limit 1",
            (user_id,),
        )
        if not row:
            raise ApiError(404, "USER_NOT_FOUND", "User not found")
        return row

    def _require_member(self, tenant_id: str, user_id: str) -> TenantMember:
        row = fetch_one(
            self.connection,
            """
            select
              u.id as user_id,
              u.email,
              u.name,
              u.status,
              tm.role,
              tm.created_at as joined_at
            from tenant_members tm
            inner join users u on u.id = tm.user_id
            where tm.tenant_id = ? and tm.user_id = ?
            limit 1
            """,
            (tenant_id, user_id),
        )
        if not row:
            raise ApiError(404, "MEMBER_NOT_FOUND", "User is not a member of this tenant")
        return _map_member(row)

    def _upsert_member(self, tenant_id: str, user_id: str, role: TenantRole) -> None:
        execute(
            self.connection,
            """
            insert into tenant_members (id, tenant_id, user_id, role)
            values (?, ?, ?, ?)
            on conflict (tenant_id, user_id) do update
            set role = excluded.role,
                updated_at = CURRENT_TIMESTAMP
            """,
            (f"member_{uuid4().hex}", tenant_id, user_id, role.value),
        )

    def _count_tenant_admins(self, tenant_id: str) -> int:
        row = fetch_one(
            self.connection,
            "select count(*) as count from tenant_members where tenant_id = ? and role = ?",
            (tenant_id, TenantRole.ADMIN.value),
        )
        return int(row["count"]) if row else 0

    def _require_team_tenant(self, tenant_id: str) -> Tenant:
        row = self._tenant_row(tenant_id)
        if not row:
            raise ApiError(404, "TENANT_NOT_FOUND", "Tenant not found")
        tenant = _map_tenant(row)
        if tenant.type != "team":
            raise ApiError(
                409,
                "TENANT_MEMBERS_UNSUPPORTED",
                "Member management is only available for team tenants",
            )
        return tenant

    def _hydrate_tenant(self, tenant: Tenant, *, include_members: bool) -> Tenant:
        subscription, plan, monthly_usage = self._tenant_subscription_context(tenant.id)
        tenant.currentSubscription = subscription
        tenant.currentPlan = plan
        tenant.monthlyUsage = monthly_usage
        tenant.orderSummary = TenantOrderSummary()
        tenant.members = self._list_members_raw(tenant.id) if include_members else []
        return tenant

    def _tenant_subscription_context(
        self, tenant_id: str
    ) -> tuple[TenantSubscriptionSummary | None, TenantPlanSummary | None, TenantMonthlyUsageSummary]:
        current = self.subscription_service.current_subscription(tenant_id)
        subscription = current.subscription
        snapshot = current.snapshot
        price_snapshot = snapshot.priceSnapshot
        entitlements = snapshot.entitlementsSnapshot
        status = _subscription_status(subscription.status, subscription.currentPeriodEnd)
        summary = TenantSubscriptionSummary(
            subscriptionId=subscription.id,
            planId=subscription.planId,
            planCode=snapshot.planCode,
            planName=snapshot.planName,
            billingPeriod=subscription.billingPeriod,
            status=status,
            rawStatus=subscription.status,
            currentPeriodStart=subscription.currentPeriodStart,
            currentPeriodEnd=subscription.currentPeriodEnd,
            daysUntilExpiry=_days_until(subscription.currentPeriodEnd),
            cancelAtPeriodEnd=subscription.cancelAtPeriodEnd,
            autoRenew=not subscription.cancelAtPeriodEnd and subscription.billingPeriod != "free",
            priceLabel=_price_label(price_snapshot),
        )
        plan_row = fetch_one(
            self.connection,
            "select code, name, type_label from plans where id = ? limit 1",
            (subscription.planId,),
        )
        plan = TenantPlanSummary(
            id=subscription.planId,
            code=str(plan_row["code"]) if plan_row else snapshot.planCode,
            name=str(plan_row["name"]) if plan_row else snapshot.planName,
            typeLabel=(
                str(plan_row["type_label"])
                if plan_row and plan_row["type_label"] is not None
                else None
            ),
            billingPeriod=subscription.billingPeriod,
            priceLabel=summary.priceLabel,
            priceSnapshot=price_snapshot,
            entitlementsSnapshot=entitlements,
        )
        monthly_usage = self._monthly_usage(tenant_id, summary, entitlements)
        return summary, plan, monthly_usage

    def _monthly_usage(
        self,
        tenant_id: str,
        subscription: TenantSubscriptionSummary,
        entitlements: dict[str, Any],
    ) -> TenantMonthlyUsageSummary:
        month_start = datetime.now(timezone.utc).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        ).isoformat()
        row = fetch_one(
            self.connection,
            """
            select count(*) as count
            from chat_turns
            where tenant_id = ?
              and created_at >= ?
              and is_internal = false
            """,
            (tenant_id, month_start),
        )
        question_used = int(row["count"]) if row else 0
        question_limit = int(entitlements.get("monthlyQuestionLimit", 0) or 0)
        token_limit = int(entitlements.get("monthlyTokenLimit", 0) or 0)
        token_used = 0
        status = _usage_status(
            subscription,
            question_used,
            question_limit,
            token_used,
            token_limit,
        )
        return TenantMonthlyUsageSummary(
            questionUsed=question_used,
            questionLimit=question_limit,
            tokenUsed=token_used,
            tokenLimit=token_limit,
            questionUsagePercent=_percent(question_used, question_limit),
            tokenUsagePercent=_percent(token_used, token_limit),
            status=status,
            isServicePaused=status in {"question_exhausted", "token_exhausted", "expired"},
        )


def _map_tenant(row: dict[str, Any]) -> Tenant:
    return Tenant(
        id=str(row["id"]),
        type=str(row["type"]),
        name=str(row["name"]),
        slug=str(row["slug"]),
        ownerUserId=str(row["owner_user_id"]) if row["owner_user_id"] is not None else None,
        ownerUserName=(
            str(row["owner_user_name"]) if row.get("owner_user_name") is not None else None
        ),
        ownerUserEmail=(
            str(row["owner_user_email"]) if row.get("owner_user_email") is not None else None
        ),
        status=str(row["status"]),
        memberCount=int(row["member_count"]),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _map_member(row: dict[str, Any]) -> TenantMember:
    return TenantMember(
        userId=str(row["user_id"]),
        email=str(row["email"]),
        name=str(row["name"]),
        status=str(row["status"]),
        role=TenantRole(str(row["role"])),
        joinedAt=str(row["joined_at"]),
    )


def _tenant_slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"{slug or 'tenant'}-{uuid4().hex[:8]}"


def _filter_tenants(
    items: list[Tenant],
    *,
    search: str | None,
    tenant_type: str | None,
    subscription_type: str | None,
    subscription_status: str | None,
) -> list[Tenant]:
    if search:
        needle = search.casefold()
        items = [
            item
            for item in items
            if needle in item.name.casefold()
            or needle in item.slug.casefold()
            or (item.ownerUserName is not None and needle in item.ownerUserName.casefold())
            or (item.ownerUserEmail is not None and needle in item.ownerUserEmail.casefold())
            or (
                item.currentPlan is not None
                and (
                    needle in item.currentPlan.name.casefold()
                    or needle in item.currentPlan.code.casefold()
                )
            )
        ]
    if tenant_type:
        items = [item for item in items if item.type == tenant_type]
    if subscription_type:
        expected = subscription_type.casefold()
        items = [
            item
            for item in items
            if item.currentSubscription is not None
            and (
                expected == item.currentSubscription.billingPeriod
                or (
                    item.currentPlan is not None
                    and (
                        expected in item.currentPlan.name.casefold()
                        or expected in item.currentPlan.code.casefold()
                        or (
                            item.currentPlan.typeLabel is not None
                            and expected in item.currentPlan.typeLabel.casefold()
                        )
                    )
                )
            )
        ]
    if subscription_status:
        expected = _normalize_subscription_filter(subscription_status)
        items = [
            item
            for item in items
            if item.currentSubscription is not None and item.currentSubscription.status == expected
        ]
    return items


def _sort_tenants(items: list[Tenant], sort: str | None) -> list[Tenant]:
    if sort == "expiresAt":
        return sorted(
            items,
            key=lambda item: (
                item.currentSubscription is None
                or item.currentSubscription.currentPeriodEnd is None,
                item.currentSubscription.currentPeriodEnd if item.currentSubscription else "",
            ),
        )
    if sort == "monthlyUsage":
        return sorted(items, key=lambda item: item.monthlyUsage.questionUsed, reverse=True)
    if sort == "subscriptionStart":
        return sorted(
            items,
            key=lambda item: (
                item.currentSubscription.currentPeriodStart
                if item.currentSubscription is not None
                else ""
            ),
            reverse=True,
        )
    if sort == "name":
        return sorted(items, key=lambda item: (item.name.casefold(), item.id))
    return items


def _normalize_subscription_filter(value: str) -> str:
    normalized = value.casefold()
    mapping = {
        "active": "active",
        "trialing": "active",
        "past_due": "active",
        "expiringsoon": "expiring_soon",
        "expiring_soon": "expiring_soon",
        "cancelled": "expired",
        "expired": "expired",
    }
    return mapping.get(normalized, normalized)


def _require_enabled_price(plan: Plan, billing_period: str) -> None:
    if any(price.billingPeriod == billing_period and price.isEnabled for price in plan.prices):
        return
    raise ApiError(
        400,
        "PLAN_PRICE_NOT_AVAILABLE",
        "The selected plan does not have an enabled price for this billing period",
    )


def _subscription_status(status: str, ends_at: str | None) -> str:
    if status in {"cancelled", "expired"}:
        return "expired"
    if ends_at is not None:
        days = _days_until(ends_at)
        if _parse_datetime(ends_at) <= datetime.now(timezone.utc):
            return "expired"
        if days is not None and days <= 14:
            return "expiring_soon"
    return "active"


def _usage_status(
    subscription: TenantSubscriptionSummary,
    question_used: int,
    question_limit: int,
    token_used: int,
    token_limit: int,
) -> str:
    if subscription.status == "expired":
        return "expired"
    if question_limit > 0 and question_used >= question_limit:
        return "question_exhausted"
    if token_limit > 0 and token_used >= token_limit:
        return "token_exhausted"
    if subscription.status == "expiring_soon":
        return "expiring_soon"
    return "normal"


def _price_label(price_snapshot: dict[str, Any]) -> str | None:
    billing_period = str(price_snapshot.get("billingPeriod") or "")
    amount = int(price_snapshot.get("amountCents") or 0)
    currency = str(price_snapshot.get("currency") or "CNY")
    if billing_period == "free":
        return "Free"
    if billing_period == "sales":
        return "Contact sales"
    symbol = "¥" if currency == "CNY" else f"{currency} "
    suffix = {"monthly": " / month", "yearly": " / year"}.get(billing_period, "")
    return f"{symbol}{amount / 100:g}{suffix}"


def _percent(used: int, limit: int) -> float:
    if limit <= 0:
        return 0
    return round(min((used / limit) * 100, 100), 2)


def _days_until(value: str | None) -> int | None:
    if value is None:
        return None
    delta = _parse_datetime(value) - datetime.now(timezone.utc)
    return max(delta.days, 0)


def _parse_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
