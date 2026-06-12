from __future__ import annotations

from uuid import uuid4

from app.core.errors import ApiError
from app.db import DatabaseConnection
from app.domain.plans import (
    CreateExpertGroupRequest,
    ExpertGroup,
    ReplaceExpertGroupMembersRequest,
    UpdateExpertGroupRequest,
)
from app.services._sql import is_unique_violation
from app.services.expert_group_repository import ExpertGroupRepository


class ExpertGroupService:
    def __init__(self, connection: DatabaseConnection) -> None:
        self.connection = connection
        self.repo = ExpertGroupRepository(connection)

    def list(self) -> list[ExpertGroup]:
        return self.repo.list()

    def get(self, group_id: str) -> ExpertGroup:
        group = self.repo.get(group_id)
        if not group:
            raise ApiError(404, "EXPERT_GROUP_NOT_FOUND", "Expert group not found")
        return group

    def create(self, request: CreateExpertGroupRequest) -> ExpertGroup:
        group_id = f"expert_group_{uuid4().hex}"
        try:
            self.repo.insert(
                group_id=group_id,
                code=_normalize_code(request.code),
                name=request.name,
                description=request.description,
                sort_order=request.sortOrder,
            )
            self.connection.commit()
        except Exception as exc:
            if is_unique_violation(exc):
                raise ApiError(409, "EXPERT_GROUP_CODE_EXISTS", "Expert group code exists") from exc
            raise
        return self.get(group_id)

    def update(self, group_id: str, request: UpdateExpertGroupRequest) -> ExpertGroup:
        current = self.get(group_id)
        try:
            self.repo.update(
                group_id,
                code=_normalize_code(request.code) if request.code is not None else current.code,
                name=request.name if request.name is not None else current.name,
                description=(
                    request.description if request.description is not None else current.description
                ),
                sort_order=request.sortOrder if request.sortOrder is not None else current.sortOrder,
            )
            self.connection.commit()
        except Exception as exc:
            if is_unique_violation(exc):
                raise ApiError(409, "EXPERT_GROUP_CODE_EXISTS", "Expert group code exists") from exc
            raise
        return self.get(group_id)

    def replace_members(
        self, group_id: str, request: ReplaceExpertGroupMembersRequest
    ) -> ExpertGroup:
        self.get(group_id)
        expert_ids = _unique_strings(request.expertIds)
        existing = self.repo.existing_expert_ids(expert_ids)
        missing = [expert_id for expert_id in expert_ids if expert_id not in existing]
        if missing:
            raise ApiError(404, "EXPERT_NOT_FOUND", "Expert not found", {"expertIds": missing})
        self.repo.replace_members(group_id, expert_ids)
        self.connection.commit()
        return self.get(group_id)

    def delete(self, group_id: str) -> None:
        self.get(group_id)
        if self.repo.is_used_by_plan(group_id):
            raise ApiError(
                409,
                "EXPERT_GROUP_IN_USE",
                "Expert group is used by one or more plans",
            )
        if self.repo.delete(group_id) <= 0:
            raise ApiError(404, "EXPERT_GROUP_NOT_FOUND", "Expert group not found")
        self.connection.commit()


def _normalize_code(value: str) -> str:
    return value.strip().lower()


def _unique_strings(values: list[str]) -> list[str]:
    return [value for value in dict.fromkeys(values) if value]
