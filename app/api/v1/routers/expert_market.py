from fastapi import APIRouter, Depends, Query

from app.api.deps import get_database
from app.db import DatabaseConnection
from app.domain.experts import (
    ExpertMarketCategoryListResponse,
    ExpertMarketExpert,
    ExpertMarketExpertListResponse,
)
from app.services.expert_category_service import ExpertCategoryService
from app.services.expert_service import ExpertService

router = APIRouter()


@router.get("/categories", response_model=ExpertMarketCategoryListResponse)
async def list_market_categories(
    connection: DatabaseConnection = Depends(get_database),
) -> ExpertMarketCategoryListResponse:
    return ExpertMarketCategoryListResponse(
        items=ExpertCategoryService(connection).list_market_categories()
    )


@router.get("/experts", response_model=ExpertMarketExpertListResponse)
async def list_market_experts(
    category_id: str | None = Query(default=None, alias="categoryId", min_length=1),
    connection: DatabaseConnection = Depends(get_database),
) -> ExpertMarketExpertListResponse:
    return ExpertMarketExpertListResponse(
        items=ExpertService(connection).list_market_experts(category_id=category_id)
    )


@router.get("/experts/{expert_id}", response_model=ExpertMarketExpert)
async def get_market_expert(
    expert_id: str,
    connection: DatabaseConnection = Depends(get_database),
) -> ExpertMarketExpert:
    return ExpertService(connection).get_market_expert(expert_id)
