from fastapi import APIRouter, Depends

from app.api.deps import get_database, require_platform_permission
from app.db import DatabaseConnection
from app.domain.auth import Principal
from app.domain.plans import (
    CreateExpertGroupRequest,
    ExpertGroup,
    ExpertGroupListResponse,
    ReplaceExpertGroupMembersRequest,
    UpdateExpertGroupRequest,
)
from app.services.expert_group_service import ExpertGroupService

router = APIRouter()


@router.get("", response_model=ExpertGroupListResponse)
async def list_expert_groups(
    principal: Principal = Depends(require_platform_permission("expert:read")),
    connection: DatabaseConnection = Depends(get_database),
) -> ExpertGroupListResponse:
    return ExpertGroupListResponse(items=ExpertGroupService(connection).list())


@router.post("", response_model=ExpertGroup, status_code=201)
async def create_expert_group(
    body: CreateExpertGroupRequest,
    principal: Principal = Depends(require_platform_permission("expert:write")),
    connection: DatabaseConnection = Depends(get_database),
) -> ExpertGroup:
    return ExpertGroupService(connection).create(body)


@router.get("/{group_id}", response_model=ExpertGroup)
async def get_expert_group(
    group_id: str,
    principal: Principal = Depends(require_platform_permission("expert:read")),
    connection: DatabaseConnection = Depends(get_database),
) -> ExpertGroup:
    return ExpertGroupService(connection).get(group_id)


@router.patch("/{group_id}", response_model=ExpertGroup)
async def update_expert_group(
    group_id: str,
    body: UpdateExpertGroupRequest,
    principal: Principal = Depends(require_platform_permission("expert:write")),
    connection: DatabaseConnection = Depends(get_database),
) -> ExpertGroup:
    return ExpertGroupService(connection).update(group_id, body)


@router.put("/{group_id}/experts", response_model=ExpertGroup)
async def replace_expert_group_members(
    group_id: str,
    body: ReplaceExpertGroupMembersRequest,
    principal: Principal = Depends(require_platform_permission("expert:write")),
    connection: DatabaseConnection = Depends(get_database),
) -> ExpertGroup:
    return ExpertGroupService(connection).replace_members(group_id, body)


@router.delete("/{group_id}", status_code=204)
async def delete_expert_group(
    group_id: str,
    principal: Principal = Depends(require_platform_permission("expert:write")),
    connection: DatabaseConnection = Depends(get_database),
) -> None:
    ExpertGroupService(connection).delete(group_id)
    return None
