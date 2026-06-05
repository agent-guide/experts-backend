from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.core.errors import ApiError
from app.db import DatabaseConnection
from app.domain.auth import Principal
from app.domain.knowledge import (
    CreateKnowledgeBaseRequest,
    KnowledgeBase,
    UpdateKnowledgeBaseRequest,
)
from app.services.kb_authz import authorize_kb_access
from app.services.knowledge_base_repository import KnowledgeBaseRepository


class KnowledgeBaseService:
    def __init__(self, connection: DatabaseConnection) -> None:
        self.connection = connection
        self.repo = KnowledgeBaseRepository(connection)

    def create(
        self, principal: Principal, request: CreateKnowledgeBaseRequest
    ) -> KnowledgeBase:
        now = _now_iso()
        kb = KnowledgeBase(
            id=f"kb_{uuid4().hex}",
            ownerUserId=principal.user_id,
            name=request.name,
            description=request.description,
            status="active",
            metadata=request.metadata,
            createdAt=now,
            updatedAt=now,
        )
        self.repo.create(kb)
        created = self.repo.get(kb.id) or kb
        self.connection.commit()
        return created

    def get(self, principal: Principal, knowledge_base_id: str) -> KnowledgeBase:
        kb = self.repo.get(knowledge_base_id)
        if not kb:
            raise ApiError(404, "KB_NOT_FOUND", "Knowledge base not found")
        authorize_kb_access(principal, kb, "read")
        return kb

    def list(self, principal: Principal) -> list[KnowledgeBase]:
        return self.repo.list_for_platform()

    def update(
        self,
        principal: Principal,
        knowledge_base_id: str,
        request: UpdateKnowledgeBaseRequest,
    ) -> KnowledgeBase:
        kb = self.repo.get(knowledge_base_id)
        if not kb:
            raise ApiError(404, "KB_NOT_FOUND", "Knowledge base not found")
        authorize_kb_access(principal, kb, "update")

        updated = self.repo.update(
            knowledge_base_id,
            name=request.name or kb.name,
            description=request.description if request.description is not None else kb.description,
            metadata=request.metadata if request.metadata is not None else kb.metadata,
            updated_at=_now_iso(),
        )
        if not updated:
            raise ApiError(404, "KB_NOT_FOUND", "Knowledge base not found")
        self.connection.commit()
        return updated

    def delete(self, principal: Principal, knowledge_base_id: str) -> None:
        kb = self.repo.get(knowledge_base_id)
        if not kb:
            raise ApiError(404, "KB_NOT_FOUND", "Knowledge base not found")
        authorize_kb_access(principal, kb, "delete")
        # Soft delete: a hard delete would cascade documents/upload_sessions and strand their
        # MinIO objects. The base disappears from all reads immediately; GC
        # (DocumentService.purge_deleted_knowledge_bases) reclaims the objects, then hard-deletes.
        self.repo.soft_delete(knowledge_base_id, _now_iso())
        self.connection.commit()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
