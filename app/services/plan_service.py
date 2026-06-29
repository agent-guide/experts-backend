from __future__ import annotations

from uuid import uuid4

from app.core.errors import ApiError
from app.db import DatabaseConnection
from app.domain.plans import (
    CreatePlanRequest,
    Plan,
    ReplacePlanEntitlementsRequest,
    ReplacePlanExpertsRequest,
    ReplacePlanPricesRequest,
    UpdatePlanRequest,
)
from app.services._sql import is_unique_violation
from app.services.plan_repository import PlanRepository


class PlanService:
    def __init__(self, connection: DatabaseConnection) -> None:
        self.connection = connection
        self.repo = PlanRepository(connection)

    def list(self) -> list[Plan]:
        return self.repo.list()

    def list_market(self) -> list[Plan]:
        return self.repo.list(active_only=True)

    def get(self, plan_id: str) -> Plan:
        plan = self.repo.get(plan_id)
        if not plan:
            raise ApiError(404, "PLAN_NOT_FOUND", "Plan not found")
        return plan

    def create(self, request: CreatePlanRequest) -> Plan:
        plan_id = f"plan_{uuid4().hex}"
        code = (
            _normalize_code(request.code)
            if request.code is not None
            else self._generate_code_from_type_label(request.typeLabel)
        )
        try:
            if request.isRecommended:
                self.repo.clear_recommended_except()
            self.repo.insert(
                plan_id=plan_id,
                code=code,
                name=request.name,
                level=request.level,
                description=request.description,
                type_label=request.typeLabel,
                subtitle=request.subtitle,
                badge_label=request.badgeLabel,
                highlight_items=_unique_strings(request.highlightItems),
                upgrade_rules=request.upgradeRules,
                status=request.status,
                is_recommended=request.isRecommended,
                sort_order=request.sortOrder,
            )
            self.connection.commit()
        except Exception as exc:
            if is_unique_violation(exc):
                raise ApiError(409, "PLAN_CONFLICT", "Plan code or level already exists") from exc
            raise
        return self.get(plan_id)

    def update(self, plan_id: str, request: UpdatePlanRequest) -> Plan:
        current = self.get(plan_id)
        next_recommended = (
            request.isRecommended if request.isRecommended is not None else current.isRecommended
        )
        next_code = self._resolve_update_code(plan_id, current, request)
        try:
            if next_recommended:
                self.repo.clear_recommended_except(plan_id)
            self.repo.update(
                plan_id,
                code=next_code,
                name=request.name if request.name is not None else current.name,
                level=request.level if request.level is not None else current.level,
                description=(
                    request.description if request.description is not None else current.description
                ),
                type_label=request.typeLabel if request.typeLabel is not None else current.typeLabel,
                subtitle=request.subtitle if request.subtitle is not None else current.subtitle,
                badge_label=(
                    request.badgeLabel if request.badgeLabel is not None else current.badgeLabel
                ),
                highlight_items=(
                    _unique_strings(request.highlightItems)
                    if request.highlightItems is not None
                    else current.highlightItems
                ),
                upgrade_rules=(
                    request.upgradeRules if request.upgradeRules is not None else current.upgradeRules
                ),
                status=request.status if request.status is not None else current.status,
                is_recommended=next_recommended,
                sort_order=request.sortOrder if request.sortOrder is not None else current.sortOrder,
            )
            self.connection.commit()
        except Exception as exc:
            if is_unique_violation(exc):
                raise ApiError(409, "PLAN_CONFLICT", "Plan code or level already exists") from exc
            raise
        return self.get(plan_id)

    def _resolve_update_code(
        self, plan_id: str, current: Plan, request: UpdatePlanRequest
    ) -> str:
        if request.code is not None:
            return _normalize_code(request.code)
        if request.typeLabel is not None and request.typeLabel != current.typeLabel:
            return self._generate_code_from_type_label(request.typeLabel, current_plan_id=plan_id)
        return current.code

    def _generate_code_from_type_label(
        self, type_label: str | None, *, current_plan_id: str | None = None
    ) -> str:
        if not type_label:
            raise ApiError(400, "PLAN_TYPE_LABEL_REQUIRED", "Plan typeLabel is required")
        base_code = _base_code_for_type_label(type_label)
        candidate = base_code
        suffix = 2
        while True:
            owner_id = self.repo.plan_id_by_code(candidate)
            if owner_id is None or owner_id == current_plan_id:
                return candidate
            candidate = f"{base_code}_{suffix}"
            suffix += 1

    def replace_prices(self, plan_id: str, request: ReplacePlanPricesRequest) -> Plan:
        self.get(plan_id)
        seen = set()
        prices = []
        for item in request.items:
            key = (item.billingPeriod, item.currency.strip().upper())
            if key in seen:
                raise ApiError(409, "PLAN_PRICE_DUPLICATE", "Duplicate plan price")
            seen.add(key)
            prices.append(
                {
                    "billing_period": item.billingPeriod,
                    "currency": item.currency.strip().upper(),
                    "amount_cents": item.amountCents,
                    "discount_label": item.discountLabel,
                    "is_enabled": item.isEnabled,
                }
            )
        self.repo.replace_prices(plan_id, prices)
        self.connection.commit()
        return self.get(plan_id)

    def replace_entitlements(
        self, plan_id: str, request: ReplacePlanEntitlementsRequest
    ) -> Plan:
        self.get(plan_id)
        self.repo.replace_entitlements(
            plan_id,
            monthly_question_limit=request.monthlyQuestionLimit,
            monthly_token_limit=request.monthlyTokenLimit,
            seat_limit=request.seatLimit,
            single_turn_token_limit=request.singleTurnTokenLimit,
            model_tiers=_unique_strings(request.modelTiers),
            features=request.features,
        )
        self.connection.commit()
        return self.get(plan_id)

    def replace_experts(
        self, plan_id: str, request: ReplacePlanExpertsRequest
    ) -> Plan:
        self.get(plan_id)
        expert_ids = _unique_strings(request.expertIds)
        existing = self.repo.existing_expert_ids(expert_ids)
        missing = [eid for eid in expert_ids if eid not in existing]
        if missing:
            raise ApiError(404, "EXPERT_NOT_FOUND", "Expert not found", {"expertIds": missing})
        self.repo.replace_experts(plan_id, expert_ids)
        self.connection.commit()
        return self.get(plan_id)

    def delete(self, plan_id: str) -> None:
        plan = self.get(plan_id)
        if plan.code == "default":
            raise ApiError(409, "PLAN_DEFAULT_DELETE_FORBIDDEN", "Default plan cannot be deleted")
        if self.repo.has_subscriptions(plan_id):
            raise ApiError(409, "PLAN_HAS_SUBSCRIPTIONS", "Plan has subscriptions")
        if self.repo.delete(plan_id) <= 0:
            raise ApiError(404, "PLAN_NOT_FOUND", "Plan not found")
        self.connection.commit()


def _normalize_code(value: str) -> str:
    return value.strip().lower()


def _base_code_for_type_label(type_label: str) -> str:
    normalized = type_label.strip().lower()
    mapping = {
        "免费版": "free",
        "免费": "free",
        "free": "free",
        "默认套餐": "default",
        "默认": "default",
        "default": "default",
        "个人付费": "pro",
        "专业版": "pro",
        "pro": "pro",
        "paid": "pro",
        "团队": "business",
        "business": "business",
        "business 版": "business",
        "企业定制": "enterprise",
        "enterprise": "enterprise",
    }
    code = mapping.get(normalized)
    if code is None:
        raise ApiError(400, "PLAN_TYPE_LABEL_UNSUPPORTED", "Unsupported plan typeLabel")
    return code


def _unique_strings(values: list[str]) -> list[str]:
    return [value for value in dict.fromkeys(values) if value]
