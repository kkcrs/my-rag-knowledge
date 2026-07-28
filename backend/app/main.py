"""FastAPI application entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.error_handlers import register_error_handlers
from app.api.routes import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.observability import configure_observability


def create_app() -> FastAPI:
    configure_logging()
    configure_observability()
    logger = get_logger(__name__)

    app = FastAPI(title=settings.app_name)

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
