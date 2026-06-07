from fastapi import APIRouter, Depends

from app.api.deps import get_database, require_platform_permission
from app.db import DatabaseConnection
from app.domain.auth import Principal
from app.domain.experts import (
    CreateExpertCategoryRequest,
    ExpertCategory,
    ExpertCategoryListResponse,
    UpdateExpertCategoryRequest,
)
from app.services.expert_category_service import ExpertCategoryService

router = APIRouter()


@router.get("", response_model=ExpertCategoryListResponse)
async def list_expert_categories(
    principal: Principal = Depends(require_platform_permission("expert:read")),
    connection: DatabaseConnection = Depends(get_database),
) -> ExpertCategoryListResponse:
    return ExpertCategoryListResponse(items=ExpertCategoryService(connection).list())


@router.post("", response_model=ExpertCategory, status_code=201)
async def create_expert_category(
    body: CreateExpertCategoryRequest,
    principal: Principal = Depends(require_platform_permission("expert:write")),
    connection: DatabaseConnection = Depends(get_database),
) -> ExpertCategory:
    return ExpertCategoryService(connection).create(body)


@router.get("/{category_id}", response_model=ExpertCategory)
async def get_expert_category(
    category_id: str,
    principal: Principal = Depends(require_platform_permission("expert:read")),
    connection: DatabaseConnection = Depends(get_database),
) -> ExpertCategory:
    return ExpertCategoryService(connection).get(category_id)


@router.patch("/{category_id}", response_model=ExpertCategory)
async def update_expert_category(
    category_id: str,
    body: UpdateExpertCategoryRequest,
    principal: Principal = Depends(require_platform_permission("expert:write")),
    connection: DatabaseConnection = Depends(get_database),
) -> ExpertCategory:
    return ExpertCategoryService(connection).update(category_id, body)


@router.delete("/{category_id}", status_code=204)
async def delete_expert_category(
    category_id: str,
    principal: Principal = Depends(require_platform_permission("expert:write")),
    connection: DatabaseConnection = Depends(get_database),
) -> None:
    ExpertCategoryService(connection).delete(category_id)
    return None
