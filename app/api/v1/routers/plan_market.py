from fastapi import APIRouter, Depends

from app.api.deps import get_database, require_principal
from app.db import DatabaseConnection
from app.domain.auth import Principal
from app.domain.plans import CurrentSubscriptionResponse, PlanListResponse
from app.services.plan_service import PlanService
from app.services.subscription_service import SubscriptionService

router = APIRouter()


@router.get("/plans", response_model=PlanListResponse)
async def list_market_plans(
    principal: Principal = Depends(require_principal),
    connection: DatabaseConnection = Depends(get_database),
) -> PlanListResponse:
    return PlanListResponse(items=PlanService(connection).list_market())


@router.get("/current-subscription", response_model=CurrentSubscriptionResponse)
async def get_current_subscription(
    principal: Principal = Depends(require_principal),
    connection: DatabaseConnection = Depends(get_database),
) -> CurrentSubscriptionResponse:
    return SubscriptionService(connection).current_subscription(principal.active_tenant_id)
