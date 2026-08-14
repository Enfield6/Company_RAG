from fastapi import APIRouter

from app.api.routes import chat, documents, health, knowledge_bases

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(knowledge_bases.router)
api_router.include_router(documents.router)
api_router.include_router(chat.router)
