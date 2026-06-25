from fastapi import APIRouter, Depends

from app.api.deps import get_database, require_platform_permission
from app.db import DatabaseConnection
from app.domain.auth import Principal
from app.domain.plans import (
    CreatePlanRequest,
    Plan,
    PlanListResponse,
    ReplacePlanEntitlementsRequest,
    ReplacePlanExpertsRequest,
    ReplacePlanPricesRequest,
    UpdatePlanRequest,
)
from app.services.plan_service import PlanService

router = APIRouter()


@router.get("", response_model=PlanListResponse)
async def list_plans(
    principal: Principal = Depends(require_platform_permission("plan:read")),
    connection: DatabaseConnection = Depends(get_database),
) -> PlanListResponse:
    return PlanListResponse(items=PlanService(connection).list())


@router.post("", response_model=Plan, status_code=201)
async def create_plan(
    body: CreatePlanRequest,
    principal: Principal = Depends(require_platform_permission("plan:write")),
    connection: DatabaseConnection = Depends(get_database),
) -> Plan:
    return PlanService(connection).create(body)


@router.get("/{plan_id}", response_model=Plan)
async def get_plan(
    plan_id: str,
    principal: Principal = Depends(require_platform_permission("plan:read")),
    connection: DatabaseConnection = Depends(get_database),
) -> Plan:
    return PlanService(connection).get(plan_id)


@router.patch("/{plan_id}", response_model=Plan)
async def update_plan(
    plan_id: str,
    body: UpdatePlanRequest,
    principal: Principal = Depends(require_platform_permission("plan:write")),
    connection: DatabaseConnection = Depends(get_database),
) -> Plan:
    return PlanService(connection).update(plan_id, body)


@router.put("/{plan_id}/prices", response_model=Plan)
async def replace_plan_prices(
    plan_id: str,
    body: ReplacePlanPricesRequest,
    principal: Principal = Depends(require_platform_permission("plan:write")),
    connection: DatabaseConnection = Depends(get_database),
) -> Plan:
    return PlanService(connection).replace_prices(plan_id, body)


@router.put("/{plan_id}/entitlements", response_model=Plan)
async def replace_plan_entitlements(
    plan_id: str,
    body: ReplacePlanEntitlementsRequest,
    principal: Principal = Depends(require_platform_permission("plan:write")),
    connection: DatabaseConnection = Depends(get_database),
) -> Plan:
    return PlanService(connection).replace_entitlements(plan_id, body)


@router.put("/{plan_id}/experts", response_model=Plan)
async def replace_plan_experts(
    plan_id: str,
    body: ReplacePlanExpertsRequest,
    principal: Principal = Depends(require_platform_permission("plan:write")),
    connection: DatabaseConnection = Depends(get_database),
) -> Plan:
    return PlanService(connection).replace_experts(plan_id, body)


@router.delete("/{plan_id}", status_code=204)
async def delete_plan(
    plan_id: str,
    principal: Principal = Depends(require_platform_permission("plan:write")),
    connection: DatabaseConnection = Depends(get_database),
) -> None:
    PlanService(connection).delete(plan_id)
    return None
