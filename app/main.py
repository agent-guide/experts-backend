from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import install_error_handlers
from app.db import migrate_database


OPENAPI_TAGS = [
    {"name": "health", "description": "Service liveness checks."},
    {"name": "auth", "description": "Login, token refresh and logout."},
    {"name": "users", "description": "Regular users, platform staff and account lifecycle."},
    {"name": "tenants", "description": "Tenants, workspaces and tenant members."},
    {"name": "expert-categories", "description": "Create, query, update and delete expert categories."},
    {"name": "experts", "description": "Create, query, update, delete and switch expert status."},
    {"name": "expert-groups", "description": "Manage expert authorization groups."},
    {"name": "expert-market", "description": "Expert marketplace categories and published experts (requires sign-in)."},
    {"name": "plans", "description": "Manage expert subscription plans."},
    {"name": "plan-market", "description": "Signed-in user plan catalog and current subscription."},
    {"name": "rbac", "description": "Platform roles, tenant roles and member authorization."},
    {"name": "models", "description": "Models available to tenants."},
    {"name": "ops", "description": "System operations and cleanup."},
    {"name": "chat", "description": "Tenant chat sessions, turns and permission events."},
    {"name": "library", "description": "Personal user library files."},
    {"name": "knowledge-bases", "description": "Platform knowledge base management."},
    {"name": "docs", "description": "Knowledge base document upload, view, update and delete."},
    {"name": "builds", "description": "Knowledge base build placeholder endpoints."},
    {"name": "skills", "description": "Platform skill upload, view, update and delete."},
]

OPENAPI_OPERATION_SUMMARIES = {
    ("GET", "/health"): "Health check",
    ("POST", "/api/v1/auth/login"): "User login",
    ("POST", "/api/v1/auth/refresh"): "Refresh access token",
    ("POST", "/api/v1/auth/logout"): "Logout",
    ("POST", "/api/v1/users/register"): "Register a regular user",
    ("GET", "/api/v1/users"): "List regular users",
    ("POST", "/api/v1/users/platform/activate"): "Activate a platform user",
    ("GET", "/api/v1/users/platform"): "List platform users",
    ("POST", "/api/v1/users/platform"): "Create a platform user",
    ("GET", "/api/v1/users/{user_id}/tenants"): "List the user's tenants",
    ("GET", "/api/v1/users/{user_id}"): "Get user details",
    ("PATCH", "/api/v1/users/{user_id}"): "Update user profile",
    ("PATCH", "/api/v1/users/{user_id}/status"): "Update user status",
    ("GET", "/api/v1/tenants"): "List tenants",
    ("POST", "/api/v1/tenants"): "Create a tenant",
    ("GET", "/api/v1/tenants/{tenant_id}"): "Get tenant details",
    ("PATCH", "/api/v1/tenants/{tenant_id}"): "Update tenant",
    ("PATCH", "/api/v1/tenants/{tenant_id}/status"): "Update tenant status",
    ("GET", "/api/v1/tenants/{tenant_id}/members"): "List tenant members",
    ("POST", "/api/v1/tenants/{tenant_id}/members"): "Add a tenant member",
    ("PATCH", "/api/v1/tenants/{tenant_id}/members/{user_id}"): "Update tenant member role",
    ("DELETE", "/api/v1/tenants/{tenant_id}/members/{user_id}"): "Remove a tenant member",
    ("GET", "/api/v1/expert-categories"): "List expert categories",
    ("POST", "/api/v1/expert-categories"): "Create an expert category",
    ("GET", "/api/v1/expert-categories/{category_id}"): "Get expert category details",
    ("PATCH", "/api/v1/expert-categories/{category_id}"): "Update an expert category",
    ("DELETE", "/api/v1/expert-categories/{category_id}"): "Delete an expert category",
    ("GET", "/api/v1/experts"): "List experts",
    ("GET", "/api/v1/experts/search/name"): "Search experts by name",
    ("GET", "/api/v1/experts/search/category"): "Search experts by category",
    ("GET", "/api/v1/experts/search/status"): "Search experts by status",
    ("POST", "/api/v1/experts"): "Create an expert",
    ("GET", "/api/v1/experts/stats/summary"): "Get expert statistics",
    ("GET", "/api/v1/experts/{expert_id}"): "Get expert details",
    ("PATCH", "/api/v1/experts/{expert_id}"): "Update an expert",
    ("DELETE", "/api/v1/experts/{expert_id}"): "Delete an expert",
    ("PATCH", "/api/v1/experts/{expert_id}/status"): "Update expert status",
    ("GET", "/api/v1/expert-groups"): "List expert groups",
    ("POST", "/api/v1/expert-groups"): "Create an expert group",
    ("GET", "/api/v1/expert-groups/{group_id}"): "Get expert group details",
    ("PATCH", "/api/v1/expert-groups/{group_id}"): "Update an expert group",
    ("DELETE", "/api/v1/expert-groups/{group_id}"): "Delete an expert group",
    ("PUT", "/api/v1/expert-groups/{group_id}/experts"): "Replace expert group members",
    ("GET", "/api/v1/expert-market/categories"): "List public expert categories",
    ("GET", "/api/v1/expert-market/experts"): "List public experts",
    ("GET", "/api/v1/expert-market/experts/{expert_id}"): "Get public expert details",
    ("GET", "/api/v1/plans"): "List plans",
    ("POST", "/api/v1/plans"): "Create a plan",
    ("GET", "/api/v1/plans/{plan_id}"): "Get plan details",
    ("PATCH", "/api/v1/plans/{plan_id}"): "Update a plan",
    ("DELETE", "/api/v1/plans/{plan_id}"): "Delete a plan",
    ("PUT", "/api/v1/plans/{plan_id}/prices"): "Replace plan prices",
    ("PUT", "/api/v1/plans/{plan_id}/entitlements"): "Replace plan entitlements",
    ("PUT", "/api/v1/plans/{plan_id}/expert-groups"): "Replace plan expert groups",
    ("GET", "/api/v1/plan-market/plans"): "List market plans",
    ("GET", "/api/v1/plan-market/current-subscription"): "Get current subscription",
    ("GET", "/api/v1/rbac/tenant/users"): "List current tenant users",
    ("POST", "/api/v1/rbac/tenant/users/{user_id}/roles"): "Grant or update tenant role",
    ("DELETE", "/api/v1/rbac/tenant/users/{user_id}"): "Remove current tenant member",
    ("GET", "/api/v1/rbac/platform/roles"): "List platform roles",
    ("POST", "/api/v1/rbac/platform/users/{user_id}/roles"): "Grant platform role",
    ("DELETE", "/api/v1/rbac/platform/users/{user_id}/roles/{role}"): "Revoke platform role",
    ("GET", "/api/v1/models/llm"): "List LLM models",
    ("GET", "/api/v1/models/embedding"): "Get embedding model info",
    ("GET", "/api/v1/ops/metrics"): "Get system metrics",
    ("POST", "/api/v1/ops/storage/gc"): "Run object storage GC",
    ("POST", "/api/v1/chat/sessions"): "Create a chat session",
    ("GET", "/api/v1/chat/sessions"): "List chat sessions",
    ("GET", "/api/v1/chat/sessions/{session_id}"): "Get chat session details",
    ("DELETE", "/api/v1/chat/sessions/{session_id}"): "Delete a chat session",
    ("GET", "/api/v1/chat/sessions/{session_id}/messages"): "List chat messages",
    ("PATCH", "/api/v1/chat/sessions/{session_id}/title"): "Rename a chat session",
    ("PATCH", "/api/v1/chat/sessions/{session_id}/pin"): "Pin or unpin a chat session",
    ("PATCH", "/api/v1/chat/sessions/{session_id}/archive"): "Archive or unarchive a chat session",
    ("POST", "/api/v1/chat/sessions/{session_id}/turns"): "Create and stream a chat turn",
    ("POST", "/api/v1/chat/turns/{turn_id}/cancel"): "Cancel a chat turn",
    ("GET", "/api/v1/chat/turns/{turn_id}/events"): "Stream chat turn events",
    ("POST", "/api/v1/chat/permissions/{permission_id}"): "Resolve a chat permission request",
    ("GET", "/api/v1/library/files"): "List personal library files",
    ("POST", "/api/v1/library/files"): "Upload a personal library file",
    ("GET", "/api/v1/library/files/{file_id}/preview"): "Preview a personal library file",
    ("GET", "/api/v1/library/files/{file_id}/download"): "Download a personal library file",
    ("DELETE", "/api/v1/library/files/{file_id}"): "Delete a personal library file",
    ("POST", "/api/v1/knowledge-bases"): "Create a knowledge base",
    ("GET", "/api/v1/knowledge-bases"): "List knowledge bases",
    ("GET", "/api/v1/knowledge-bases/{knowledge_base_id}"): "Get knowledge base details",
    ("PATCH", "/api/v1/knowledge-bases/{knowledge_base_id}"): "Update a knowledge base",
    ("DELETE", "/api/v1/knowledge-bases/{knowledge_base_id}"): "Delete a knowledge base",
    ("POST", "/api/v1/knowledge-bases/{knowledge_base_id}/docs/upload-url"): "Create a document upload URL",
    ("POST", "/api/v1/knowledge-bases/{knowledge_base_id}/docs/upload-urls"): "Create document upload URLs",
    ("POST", "/api/v1/knowledge-bases/{knowledge_base_id}/docs/complete-upload"): "Complete a document upload",
    ("POST", "/api/v1/knowledge-bases/{knowledge_base_id}/docs/complete-uploads"): "Complete document uploads",
    ("GET", "/api/v1/knowledge-bases/{knowledge_base_id}/docs"): "List knowledge base documents",
    ("GET", "/api/v1/knowledge-bases/{knowledge_base_id}/docs/{document_id}"): "Get document details",
    ("PATCH", "/api/v1/knowledge-bases/{knowledge_base_id}/docs/{document_id}"): "Update document metadata",
    ("DELETE", "/api/v1/knowledge-bases/{knowledge_base_id}/docs/{document_id}"): "Delete a document",
    ("GET", "/api/v1/knowledge-bases/{knowledge_base_id}/docs/{document_id}/download-url"): "Get a document download URL",
    ("POST", "/api/v1/knowledge-bases/{knowledge_base_id}/build"): "Trigger a knowledge base build",
    ("GET", "/api/v1/knowledge-bases/{knowledge_base_id}/builds"): "List knowledge base builds",
    ("GET", "/api/v1/knowledge-bases/{knowledge_base_id}/builds/{build_id}"): "Get knowledge base build details",
    ("POST", "/api/v1/knowledge-bases/{knowledge_base_id}/builds/{build_id}/cancel"): "Cancel a knowledge base build",
    ("POST", "/api/v1/skills"): "Upload a skill",
    ("GET", "/api/v1/skills"): "List skills",
    ("GET", "/api/v1/skills/{slug}"): "Get skill details",
    ("PUT", "/api/v1/skills/{slug}"): "Update a skill",
    ("DELETE", "/api/v1/skills/{slug}"): "Delete a skill",
    ("GET", "/api/v1/skills/{slug}/file"): "Get a skill file",
}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if settings.database_auto_migrate:
            migrate_database(settings)
        yield

    app = FastAPI(
        title="Amazon Experts Backend API",
        version="0.1.0",
        description=(
            "Swagger/OpenAPI documentation for the Amazon Experts backend service. "
            "Platform APIs do not require x-tenant-id; tenant APIs require x-tenant-id "
            "in the request header."
        ),
        openapi_tags=OPENAPI_TAGS,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    install_error_handlers(app)
    app.dependency_overrides[get_settings] = lambda: settings

    @app.get("/health", tags=["health"], summary="Health check")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "amazon-experts-backend"}

    app.include_router(api_router, prefix="/api/v1")
    _apply_operation_summaries(app)
    return app


def _apply_operation_summaries(app: FastAPI) -> None:
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods or set():
            summary = OPENAPI_OPERATION_SUMMARIES.get((method, route.path))
            if summary:
                route.summary = summary


app = create_app()
