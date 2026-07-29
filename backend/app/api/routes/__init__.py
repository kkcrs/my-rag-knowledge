"""API route registry."""

from fastapi import APIRouter

from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.api.routes.chat import router as chat_router
from app.api.routes.evaluations import router as evaluations_router

api_router = APIRouter(prefix="/api")
api_router.include_router(health_router)
api_router.include_router(documents_router)
api_router.include_router(chat_router)
api_router.include_router(evaluations_router)

__all__ = ["api_router", "chat_router", "documents_router", "evaluations_router", "health_router"]
