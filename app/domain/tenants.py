from typing import Literal

from pydantic import BaseModel

from app.domain.auth import TenantRole


TenantType = Literal["personal", "team"]
TenantStatus = Literal["active", "disabled"]


class Tenant(BaseModel):
    id: str
    type: TenantType
    name: str
    slug: str
    ownerUserId: str | None = None
    ownerUserName: str | None = None
    status: TenantStatus
    memberCount: int
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


class AddTenantMemberRequest(BaseModel):
    userId: str
    role: TenantRole = TenantRole.MEMBER


class UpdateTenantMemberRequest(BaseModel):
    role: TenantRole


class TenantListResponse(BaseModel):
    items: list[Tenant]


class TenantMemberListResponse(BaseModel):
    items: list[TenantMember]
