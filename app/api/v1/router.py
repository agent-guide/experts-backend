from fastapi import APIRouter

from app.api.v1.routers import (
    auth,
    builds,
    chat,
    documents,
    expert_categories,
    expert_groups,
    expert_market,
    experts,
    knowledge_bases,
    models,
    ops,
    plan_market,
    plans,
    rbac,
    skills,
    tenants,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(tenants.router, prefix="/tenants", tags=["tenants"])
api_router.include_router(
    expert_categories.router,
    prefix="/expert-categories",
    tags=["expert-categories"],
)
api_router.include_router(experts.router, prefix="/experts", tags=["experts"])
api_router.include_router(
    expert_groups.router,
    prefix="/expert-groups",
    tags=["expert-groups"],
)
api_router.include_router(
    expert_market.router,
    prefix="/expert-market",
    tags=["expert-market"],
)
api_router.include_router(plans.router, prefix="/plans", tags=["plans"])
api_router.include_router(
    plan_market.router,
    prefix="/plan-market",
    tags=["plan-market"],
)
api_router.include_router(rbac.router, prefix="/rbac", tags=["rbac"])
api_router.include_router(models.router, prefix="/models", tags=["models"])
api_router.include_router(ops.router, prefix="/ops", tags=["ops"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(knowledge_bases.router, prefix="/knowledge-bases", tags=["knowledge-bases"])
# Documents and builds are nested under a knowledge base. There are no top-level /documents or
# /uploads routes any more (see KNOWLEDGE_BASE_STORAGE_AND_BUILD_DESIGN.md section 4).
api_router.include_router(
    documents.router,
    prefix="/knowledge-bases/{knowledge_base_id}/docs",
    tags=["docs"],
)
api_router.include_router(
    builds.router,
    prefix="/knowledge-bases/{knowledge_base_id}",
    tags=["builds"],
)
api_router.include_router(skills.router, prefix="/skills", tags=["skills"])
