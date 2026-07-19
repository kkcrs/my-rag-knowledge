"""Backend application entrypoint."""

from fastapi import FastAPI

from app.api.error_handlers import register_error_handlers
from app.api.routes.health import router as health_router
from app.core.config import settings
from app.core.logging import configure_logging

configure_logging()

app = FastAPI(title=settings.app_name)
register_error_handlers(app)
app.include_router(health_router)


def main() -> None:
    print("Hello from backend!")


if __name__ == "__main__":
    main()
