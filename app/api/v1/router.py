from fastapi import APIRouter

from app.api.v1.routers import (
    auth,
    builds,
    chat,
    documents,
    expert_categories,
    experts,
    knowledge_bases,
    models,
    ops,
    rbac,
    skills,
    tenants,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(users.router, prefix="/users", tags=["用户管理"])
api_router.include_router(tenants.router, prefix="/tenants", tags=["租户管理"])
api_router.include_router(
    expert_categories.router,
    prefix="/expert-categories",
    tags=["专家分类"],
)
api_router.include_router(experts.router, prefix="/experts", tags=["专家管理"])
api_router.include_router(rbac.router, prefix="/rbac", tags=["权限管理"])
api_router.include_router(models.router, prefix="/models", tags=["模型"])
api_router.include_router(ops.router, prefix="/ops", tags=["运维"])
api_router.include_router(chat.router, prefix="/chat", tags=["聊天"])
api_router.include_router(knowledge_bases.router, prefix="/knowledge-bases", tags=["知识库"])
# Documents and builds are nested under a knowledge base. There are no top-level /documents or
# /uploads routes any more (see KNOWLEDGE_BASE_STORAGE_AND_BUILD_DESIGN.md section 4).
api_router.include_router(
    documents.router,
    prefix="/knowledge-bases/{knowledge_base_id}/docs",
    tags=["文档"],
)
api_router.include_router(
    builds.router,
    prefix="/knowledge-bases/{knowledge_base_id}",
    tags=["构建"],
)
api_router.include_router(skills.router, prefix="/skills", tags=["技能"])
