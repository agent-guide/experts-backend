from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import install_error_handlers
from app.db import migrate_database


OPENAPI_TAGS = [
    {"name": "健康检查", "description": "服务存活状态检查。"},
    {"name": "认证", "description": "登录、刷新令牌和退出登录。"},
    {"name": "用户管理", "description": "普通用户、平台人员和账号生命周期管理。"},
    {"name": "租户管理", "description": "平台侧租户、工作区和租户成员管理。"},
    {"name": "专家分类", "description": "专家分类的创建、查询、修改和删除。"},
    {"name": "专家管理", "description": "专家的创建、查询、修改、删除和状态切换。"},
    {"name": "权限管理", "description": "平台角色、租户角色和成员授权管理。"},
    {"name": "模型", "description": "租户侧可用模型信息。"},
    {"name": "运维", "description": "系统运维和清理操作。"},
    {"name": "聊天", "description": "租户侧聊天会话、消息和任务接口。"},
    {"name": "知识库", "description": "平台侧知识库管理。"},
    {"name": "文档", "description": "知识库文档上传、查看、更新和删除。"},
    {"name": "构建", "description": "知识库构建相关占位接口。"},
    {"name": "技能", "description": "平台侧技能上传、查看、更新和删除。"},
]

OPENAPI_OPERATION_SUMMARIES = {
    ("GET", "/health"): "健康检查",
    ("POST", "/api/v1/auth/login"): "用户登录",
    ("POST", "/api/v1/auth/refresh"): "刷新访问令牌",
    ("POST", "/api/v1/auth/logout"): "退出登录",
    ("POST", "/api/v1/users/register"): "注册普通用户",
    ("GET", "/api/v1/users"): "获取普通用户列表",
    ("POST", "/api/v1/users/platform/activate"): "激活平台用户",
    ("GET", "/api/v1/users/platform"): "获取平台用户列表",
    ("POST", "/api/v1/users/platform"): "创建平台用户",
    ("GET", "/api/v1/users/{user_id}/tenants"): "获取用户所属租户",
    ("GET", "/api/v1/users/{user_id}"): "获取用户详情",
    ("PATCH", "/api/v1/users/{user_id}"): "更新用户基础信息",
    ("PATCH", "/api/v1/users/{user_id}/status"): "更新用户状态",
    ("GET", "/api/v1/tenants"): "获取租户列表",
    ("POST", "/api/v1/tenants"): "创建租户",
    ("GET", "/api/v1/tenants/{tenant_id}"): "获取租户详情",
    ("PATCH", "/api/v1/tenants/{tenant_id}"): "更新租户信息",
    ("PATCH", "/api/v1/tenants/{tenant_id}/status"): "更新租户状态",
    ("GET", "/api/v1/tenants/{tenant_id}/members"): "获取租户成员列表",
    ("POST", "/api/v1/tenants/{tenant_id}/members"): "添加租户成员",
    ("PATCH", "/api/v1/tenants/{tenant_id}/members/{user_id}"): "更新租户成员角色",
    ("DELETE", "/api/v1/tenants/{tenant_id}/members/{user_id}"): "移除租户成员",
    ("GET", "/api/v1/expert-categories"): "获取专家分类列表",
    ("POST", "/api/v1/expert-categories"): "创建专家分类",
    ("GET", "/api/v1/expert-categories/{category_id}"): "获取专家分类详情",
    ("PATCH", "/api/v1/expert-categories/{category_id}"): "更新专家分类",
    ("DELETE", "/api/v1/expert-categories/{category_id}"): "删除专家分类",
    ("GET", "/api/v1/experts"): "获取专家列表",
    ("GET", "/api/v1/experts/search/name"): "按专家名称搜索专家",
    ("GET", "/api/v1/experts/search/category"): "按专家分类搜索专家",
    ("GET", "/api/v1/experts/search/status"): "按专家状态搜索专家",
    ("POST", "/api/v1/experts"): "创建专家",
    ("GET", "/api/v1/experts/stats/summary"): "获取专家统计数据",
    ("GET", "/api/v1/experts/{expert_id}"): "获取专家详情",
    ("PATCH", "/api/v1/experts/{expert_id}"): "更新专家信息",
    ("DELETE", "/api/v1/experts/{expert_id}"): "删除专家",
    ("PATCH", "/api/v1/experts/{expert_id}/status"): "更新专家状态",
    ("GET", "/api/v1/rbac/tenant/users"): "获取当前租户用户列表",
    ("POST", "/api/v1/rbac/tenant/users/{user_id}/roles"): "授予或更新租户角色",
    ("DELETE", "/api/v1/rbac/tenant/users/{user_id}"): "移除当前租户成员",
    ("GET", "/api/v1/rbac/platform/roles"): "获取平台角色列表",
    ("POST", "/api/v1/rbac/platform/users/{user_id}/roles"): "授予平台角色",
    ("DELETE", "/api/v1/rbac/platform/users/{user_id}/roles/{role}"): "撤销平台角色",
    ("GET", "/api/v1/models/llm"): "获取大语言模型列表",
    ("GET", "/api/v1/models/embedding"): "获取嵌入模型信息",
    ("GET", "/api/v1/ops/metrics"): "获取系统指标",
    ("POST", "/api/v1/ops/storage/gc"): "执行对象存储清理",
    ("POST", "/api/v1/chat/sessions"): "创建聊天会话",
    ("GET", "/api/v1/chat/sessions"): "获取聊天会话列表",
    ("GET", "/api/v1/chat/sessions/{session_id}/messages"): "获取聊天消息列表",
    ("PATCH", "/api/v1/chat/sessions/{session_id}/title"): "重命名聊天会话",
    ("PATCH", "/api/v1/chat/sessions/{session_id}/pin"): "置顶或取消置顶聊天会话",
    ("POST", "/api/v1/chat/tasks"): "创建聊天任务",
    ("POST", "/api/v1/chat/tasks/{task_id}/cancel"): "取消聊天任务",
    ("GET", "/api/v1/chat/tasks/{task_id}/position"): "获取聊天任务排队位置",
    ("GET", "/api/v1/chat/tasks/{task_id}/events"): "订阅聊天任务事件",
    ("POST", "/api/v1/knowledge-bases"): "创建知识库",
    ("GET", "/api/v1/knowledge-bases"): "获取知识库列表",
    ("GET", "/api/v1/knowledge-bases/{knowledge_base_id}"): "获取知识库详情",
    ("PATCH", "/api/v1/knowledge-bases/{knowledge_base_id}"): "更新知识库",
    ("DELETE", "/api/v1/knowledge-bases/{knowledge_base_id}"): "删除知识库",
    ("POST", "/api/v1/knowledge-bases/{knowledge_base_id}/docs/upload-url"): "创建文档上传地址",
    ("POST", "/api/v1/knowledge-bases/{knowledge_base_id}/docs/complete-upload"): "完成文档上传",
    ("GET", "/api/v1/knowledge-bases/{knowledge_base_id}/docs"): "获取知识库文档列表",
    ("GET", "/api/v1/knowledge-bases/{knowledge_base_id}/docs/{document_id}"): "获取文档详情",
    ("PATCH", "/api/v1/knowledge-bases/{knowledge_base_id}/docs/{document_id}"): "更新文档信息",
    ("DELETE", "/api/v1/knowledge-bases/{knowledge_base_id}/docs/{document_id}"): "删除文档",
    (
        "GET",
        "/api/v1/knowledge-bases/{knowledge_base_id}/docs/{document_id}/download-url",
    ): "获取文档下载地址",
    ("POST", "/api/v1/knowledge-bases/{knowledge_base_id}/build"): "触发知识库构建",
    ("GET", "/api/v1/knowledge-bases/{knowledge_base_id}/builds"): "获取知识库构建列表",
    ("GET", "/api/v1/knowledge-bases/{knowledge_base_id}/builds/{build_id}"): "获取知识库构建详情",
    (
        "POST",
        "/api/v1/knowledge-bases/{knowledge_base_id}/builds/{build_id}/cancel",
    ): "取消知识库构建",
    ("POST", "/api/v1/skills"): "上传技能",
    ("GET", "/api/v1/skills"): "获取技能列表",
    ("GET", "/api/v1/skills/{slug}"): "获取技能详情",
    ("PUT", "/api/v1/skills/{slug}"): "更新技能",
    ("DELETE", "/api/v1/skills/{slug}"): "删除技能",
    ("GET", "/api/v1/skills/{slug}/file"): "获取技能文件",
}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if settings.database_auto_migrate:
            migrate_database(settings)
        yield

    app = FastAPI(
        title="Amazon Experts 后端接口文档",
        version="0.1.0",
        description=(
            "Amazon Experts 后端服务的 Swagger/OpenAPI 文档。"
            "平台侧接口不需要 x-tenant-id；租户侧接口需要在请求头中传入 x-tenant-id。"
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

    @app.get("/health", tags=["健康检查"], summary="健康检查")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "amazon-experts-backend"}

    app.include_router(api_router, prefix="/api/v1")
    _localize_operation_summaries(app)
    return app

def _localize_operation_summaries(app: FastAPI) -> None:
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods or set():
            summary = OPENAPI_OPERATION_SUMMARIES.get((method, route.path))
            if summary:
                route.summary = summary


app = create_app()
