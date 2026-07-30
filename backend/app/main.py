"""FastAPI application entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.error_handlers import register_error_handlers
from app.api.routes import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.observability import configure_observability
from app.db.seed import seed_default_admin


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger = get_logger(__name__)
    if not settings.jwt_secret:
        logger.error(
            "JWT_SECRET 未配置，签发功能将不可用，请在 .env 中设置 JWT_SECRET"
        )
    try:
        await seed_default_admin()
    except Exception:
        logger.exception("种子初始化失败；后续可重新启服务重试")
    yield


def create_app() -> FastAPI:
    configure_logging()
    configure_observability()
    logger = get_logger(__name__)

    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_error_handlers(app)
    app.include_router(api_router)

    logger.info("app initialized: %s", settings.app_name)
    return app


app = create_app()
