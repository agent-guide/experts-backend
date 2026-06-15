from typing import Any, Literal

from pydantic import BaseModel, Field

from app.domain.auth import TenantRole
from app.domain.plans import BillingPeriod, SubscriptionStatus


TenantType = Literal["personal", "team"]
TenantStatus = Literal["active", "disabled"]


class Tenant(BaseModel):
    id: str
    type: TenantType
    name: str
    slug: str
    ownerUserId: str | None = None
    ownerUserName: str | None = None
    ownerUserEmail: str | None = None
    status: TenantStatus
    memberCount: int
    currentSubscription: "TenantSubscriptionSummary | None" = None
    currentPlan: "TenantPlanSummary | None" = None
    monthlyUsage: "TenantMonthlyUsageSummary" = Field(default_factory=lambda: TenantMonthlyUsageSummary())
    orderSummary: "TenantOrderSummary" = Field(default_factory=lambda: TenantOrderSummary())
    members: list["TenantMember"] = Field(default_factory=list)
    createdAt: str
    updatedAt: str


class TenantMember(BaseModel):
    userId: str
    email: str
    name: str
    status: str
    role: TenantRole
    joinedAt: str


class CreateTenantRequest(BaseModel):
    name: str
    slug: str | None = None
    ownerUserId: str


class UpdateTenantRequest(BaseModel):
    name: str | None = None
    slug: str | None = None
    ownerUserId: str | None = None


class UpdateTenantStatusRequest(BaseModel):
    status: TenantStatus


class UpdateTenantSubscriptionRequest(BaseModel):
    planId: str
    billingPeriod: BillingPeriod
    status: SubscriptionStatus = "active"
    currentPeriodStart: str | None = None
    currentPeriodEnd: str | None = None
    cancelAtPeriodEnd: bool = False


class TenantPlanSummary(BaseModel):
    id: str
    code: str
    name: str
    typeLabel: str | None = None
    billingPeriod: BillingPeriod
    priceLabel: str | None = None
    priceSnapshot: dict[str, Any] = Field(default_factory=dict)
    entitlementsSnapshot: dict[str, Any] = Field(default_factory=dict)


class TenantSubscriptionSummary(BaseModel):
    subscriptionId: str
    planId: str
    planCode: str
    planName: str
    billingPeriod: BillingPeriod
    status: str
    rawStatus: SubscriptionStatus
    currentPeriodStart: str
    currentPeriodEnd: str | None = None
    daysUntilExpiry: int | None = None
    cancelAtPeriodEnd: bool
    autoRenew: bool
    priceLabel: str | None = None


class TenantMonthlyUsageSummary(BaseModel):
    questionUsed: int = 0
    questionLimit: int = 0
    tokenUsed: int = 0
    tokenLimit: int = 0
    questionUsagePercent: float = 0
    tokenUsagePercent: float = 0
    status: str = "normal"
    isServicePaused: bool = False


class TenantOrderItem(BaseModel):
    orderNo: str
    planName: str | None = None
    billingPeriod: BillingPeriod | None = None
    amountCents: int = 0
    paidAt: str | None = None
    status: str


class TenantOrderSummary(BaseModel):
    totalAmountCents: int = 0
    orderCount: int = 0
    recentOrders: list[TenantOrderItem] = Field(default_factory=list)


class AddTenantMemberRequest(BaseModel):
    userId: str
    role: TenantRole = TenantRole.MEMBER


class UpdateTenantMemberRequest(BaseModel):
    role: TenantRole


class TenantListResponse(BaseModel):
    items: list[Tenant]
    total: int = 0
    page: int = 1
    pageSize: int = 50


class TenantMemberListResponse(BaseModel):
    items: list[TenantMember]
