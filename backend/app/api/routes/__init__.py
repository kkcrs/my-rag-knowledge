"""API route registry."""

from fastapi import APIRouter

from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.api.routes.chat import router as chat_router

api_router = APIRouter(prefix="/api")
api_router.include_router(health_router)
api_router.include_router(documents_router)
api_router.include_router(chat_router)

__all__ = ["api_router", "documents_router", "health_router", "chat_router"]
