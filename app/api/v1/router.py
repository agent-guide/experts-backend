from fastapi import APIRouter

from app.api.v1.routers import admin, auth, chat, documents, knowledge_bases, models, ops, skills, uploads

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(models.router, prefix="/models", tags=["models"])
api_router.include_router(ops.router, prefix="/ops", tags=["ops"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(knowledge_bases.router, prefix="/knowledge-bases", tags=["knowledge-bases"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(uploads.router, prefix="/uploads", tags=["uploads"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(skills.router, prefix="/skills", tags=["skills"])
