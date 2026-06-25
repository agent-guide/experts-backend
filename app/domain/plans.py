from typing import Any, Literal

from pydantic import BaseModel, Field


PlanStatus = Literal["active", "disabled"]
BillingPeriod = Literal["free", "monthly", "yearly", "sales"]
SubscriptionStatus = Literal["active", "trialing", "past_due", "cancelled", "expired"]


class PlanPrice(BaseModel):
    id: str
    planId: str
    billingPeriod: BillingPeriod
    currency: str
    amountCents: int
    discountLabel: str | None = None
    isEnabled: bool
    createdAt: str
    updatedAt: str


class ReplacePlanPriceRequest(BaseModel):
    billingPeriod: BillingPeriod
    currency: str
    amountCents: int = Field(ge=0)
    discountLabel: str | None = None
    isEnabled: bool = True


class ReplacePlanPricesRequest(BaseModel):
    items: list[ReplacePlanPriceRequest] = Field(default_factory=list)


class PlanEntitlements(BaseModel):
    id: str
    planId: str
    monthlyQuestionLimit: int
    monthlyTokenLimit: int
    seatLimit: int
    singleTurnTokenLimit: int | None = None
    modelTiers: list[str] = Field(default_factory=list)
    features: dict[str, Any] = Field(default_factory=dict)
    createdAt: str
    updatedAt: str


class ReplacePlanEntitlementsRequest(BaseModel):
    monthlyQuestionLimit: int = Field(ge=0)
    monthlyTokenLimit: int = Field(ge=0)
    seatLimit: int = Field(ge=1)
    singleTurnTokenLimit: int | None = Field(default=None, ge=0)
    modelTiers: list[str] = Field(default_factory=list)
    features: dict[str, Any] = Field(default_factory=dict)


class Plan(BaseModel):
    id: str
    code: str
    name: str
    level: int
    description: str
    typeLabel: str | None = None
    subtitle: str | None = None
    badgeLabel: str | None = None
    highlightItems: list[str] = Field(default_factory=list)
    upgradeRules: dict[str, Any] = Field(default_factory=dict)
    status: PlanStatus
    isRecommended: bool
    sortOrder: int
    subscriptionCount: int = 0
    prices: list[PlanPrice] = Field(default_factory=list)
    entitlements: PlanEntitlements | None = None
    expertIds: list[str] = Field(default_factory=list)
    createdAt: str
    updatedAt: str


class CreatePlanRequest(BaseModel):
    code: str | None = None
    name: str
    level: int = Field(ge=1, le=99)
    description: str
    typeLabel: str | None = None
    subtitle: str | None = None
    badgeLabel: str | None = None
    highlightItems: list[str] = Field(default_factory=list)
    upgradeRules: dict[str, Any] = Field(default_factory=dict)
    status: PlanStatus = "active"
    isRecommended: bool = False
    sortOrder: int = Field(default=0, ge=0, le=9999)


class UpdatePlanRequest(BaseModel):
    code: str | None = None
    name: str | None = None
    level: int | None = Field(default=None, ge=1, le=99)
    description: str | None = None
    typeLabel: str | None = None
    subtitle: str | None = None
    badgeLabel: str | None = None
    highlightItems: list[str] | None = None
    upgradeRules: dict[str, Any] | None = None
    status: PlanStatus | None = None
    isRecommended: bool | None = None
    sortOrder: int | None = Field(default=None, ge=0, le=9999)


class ReplacePlanExpertsRequest(BaseModel):
    expertIds: list[str] = Field(default_factory=list)


class PlanListResponse(BaseModel):
    items: list[Plan]


class SubscriptionEntitlementSnapshot(BaseModel):
    id: str
    subscriptionId: str
    planCode: str
    planName: str
    billingPeriod: BillingPeriod
    priceSnapshot: dict[str, Any] = Field(default_factory=dict)
    entitlementsSnapshot: dict[str, Any] = Field(default_factory=dict)
    startsAt: str
    endsAt: str | None = None
    createdAt: str


class TenantSubscription(BaseModel):
    id: str
    tenantId: str
    planId: str
    status: SubscriptionStatus
    billingPeriod: BillingPeriod
    currentPeriodStart: str
    currentPeriodEnd: str | None = None
    cancelAtPeriodEnd: bool
    createdAt: str
    updatedAt: str


class CurrentSubscriptionResponse(BaseModel):
    subscription: TenantSubscription
    snapshot: SubscriptionEntitlementSnapshot
